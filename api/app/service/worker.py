import json
import logging
from datetime import timedelta
from time import monotonic
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.models import Attempt, Operation, Resume, Status, utcnow
from app.service.errors import AppError, ProcessingError
from app.service.ports import Compiler, ModelResult, Optimizer, Storage
from app.service.proposals import TEMPLATE_VERSION, ProposalValidator
from app.service.resumes import lock_user

logger = logging.getLogger(__name__)


class Worker:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        storage: Storage,
        optimizer: Optimizer,
        compiler: Compiler,
    ) -> None:
        self.settings = settings
        self.database = database
        self.storage = storage
        self.optimizer = optimizer
        self.compiler = compiler
        self.validator = ProposalValidator()

    def claim(self) -> Attempt | None:
        now = utcnow()
        with self.database.sessions.begin() as session:
            stale = list(
                session.scalars(
                    select(Attempt)
                    .where(
                        Attempt.status == Status.PROCESSING,
                        Attempt.lease_until < now,
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            for item in stale:
                if item.executions >= self.settings.worker_max_executions:
                    item.status = Status.FAILED
                    item.etapa = "falha"
                    item.codigo_erro = "execucao_interrompida"
                    item.mensagem_erro = (
                        "A execução foi interrompida e atingiu o limite de tentativas."
                    )
                    item.completed_at = now
                else:
                    item.status = Status.PENDING
                    item.available_at = now + timedelta(seconds=self.settings.retry_base_seconds)
                item.lease_token = None
            session.flush()
            attempt = session.scalar(
                select(Attempt)
                .where(
                    Attempt.status == Status.PENDING,
                    Attempt.available_at <= now,
                )
                .order_by(Attempt.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if attempt is None:
                return None
            attempt.status = Status.PROCESSING
            attempt.etapa = (
                "openai" if attempt.tipo_operacao == Operation.OPTIMIZATION else "compilacao"
            )
            attempt.executions += 1
            attempt.started_at = now
            attempt.lease_token = uuid4()
            attempt.lease_until = now + timedelta(seconds=self.settings.worker_lease_seconds)
            return attempt

    def _locked_attempt(self, session: Session, claim: Attempt) -> tuple[Attempt, Resume] | None:
        lock_user(session, claim.usuario_id)
        resume = session.scalar(
            select(Resume)
            .where(Resume.id == claim.curriculo_id, Resume.usuario_id == claim.usuario_id)
            .with_for_update()
        )
        attempt = session.scalar(
            select(Attempt)
            .where(
                Attempt.id == claim.id,
                Attempt.lease_token == claim.lease_token,
                Attempt.status == Status.PROCESSING,
            )
            .with_for_update()
        )
        if attempt is None or resume is None:
            return None
        return attempt, resume

    def run_once(self) -> bool:
        self.cleanup()
        claim = self.claim()
        if claim is None:
            return False
        started = monotonic()
        try:
            if not claim.entrada_temporaria_key:
                raise ProcessingError("entrada_indisponivel", "Entrada da tentativa indisponível.")
            payload = json.loads(self.storage.read(claim.entrada_temporaria_key))
            model_result: ModelResult | None = None
            pdf: bytes | None = None
            if claim.tipo_operacao == Operation.OPTIMIZATION:
                model_result = self.optimizer.optimize(payload["texto"], payload["vaga"])
                self.validator.validate(model_result.proposal, payload["texto"], payload["vaga"])
            else:
                pdf = self.compiler.compile(payload["latex"])
            self._complete(claim, model_result, pdf)
        except ProcessingError as exc:
            self._fail(claim, exc)
        except AppError:
            self._fail(
                claim, ProcessingError("entrada_indisponivel", "Entrada indisponível ou expirada.")
            )
        except Exception:
            # Never record provider payloads, CVs or compiler logs in exception telemetry.
            self._fail(claim, ProcessingError("falha_interna", "Falha interna de processamento."))
        logger.info(
            "operation=%s elapsed_ms=%d", claim.tipo_operacao, int((monotonic() - started) * 1000)
        )
        return True

    def _complete(self, claim: Attempt, result: ModelResult | None, pdf: bytes | None) -> None:
        obsolete: list[str] = []
        created: list[str] = []
        try:
            with self.database.sessions.begin() as session:
                locked = self._locked_attempt(session, claim)
                if locked is None:
                    return
                attempt, resume = locked
                if result:
                    proposal = result.proposal
                    key = self.storage.put(proposal.latex_gerado.encode())
                    created.append(key)
                    generated = Resume(
                        id=uuid4(),
                        usuario_id=attempt.usuario_id,
                        curriculo_origem_id=resume.id,
                        tipo="otimizado",
                        nome_arquivo="curriculo-otimizado.tex",
                        arquivo_objeto_key=key,
                        descricao_vaga=resume.descricao_vaga,
                        latex_gerado=proposal.latex_gerado,
                        latex_revisao=1,
                        template_versao=TEMPLATE_VERSION,
                        conteudo_estruturado=proposal.model_dump(mode="json"),
                    )
                    session.add(generated)
                    session.flush()
                    attempt.curriculo_gerado_id = generated.id
                    attempt.status = Status.REVIEW
                    attempt.etapa = "revisao"
                    attempt.modelo = result.model
                    attempt.tokens_entrada = result.input_tokens
                    attempt.tokens_saida = result.output_tokens
                elif pdf is not None:
                    if attempt.tipo_operacao == Operation.PREVIEW:
                        if attempt.expires_at and attempt.expires_at <= utcnow():
                            raise ProcessingError("preview_expirada", "A prévia expirou.")
                        key = self.storage.put(pdf, temporary=True)
                        attempt.resultado_temporario_key = key
                    elif resume.latex_revisao != attempt.revisao_solicitada:
                        raise ProcessingError(
                            "revisao_alterada", "O código mudou. Solicite nova renderização."
                        )
                    else:
                        key = self.storage.put(pdf)
                        if resume.pdf_objeto_key:
                            obsolete.append(resume.pdf_objeto_key)
                        resume.pdf_objeto_key = key
                        resume.pdf_revisao = attempt.revisao_solicitada
                    created.append(key)
                    attempt.status = Status.COMPLETED
                    attempt.etapa = "finalizada"
                attempt.completed_at = utcnow()
                attempt.lease_token = None
                attempt.lease_until = None
                attempt.codigo_erro = None
                attempt.mensagem_erro = None
                if attempt.entrada_temporaria_key:
                    obsolete.append(attempt.entrada_temporaria_key)
                    attempt.entrada_temporaria_key = None
        except Exception:
            for key in created:
                self.storage.delete(key)
            raise
        for key in obsolete:
            self.storage.delete(key)
        logger.info(
            "operation=%s result=success input_tokens=%d output_tokens=%d",
            claim.tipo_operacao,
            result.input_tokens if result else 0,
            result.output_tokens if result else 0,
        )

    def _fail(self, claim: Attempt, error: ProcessingError) -> None:
        key: str | None = None
        with self.database.sessions.begin() as session:
            locked = self._locked_attempt(session, claim)
            if locked is None:
                return
            attempt, _ = locked
            if error.transient and attempt.executions < self.settings.worker_max_executions:
                attempt.status = Status.PENDING
                attempt.etapa = "nova_execucao"
                attempt.available_at = utcnow() + timedelta(
                    seconds=self.settings.retry_base_seconds * 2 ** (attempt.executions - 1)
                )
            else:
                attempt.status = Status.FAILED
                attempt.etapa = "falha"
                attempt.completed_at = utcnow()
                key = attempt.entrada_temporaria_key
                attempt.entrada_temporaria_key = None
            attempt.codigo_erro = error.code
            attempt.mensagem_erro = error.message
            attempt.lease_token = None
            attempt.lease_until = None
        if key:
            self.storage.delete(key)
        logger.info(
            "operation=%s result=failure code=%s transient=%s",
            claim.tipo_operacao,
            error.code,
            error.transient,
        )

    def cleanup(self) -> None:
        keys: list[str] = []
        with self.database.sessions.begin() as session:
            terminal = session.scalars(
                select(Attempt)
                .where(
                    Attempt.status.in_((Status.FAILED, Status.CANCELLED)),
                    Attempt.entrada_temporaria_key.is_not(None),
                )
                .with_for_update(skip_locked=True)
            )
            for attempt in terminal:
                if attempt.entrada_temporaria_key:
                    keys.append(attempt.entrada_temporaria_key)
                    attempt.entrada_temporaria_key = None
            expired = list(
                session.scalars(
                    select(Attempt)
                    .where(
                        Attempt.tipo_operacao == Operation.PREVIEW,
                        Attempt.expires_at <= utcnow(),
                        or_(
                            Attempt.entrada_temporaria_key.is_not(None),
                            Attempt.resultado_temporario_key.is_not(None),
                            Attempt.status.in_((Status.PENDING, Status.PROCESSING)),
                        ),
                    )
                    .with_for_update(skip_locked=True)
                )
            )
            for attempt in expired:
                keys.extend(
                    key
                    for key in (attempt.entrada_temporaria_key, attempt.resultado_temporario_key)
                    if key
                )
                attempt.entrada_temporaria_key = None
                attempt.resultado_temporario_key = None
                attempt.lease_token = None
                if attempt.status in (Status.PENDING, Status.PROCESSING):
                    attempt.status = Status.FAILED
                    attempt.codigo_erro = "preview_expirada"
                    attempt.mensagem_erro = "A prévia expirou. Solicite outra compilação."
                    attempt.completed_at = utcnow()
            protected = set(
                session.scalars(
                    select(Attempt.entrada_temporaria_key).where(
                        Attempt.entrada_temporaria_key.is_not(None)
                    )
                )
            ) | set(
                session.scalars(
                    select(Attempt.resultado_temporario_key).where(
                        Attempt.resultado_temporario_key.is_not(None),
                        Attempt.expires_at > utcnow(),
                    )
                )
            )
        for key in keys:
            self.storage.delete(key)
        self.storage.purge(self.settings.preview_ttl_seconds, {key for key in protected if key})
