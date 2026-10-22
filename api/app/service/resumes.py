import hashlib
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.extraction import normalize_text
from app.infrastructure.models import (
    ACTIVE_STATUSES,
    QUOTA_STATUSES,
    Attempt,
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
            if attempt.status in ACTIVE_STATUSES:
                attempt.status = Status.CANCELLED
                attempt.completed_at = utcnow()
            elif attempt.status == Status.REVIEW:
                attempt.status = Status.COMPLETED
            attempt.lease_token = None
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
    ) -> Attempt:
        lock_user(session, user_id)
        resume = owned_resume(session, user_id, resume_id, lock=True)
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
        else:
            if resume.tipo != "otimizado":
                raise AppError("operacao_invalida", "Selecione uma versão otimizada.")
            payload = {"latex": latex if latex is not None else resume.latex_gerado}
            if not payload["latex"]:
                raise AppError("latex_inexistente", "Não há código LaTeX para compilar.", 422)
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
        fingerprint = hashlib.sha256(
            str(resume_id).encode() + operation.encode() + encoded
        ).hexdigest()
        if idempotency_key:
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
        if operation == Operation.OPTIMIZATION:
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
                        Attempt.tipo_operacao != Operation.OPTIMIZATION,
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
                        Attempt.tipo_operacao != Operation.OPTIMIZATION,
                        Attempt.created_at >= now - timedelta(minutes=1),
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
