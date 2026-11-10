import json
import logging
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.models import (
    Attempt,
    Interview,
    InterviewRound,
    Operation,
    Status,
    User,
    utcnow,
)
from app.presentation.interviews import (
    Conflict,
    InterviewAnalysis,
    Question,
)
from app.presentation.interviews import (
    InterviewStatus as State,
)
from app.service.errors import ProcessingError
from app.service.interview_validation import validate_analysis
from app.service.interviews import InterviewService, analysis_executions_today
from app.service.ports import AnalysisResult, InterviewAnalyzer
from app.service.resumes import lock_user

logger = logging.getLogger(__name__)


class InterviewProcessor:
    def __init__(
        self,
        settings: Settings,
        database: Database,
        service: InterviewService,
        analyzer: InterviewAnalyzer | None,
    ) -> None:
        self.settings = settings
        self.database = database
        self.service = service
        self.analyzer = analyzer

    def cleanup(self) -> None:
        with self.database.sessions() as db:
            candidates = list(
                db.execute(
                    select(Interview.id, Interview.usuario_id).where(
                        Interview.status.in_(
                            (State.ANALYZING, State.ANSWERING, State.REVIEW, State.FAILED)
                        ),
                        Interview.expires_at <= utcnow(),
                    )
                )
            )
        for identifier, owner in candidates:
            with self.database.sessions.begin() as db:
                lock_user(db, owner)
                item = db.get(Interview, identifier, with_for_update=True)
                if item:
                    self.service.expire(db, item)

    def _locked(
        self, db: Session, claim: Attempt
    ) -> tuple[Interview, InterviewRound, Attempt] | None:
        lock_user(db, claim.usuario_id)
        item = db.get(Interview, claim.sessao_complementacao_id, with_for_update=True)
        if item is None:
            return None
        self.service.expire(db, item)
        round_item = db.get(InterviewRound, claim.rodada_complementacao_id, with_for_update=True)
        attempt = db.get(Attempt, claim.id, with_for_update=True)
        if (
            round_item is None
            or attempt is None
            or item.status != State.ANALYZING
            or item.revisao != claim.sessao_revisao_esperada
            or item.rodada_atual != round_item.numero
            or attempt.status != Status.PROCESSING
            or attempt.lease_token != claim.lease_token
        ):
            return None
        return item, round_item, attempt

    def _terminal(self, item: Interview, attempt: Attempt, code: str, message: str) -> None:
        attempt.status = Status.FAILED
        attempt.etapa = "falha"
        attempt.codigo_erro = code
        attempt.mensagem_erro = message
        attempt.completed_at = utcnow()
        attempt.lease_token = None
        attempt.lease_until = None
        item.status = State.FAILED
        item.codigo_erro = code
        item.mensagem_erro = message
        item.revisao += 1

    def claim(self) -> Attempt | None:
        now = utcnow()
        with self.database.sessions() as db:
            candidates = list(
                db.execute(
                    select(Attempt.id, Attempt.usuario_id)
                    .where(
                        Attempt.tipo_operacao == Operation.ANALYSIS,
                        ((Attempt.status == Status.PENDING) & (Attempt.available_at <= now))
                        | ((Attempt.status == Status.PROCESSING) & (Attempt.lease_until < now)),
                    )
                    .order_by(Attempt.created_at)
                )
            )
        for identifier, owner in candidates:
            with self.database.sessions.begin() as db:
                if (
                    db.scalar(
                        select(User.id).where(User.id == owner).with_for_update(skip_locked=True)
                    )
                    is None
                ):
                    continue
                candidate = db.get(Attempt, identifier)
                if candidate is None or candidate.status not in (Status.PENDING, Status.PROCESSING):
                    continue
                item = db.get(Interview, candidate.sessao_complementacao_id, with_for_update=True)
                if item is None:
                    continue
                self.service.expire(db, item)
                attempt = db.scalar(
                    select(Attempt)
                    .where(Attempt.id == identifier)
                    .with_for_update(skip_locked=True)
                    .execution_options(populate_existing=True)
                )
                if (
                    attempt is None
                    or item.status != State.ANALYZING
                    or item.revisao != attempt.sessao_revisao_esperada
                ):
                    continue
                if attempt.status == Status.PROCESSING:
                    if attempt.lease_until and attempt.lease_until > now:
                        continue
                    if attempt.execucoes_ciclo >= self.settings.worker_max_executions:
                        self._terminal(
                            item,
                            attempt,
                            "execucao_interrompida",
                            "A análise foi interrompida e atingiu o limite de execuções.",
                        )
                        continue
                elif attempt.status != Status.PENDING or attempt.available_at > now:
                    continue
                if (
                    analysis_executions_today(db, owner)
                    >= self.settings.interview_executions_per_day
                ):
                    self._terminal(
                        item,
                        attempt,
                        "limite_analises",
                        "Limite diário de execuções de análise atingido.",
                    )
                    continue
                attempt.status = Status.PROCESSING
                attempt.etapa = "analise_complementacao"
                attempt.executions += 1
                attempt.execucoes_ciclo += 1
                attempt.execucoes_analise = [*attempt.execucoes_analise, now.isoformat()]
                attempt.started_at = now
                attempt.lease_token = uuid4()
                attempt.lease_until = now + timedelta(seconds=self.settings.worker_lease_seconds)
                return attempt
        return None

    def context(self, claim: Attempt) -> dict[str, object] | None:
        with self.database.sessions.begin() as db:
            locked = self._locked(db, claim)
            if locked is None:
                return None
            item, _, _ = locked
            rounds = list(
                db.scalars(
                    select(InterviewRound)
                    .where(InterviewRound.sessao_id == item.id)
                    .order_by(InterviewRound.numero)
                )
            )
            return {
                "curriculo_confirmado": item.texto_confirmado_snapshot,
                "descricao_vaga": item.descricao_vaga_snapshot,
                "rodada": item.rodada_atual,
                "limite_perguntas": self.settings.interview_questions_per_round,
                "correcao_anterior": claim.mensagem_erro,
                "historico": [
                    {
                        "perguntas": r.perguntas,
                        "respostas": r.respostas,
                        "complemento_livre": r.complemento_livre,
                        "complemento_livre_id": str(r.complemento_livre_id)
                        if r.complemento_livre_id
                        else None,
                    }
                    for r in rounds
                    if r.numero < item.rodada_atual
                ],
            }

    def validate(self, analysis: InterviewAnalysis, context: dict[str, object]) -> None:
        validate_analysis(analysis, context, self.settings.interview_questions_per_round)

    def execute(self, claim: Attempt) -> None:
        result: AnalysisResult | None = None
        try:
            context = self.context(claim)
            if context is None:
                return
            if (
                len(json.dumps(context, ensure_ascii=False))
                > self.settings.interview_max_context_chars
            ):
                raise ProcessingError(
                    "contexto_excessivo", "O contexto da entrevista excede o limite."
                )
            if self.analyzer is None:
                raise ProcessingError("analisador_indisponivel", "Analisador não configurado.")
            result = self.analyzer.analyze(context)
            self.validate(result.analysis, context)
            self.complete(claim, result)
        except ProcessingError as error:
            self.fail(claim, error, result)
        except Exception:
            self.fail(claim, ProcessingError("falha_interna", "Falha interna de análise."), result)

    def complete(self, claim: Attempt, result: AnalysisResult) -> None:
        with self.database.sessions.begin() as db:
            locked = self._locked(db, claim)
            if locked is None:
                return
            item, round_item, attempt = locked
            round_item.perguntas = [
                Question(id=uuid4(), **q.model_dump()).model_dump(mode="json")
                for q in result.analysis.perguntas
            ]
            item.conflitos = [
                *item.conflitos,
                *[
                    Conflict(id=uuid4(), **c.model_dump()).model_dump(mode="json")
                    for c in result.analysis.conflitos
                ],
            ]
            item.status = (
                State.REVIEW if result.analysis.pronta_para_confirmacao else State.ANSWERING
            )
            item.revisao += 1
            attempt.status = Status.COMPLETED
            attempt.etapa = "finalizada"
            attempt.completed_at = utcnow()
            attempt.lease_token = None
            attempt.lease_until = None
            attempt.modelo = result.model
            attempt.tokens_entrada = (attempt.tokens_entrada or 0) + result.input_tokens
            attempt.tokens_saida = (attempt.tokens_saida or 0) + result.output_tokens
            attempt.codigo_erro = None
            attempt.mensagem_erro = None
        logger.info(
            "operation=analise_complementacao result=success input_tokens=%d output_tokens=%d",
            result.input_tokens,
            result.output_tokens,
        )

    def fail(
        self, claim: Attempt, error: ProcessingError, result: AnalysisResult | None = None
    ) -> None:
        with self.database.sessions.begin() as db:
            locked = self._locked(db, claim)
            if locked is None:
                return
            item, _, attempt = locked
            if result:
                attempt.modelo = result.model
                attempt.tokens_entrada = (attempt.tokens_entrada or 0) + result.input_tokens
                attempt.tokens_saida = (attempt.tokens_saida or 0) + result.output_tokens
            if (
                error.transient
                and attempt.execucoes_ciclo < self.settings.worker_max_executions
                and analysis_executions_today(db, attempt.usuario_id)
                < self.settings.interview_executions_per_day
            ):
                attempt.status = Status.PENDING
                attempt.etapa = "nova_execucao"
                attempt.available_at = utcnow() + timedelta(
                    seconds=self.settings.retry_base_seconds * 2 ** (attempt.execucoes_ciclo - 1)
                )
                attempt.codigo_erro = error.code
                attempt.mensagem_erro = error.message
                attempt.lease_token = None
            else:
                self._terminal(item, attempt, error.code, error.message)
        logger.info(
            "operation=analise_complementacao result=failure code=%s transient=%s",
            error.code,
            error.transient,
        )
