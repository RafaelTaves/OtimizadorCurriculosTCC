import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.extraction import normalize_text
from app.infrastructure.models import (
    ACTIVE_STATUSES,
    QUOTA_STATUSES,
    Attempt,
    IdempotencyRecord,
    Interview,
    InterviewRound,
    Operation,
    Resume,
    Status,
    User,
    utcnow,
)
from app.presentation.schemas import UsageView
from app.service.errors import AppError
from app.service.ports import Extractor, Storage

logger = logging.getLogger(__name__)


def compilation_fingerprint(
    resume_id: UUID, operation: Operation, encoded: bytes, compiler_image: str
) -> str:
    prefix = str(resume_id).encode() + operation.encode()
    # Version image tags when changing the compiler or its packages.
    if operation == Operation.PREVIEW:
        prefix += compiler_image.encode() + b"\0"
    return hashlib.sha256(prefix + encoded).hexdigest()


def month_window(now: datetime) -> tuple[datetime, datetime]:
    start = now.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, end


def owned_resume(session: Session, user_id: UUID, resume_id: UUID, *, lock: bool = False) -> Resume:
    query = select(Resume).where(Resume.id == resume_id, Resume.usuario_id == user_id)
    if lock:
        query = query.with_for_update()
    resume = session.scalar(query.execution_options(populate_existing=True))
    if resume is None:
        raise AppError("curriculo_inexistente", "Currículo inexistente.", 404)
    return resume


def lock_user(session: Session, user_id: UUID) -> None:
    session.execute(select(User.id).where(User.id == user_id).with_for_update()).one()


def require_human_review(session: Session, user_id: UUID, resume: Resume) -> None:
    if resume.tipo != "otimizado":
        return
    confirmed = session.scalar(
        select(Attempt.id).where(
            Attempt.curriculo_gerado_id == resume.id,
            Attempt.usuario_id == user_id,
            Attempt.tipo_operacao == Operation.OPTIMIZATION,
            Attempt.status == Status.COMPLETED,
        )
    )
    if confirmed is None:
        raise AppError(
            "revisao_pendente",
            "Confirme a revisão da proposta antes de editar ou exportar.",
            409,
        )


class ResumeService:
    def __init__(self, settings: Settings, storage: Storage, extractor: Extractor) -> None:
        self.settings = settings
        self.storage = storage
        self.extractor = extractor

    def upload(
        self,
        session: Session,
        user_id: UUID,
        data: bytes,
        filename: str,
        job: str,
    ) -> Resume:
        job = job.strip()
        if not 30 <= len(job) <= 20_000:
            raise AppError(
                "vaga_invalida", "A descrição da vaga deve ter de 30 a 20000 caracteres.", 422
            )
        try:
            text = self.extractor.extract(data, filename)
        except AppError as error:
            logger.info("upload=rejected code=%s", error.code)
            raise
        key = self.storage.put(data)
        safe_name = PurePosixPath(filename.replace("\\", "/")).name[:255] or "curriculo"
        resume = Resume(
            usuario_id=user_id,
            tipo="original",
            nome_arquivo=safe_name,
            arquivo_objeto_key=key,
            descricao_vaga=job,
            texto_extraido=text,
        )
        session.add(resume)
        try:
            session.commit()
        except Exception:
            session.rollback()
            self.storage.delete(key)
            raise
        logger.info("upload=accepted")
        return resume

    def confirm_text(self, session: Session, user_id: UUID, resume_id: UUID, text: str) -> Resume:
        lock_user(session, user_id)
        resume = owned_resume(session, user_id, resume_id, lock=True)
        if resume.tipo != "original":
            raise AppError("operacao_invalida", "Somente o texto do original pode ser confirmado.")
        text = normalize_text(text)
        if len(text) < 50 or len(text) > self.settings.max_extracted_chars:
            raise AppError("texto_invalido", "O texto deve ter de 50 a 60000 caracteres.", 422)
        resume.texto_extraido = text
        resume.texto_confirmado = True
        session.commit()
        return resume

    def save_latex(
        self,
        session: Session,
        user_id: UUID,
        resume_id: UUID,
        latex: str,
        etag: str | None,
    ) -> Resume:
        self.validate_latex(latex)
        resume = owned_resume(session, user_id, resume_id, lock=True)
        if resume.tipo != "otimizado":
            raise AppError("operacao_invalida", "O original não possui código LaTeX editável.")
        if etag is None:
            raise AppError("revisao_obrigatoria", "Informe o ETag atual em If-Match.", 428)
        if etag != f'"{resume.latex_revisao}"':
            raise AppError(
                "edicao_concorrente", "O currículo mudou. Recarregue antes de salvar.", 412
            )
        require_human_review(session, user_id, resume)
        if latex == resume.latex_gerado:
            session.commit()
            return resume
        new_tex = self.storage.put(latex.encode("utf-8"))
        old_tex = resume.arquivo_objeto_key
        resume.arquivo_objeto_key = new_tex
        resume.latex_gerado = latex
        resume.latex_revisao += 1
        # A PDF from an earlier revision must never be advertised as current.
        old_pdf = resume.pdf_objeto_key
        resume.pdf_objeto_key = None
        resume.pdf_revisao = None
        try:
            session.commit()
        except Exception:
            session.rollback()
            self.storage.delete(new_tex)
            raise
        if old_tex:
            self.storage.delete(old_tex)
        if old_pdf:
            self.storage.delete(old_pdf)
        return resume

    def validate_latex(self, latex: str) -> None:
        if not latex.strip():
            raise AppError("latex_vazio", "Informe o código LaTeX.", 422)
        if len(latex.encode("utf-8")) > self.settings.max_latex_bytes:
            raise AppError("latex_excessivo", "Código LaTeX excede o limite de bytes.", 413)

    def delete(self, session: Session, user_id: UUID, resume_id: UUID) -> None:
        lock_user(session, user_id)
        resume = owned_resume(session, user_id, resume_id, lock=True)
        ids = [resume.id]
        if resume.tipo == "original":
            ids += list(
                session.scalars(
                    select(Resume.id).where(
                        Resume.curriculo_origem_id == resume.id, Resume.usuario_id == user_id
                    )
                )
            )
        resumes = list(session.scalars(select(Resume).where(Resume.id.in_(ids))))
        attempts = list(
            session.scalars(
                select(Attempt)
                .where(
                    Attempt.usuario_id == user_id,
                    (Attempt.curriculo_id.in_(ids) | Attempt.curriculo_gerado_id.in_(ids)),
                )
                .with_for_update()
            )
        )
        keys: list[str] = []
        for attempt in attempts:
            for key in (attempt.entrada_temporaria_key, attempt.resultado_temporario_key):
                if key:
                    keys.append(key)
            attempt.entrada_temporaria_key = None
            attempt.resultado_temporario_key = None
            attempt.curriculo_id = None
            attempt.curriculo_gerado_id = None
            if resume.tipo == "original":
                attempt.rodada_complementacao_id = None
                attempt.sessao_complementacao_id = None
            if attempt.status in ACTIVE_STATUSES:
                attempt.status = Status.CANCELLED
                attempt.completed_at = utcnow()
            elif attempt.status == Status.REVIEW:
                attempt.status = Status.COMPLETED
            attempt.lease_token = None
        session.flush()
        if resume.tipo == "original":
            interviews = list(
                session.scalars(
                    select(Interview).where(
                        Interview.usuario_id == user_id, Interview.curriculo_id == resume.id
                    )
                )
            )
            for interview in interviews:
                for record in session.scalars(
                    select(IdempotencyRecord).where(IdempotencyRecord.sessao_id == interview.id)
                ):
                    record.resposta = None
                    record.sessao_id = None
                session.flush()
                for round_item in session.scalars(
                    select(InterviewRound).where(InterviewRound.sessao_id == interview.id)
                ):
                    session.delete(round_item)
                session.flush()
                session.delete(interview)
                session.flush()
        for item in resumes:
            keys.extend(k for k in (item.arquivo_objeto_key, item.pdf_objeto_key) if k)
        # Delete descendants first; keep anonymous technical attempts to prevent quota refunds.
        for item in sorted(resumes, key=lambda item: item.tipo == "original"):
            session.delete(item)
            session.flush()
        session.commit()
        for key in keys:
            self.storage.delete(key)


class QueueService:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage

    def usage(self, session: Session, user_id: UUID, now: datetime | None = None) -> UsageView:
        start, end = month_window(now or utcnow())
        used = (
            session.scalar(
                select(func.count())
                .select_from(Attempt)
                .where(
                    Attempt.usuario_id == user_id,
                    Attempt.tipo_operacao == Operation.OPTIMIZATION,
                    Attempt.created_at >= start,
                    Attempt.created_at < end,
                    Attempt.status.in_(QUOTA_STATUSES),
                )
            )
            or 0
        )
        return UsageView(
            limite=self.settings.monthly_optimization_limit,
            usado=used,
            restante=max(0, self.settings.monthly_optimization_limit - used),
            inicio_periodo=start,
            proximo_reinicio=end,
        )

    def enqueue(
        self,
        session: Session,
        user_id: UUID,
        resume_id: UUID,
        operation: Operation,
        *,
        idempotency_key: str | None = None,
        consent: bool = False,
        latex: str | None = None,
        interview_id: UUID | None = None,
    ) -> Attempt:
        lock_user(session, user_id)
        resume = owned_resume(session, user_id, resume_id, lock=True)
        if operation == Operation.ANALYSIS:
            raise AppError("operacao_invalida", "Use o serviço de complementação.")
        payload: dict[str, object]
        if operation == Operation.OPTIMIZATION:
            if not consent:
                raise AppError(
                    "consentimento_obrigatorio",
                    "Confirme o envio do currículo e da vaga à OpenAI.",
                    422,
                )
            if resume.tipo != "original" or not resume.texto_confirmado:
                raise AppError(
                    "texto_nao_confirmado", "Revise e confirme o texto antes de otimizar.", 422
                )
            if not idempotency_key or not 1 <= len(idempotency_key) <= 128:
                raise AppError(
                    "idempotencia_obrigatoria", "Informe Idempotency-Key de até 128 caracteres."
                )
            payload = {"texto": resume.texto_extraido, "vaga": resume.descricao_vaga}
            if interview_id:
                from app.service.interviews import InterviewService

                payload = InterviewService(self.settings, self.storage).generation_sources(
                    session, user_id, resume_id, interview_id, validate_context=False
                )
        else:
            if resume.tipo != "otimizado":
                raise AppError("operacao_invalida", "Selecione uma versão otimizada.")
            require_human_review(session, user_id, resume)
            payload = {"latex": latex if latex is not None else resume.latex_gerado}
            if not payload["latex"]:
                raise AppError("latex_inexistente", "Não há código LaTeX para compilar.", 422)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        fingerprint = compilation_fingerprint(
            resume_id, operation, encoded, self.settings.compiler_image
        )
        if idempotency_key:
            if session.scalar(
                select(IdempotencyRecord.id).where(
                    IdempotencyRecord.usuario_id == user_id,
                    IdempotencyRecord.chave == idempotency_key,
                )
            ):
                raise AppError("chave_reutilizada", "Chave usada em outra operação.", 409)
            existing = session.scalar(
                select(Attempt).where(
                    Attempt.usuario_id == user_id, Attempt.idempotency_key == idempotency_key
                )
            )
            if existing:
                if existing.request_hash != fingerprint:
                    raise AppError(
                        "chave_reutilizada", "Chave de idempotência usada com outra entrada.", 409
                    )
                session.commit()
                return existing
        now = utcnow()
        if operation == Operation.EXPORT and idempotency_key is None:
            reused = self._reuse_pdf(session, resume, encoded, fingerprint, now)
            if reused is not None:
                return reused
        if operation == Operation.OPTIMIZATION:
            if interview_id:
                from app.service.interviews import InterviewService

                InterviewService(self.settings, self.storage).generation_sources(
                    session, user_id, resume_id, interview_id
                )
                if session.scalar(
                    select(Attempt.id).where(
                        Attempt.sessao_complementacao_id == interview_id,
                        Attempt.tipo_operacao == Operation.OPTIMIZATION,
                    )
                ):
                    raise AppError("sessao_ja_utilizada", "Esta sessão já possui uma geração.", 409)
            usage = self.usage(session, user_id, now)
            if not usage.restante:
                raise AppError(
                    "cota_excedida",
                    f"Limite mensal atingido. Renova em {usage.proximo_reinicio.isoformat()}.",
                    429,
                    {
                        "Retry-After": str(
                            max(1, int((usage.proximo_reinicio - now).total_seconds()))
                        )
                    },
                )
            if not self.settings.openai_model or not self.settings.openai_api_key:
                raise AppError(
                    "ia_nao_configurada", "A integração OpenAI não está configurada.", 503
                )
        else:
            active = (
                session.scalar(
                    select(func.count())
                    .select_from(Attempt)
                    .where(
                        Attempt.usuario_id == user_id,
                        Attempt.tipo_operacao.in_((Operation.PREVIEW, Operation.EXPORT)),
                        Attempt.status.in_(ACTIVE_STATUSES),
                    )
                )
                or 0
            )
            recent = (
                session.scalar(
                    select(func.count())
                    .select_from(Attempt)
                    .where(
                        Attempt.usuario_id == user_id,
                        Attempt.tipo_operacao.in_((Operation.PREVIEW, Operation.EXPORT)),
                        Attempt.created_at >= now - timedelta(minutes=1),
                        or_(Attempt.status != Status.COMPLETED, Attempt.executions > 0),
                    )
                )
                or 0
            )
            if (
                active >= self.settings.max_active_compilations
                or recent >= self.settings.previews_per_minute
            ):
                raise AppError(
                    "compilacoes_excedidas",
                    "Aguarde antes de solicitar outra compilação.",
                    429,
                    {"Retry-After": "60"},
                )
        key = self.storage.put(encoded, temporary=True)
        attempt = Attempt(
            usuario_id=user_id,
            curriculo_id=resume_id,
            tipo_operacao=operation,
            sessao_complementacao_id=interview_id,
            idempotency_key=idempotency_key,
            request_hash=fingerprint,
            entrada_temporaria_key=key,
            revisao_solicitada=resume.latex_revisao,
            expires_at=now + timedelta(seconds=self.settings.preview_ttl_seconds)
            if operation == Operation.PREVIEW
            else None,
        )
        session.add(attempt)
        try:
            session.commit()
        except Exception:
            session.rollback()
            self.storage.delete(key)
            raise
        return attempt

    def _reuse_pdf(
        self, session: Session, resume: Resume, encoded: bytes, fingerprint: str, now: datetime
    ) -> Attempt | None:
        exports = select(Attempt).where(
            Attempt.usuario_id == resume.usuario_id,
            Attempt.curriculo_id == resume.id,
            Attempt.tipo_operacao == Operation.EXPORT,
            Attempt.revisao_solicitada == resume.latex_revisao,
        )
        if resume.pdf_objeto_key and resume.pdf_revisao == resume.latex_revisao:
            completed = session.scalar(
                exports.where(Attempt.status == Status.COMPLETED)
                .order_by(Attempt.created_at.desc())
                .limit(1)
            )
            if completed is not None:
                session.commit()
                logger.info("operation=exportacao result=reused_final")
                return completed

        active = session.scalar(exports.where(Attempt.status.in_(ACTIVE_STATUSES)).limit(1))
        if active is not None:
            session.commit()
            return active

        preview_hash = compilation_fingerprint(
            resume.id, Operation.PREVIEW, encoded, self.settings.compiler_image
        )
        preview = session.scalar(
            select(Attempt)
            .where(
                Attempt.usuario_id == resume.usuario_id,
                Attempt.curriculo_id == resume.id,
                Attempt.tipo_operacao == Operation.PREVIEW,
                Attempt.status == Status.COMPLETED,
                Attempt.request_hash == preview_hash,
                Attempt.expires_at > now,
                Attempt.resultado_temporario_key.is_not(None),
            )
            .order_by(Attempt.completed_at.desc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if preview is None or preview.resultado_temporario_key is None:
            return None
        try:
            pdf = self.storage.read(preview.resultado_temporario_key)
        except AppError as exc:
            if exc.code == "objeto_inexistente":
                return None
            raise
        if len(pdf) > self.settings.max_pdf_bytes or not pdf.startswith(b"%PDF-"):
            return None
        key = self.storage.put(pdf)
        obsolete = resume.pdf_objeto_key
        resume.pdf_objeto_key = key
        resume.pdf_revisao = resume.latex_revisao
        attempt = Attempt(
            usuario_id=resume.usuario_id,
            curriculo_id=resume.id,
            tipo_operacao=Operation.EXPORT,
            request_hash=fingerprint,
            revisao_solicitada=resume.latex_revisao,
            status=Status.COMPLETED,
            etapa="finalizada",
            completed_at=now,
        )
        session.add(attempt)
        try:
            session.commit()
        except Exception:
            session.rollback()
            self.storage.delete(key)
            raise
        if obsolete:
            self.storage.delete(obsolete)
        logger.info("operation=exportacao result=reused_preview")
        return attempt

    def confirm_review(self, session: Session, user_id: UUID, attempt_id: UUID) -> Attempt:
        attempt = session.scalar(
            select(Attempt)
            .where(
                Attempt.id == attempt_id,
                Attempt.usuario_id == user_id,
                Attempt.tipo_operacao == Operation.OPTIMIZATION,
            )
            .with_for_update()
        )
        if attempt is None:
            raise AppError("tentativa_inexistente", "Tentativa inexistente.", 404)
        if attempt.status not in (Status.REVIEW, Status.COMPLETED):
            raise AppError(
                "revisao_indisponivel", "A proposta ainda não está pronta para revisão.", 409
            )
        attempt.status = Status.COMPLETED
        attempt.completed_at = utcnow()
        session.commit()
        return attempt
