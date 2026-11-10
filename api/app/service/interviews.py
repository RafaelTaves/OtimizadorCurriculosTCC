import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.models import (
    ACTIVE_STATUSES,
    Attempt,
    IdempotencyRecord,
    Interview,
    InterviewRound,
    Operation,
    Status,
    utcnow,
)
from app.presentation.interviews import (
    Complement,
    ConfirmComplements,
    Conflict,
    ConflictResolution,
    InterviewPage,
    InterviewSummary,
    InterviewView,
    Question,
    RecordedAnswer,
    ReviseComplements,
    RoundView,
    StartInterview,
    SubmitAnswers,
)
from app.presentation.interviews import (
    InterviewStatus as State,
)
from app.service.errors import AppError
from app.service.ports import Storage
from app.service.resumes import QueueService, lock_user, owned_resume

ACTIVE_INTERVIEWS = (State.ANALYZING, State.ANSWERING, State.REVIEW, State.FAILED)
NEGATIVE = re.compile(
    r"\b(não|nao)\s+(tenho|tive|possuo|realizei|fiz|participei|conheço|sei|usei|utilizei)\b"
    r"|^(nenhum|nenhuma|nunca|sem experiência|sem experiencia)\b",
    re.IGNORECASE,
)


def context_hash(text: str | None, job: str | None) -> str:
    return hashlib.sha256(json.dumps([text, job], ensure_ascii=False).encode()).hexdigest()


def analysis_executions_today(db: Session, user_id: UUID) -> int:
    today = utcnow().date().isoformat()
    records = db.scalars(
        select(Attempt.execucoes_analise).where(
            Attempt.usuario_id == user_id, Attempt.tipo_operacao == Operation.ANALYSIS
        )
    )
    return sum(stamp.startswith(today) for dates in records for stamp in dates)


@dataclass(frozen=True)
class InterviewResult:
    view: InterviewView
    status: int = 200


class InterviewService:
    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.settings = settings
        self.storage = storage

    def view(self, db: Session, item: Interview) -> InterviewView:
        rounds = list(
            db.scalars(
                select(InterviewRound)
                .where(InterviewRound.sessao_id == item.id)
                .order_by(InterviewRound.numero)
            )
        )
        analysis = db.scalar(
            select(Attempt)
            .where(
                Attempt.sessao_complementacao_id == item.id,
                Attempt.tipo_operacao == Operation.ANALYSIS,
            )
            .order_by(Attempt.created_at.desc())
            .limit(1)
        )
        generation = db.scalar(
            select(Attempt.id).where(
                Attempt.sessao_complementacao_id == item.id,
                Attempt.tipo_operacao == Operation.OPTIMIZATION,
            )
        )
        return InterviewView(
            id=item.id,
            curriculo_id=item.curriculo_id,
            status=State(item.status),
            revisao=item.revisao,
            rodada_atual=item.rodada_atual,
            created_at=item.created_at,
            expires_at=item.expires_at,
            rodadas=[
                RoundView(
                    id=r.id,
                    numero=r.numero,
                    perguntas=[Question.model_validate(q) for q in r.perguntas],
                    respostas=[RecordedAnswer.model_validate(a) for a in r.respostas],
                    complemento_livre=r.complemento_livre,
                    complemento_livre_id=r.complemento_livre_id,
                    acao_apos_respostas=r.acao_apos_respostas,
                    created_at=r.created_at,
                )
                for r in rounds
            ],
            complementos=[Complement.model_validate(c) for c in item.complementos],
            conflitos=[Conflict.model_validate(c) for c in item.conflitos],
            resolucoes=[ConflictResolution.model_validate(r) for r in item.resolucoes],
            consentimento_em=item.consentimento_em,
            consentimento_versao=item.consentimento_versao,
            confirmado_em=item.confirmado_em,
            tentativa_id=analysis.id if analysis else None,
            geracao_id=generation,
            codigo_erro=item.codigo_erro,
            mensagem_erro=item.mensagem_erro,
            acompanhamento=f"/v1/complementacoes/{item.id}",
        )

    def owned(self, db: Session, user_id: UUID, interview_id: UUID) -> Interview:
        item = db.scalar(
            select(Interview)
            .where(
                Interview.id == interview_id,
                Interview.usuario_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if item is None:
            raise AppError("sessao_inexistente", "Sessão inexistente.", 404)
        previous_status = item.status
        self.expire(db, item)
        if previous_status != item.status:
            # Persist the purge even when the requested mutation is rejected below.
            db.commit()
        return item

    def expire(self, db: Session, item: Interview) -> None:
        if item.status in ACTIVE_INTERVIEWS and item.expires_at and item.expires_at <= utcnow():
            self.purge(db, item, State.EXPIRED)
            db.flush()

    def purge(self, db: Session, item: Interview, state: State) -> None:
        item.status = state
        item.revisao += 1
        item.texto_confirmado_snapshot = None
        item.descricao_vaga_snapshot = None
        item.complementos = []
        item.conflitos = []
        item.resolucoes = []
        item.codigo_erro = None
        item.mensagem_erro = None
        for round_item in db.scalars(
            select(InterviewRound).where(InterviewRound.sessao_id == item.id)
        ):
            round_item.perguntas = []
            round_item.respostas = []
            round_item.complemento_livre = None
        for record in db.scalars(
            select(IdempotencyRecord).where(IdempotencyRecord.sessao_id == item.id)
        ):
            record.resposta = None
        for attempt in db.scalars(
            select(Attempt).where(
                Attempt.sessao_complementacao_id == item.id,
                Attempt.tipo_operacao == Operation.ANALYSIS,
                Attempt.status.in_(ACTIVE_STATUSES),
            )
        ):
            attempt.status = Status.CANCELLED
            attempt.lease_token = None
            attempt.completed_at = utcnow()

    def get(self, db: Session, user_id: UUID, interview_id: UUID) -> InterviewView:
        lock_user(db, user_id)
        item = self.owned(db, user_id, interview_id)
        result = self.view(db, item)
        db.commit()
        return result

    def history(
        self, db: Session, user_id: UUID, resume_id: UUID, page: int, size: int
    ) -> InterviewPage:
        lock_user(db, user_id)
        owned_resume(db, user_id, resume_id)
        query = select(Interview).where(
            Interview.usuario_id == user_id, Interview.curriculo_id == resume_id
        )
        total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
        items = list(
            db.scalars(
                query.order_by(Interview.created_at.desc(), Interview.id)
                .offset((page - 1) * size)
                .limit(size)
            )
        )
        for item in items:
            self.expire(db, item)
        result = InterviewPage(
            itens=[
                InterviewSummary(
                    id=i.id,
                    curriculo_id=i.curriculo_id,
                    status=State(i.status),
                    revisao=i.revisao,
                    rodada_atual=i.rodada_atual,
                    created_at=i.created_at,
                    expires_at=i.expires_at,
                )
                for i in items
            ],
            total=total,
            pagina=page,
            tamanho=size,
        )
        db.commit()
        return result

    def _hash(self, route: str, resource: UUID, data: object) -> str:
        return hashlib.sha256(
            json.dumps([route, str(resource), data], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def replay(
        self, db: Session, user_id: UUID, key: str | None, fingerprint: str
    ) -> InterviewResult | None:
        if not key or not key.strip() or len(key) > 128:
            raise AppError(
                "idempotencia_obrigatoria", "Informe Idempotency-Key de até 128 caracteres."
            )
        record = db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.usuario_id == user_id, IdempotencyRecord.chave == key
            )
        )
        if record:
            if record.request_hash != fingerprint:
                raise AppError("chave_reutilizada", "Chave usada com outra rota ou entrada.", 409)
            if record.sessao_id:
                item = db.get(Interview, record.sessao_id)
                if item:
                    self.expire(db, item)
            if record.resposta is None:
                db.commit()
                raise AppError(
                    "resultado_expurgado", "O conteúdo da operação foi excluído ou expirou.", 410
                )
            result = InterviewResult(
                InterviewView.model_validate(record.resposta), record.status_http
            )
            db.commit()
            return result
        if db.scalar(
            select(Attempt.id).where(Attempt.usuario_id == user_id, Attempt.idempotency_key == key)
        ):
            raise AppError("chave_reutilizada", "Chave usada em outra operação.", 409)
        return None

    def finish(
        self,
        db: Session,
        item: Interview,
        key: str | None = None,
        fingerprint: str = "",
        operation: str = "",
        status: int = 200,
    ) -> InterviewResult:
        db.flush()
        result = InterviewResult(self.view(db, item), status)
        if key:
            db.add(
                IdempotencyRecord(
                    usuario_id=item.usuario_id,
                    sessao_id=item.id,
                    chave=key,
                    operacao=operation,
                    request_hash=fingerprint,
                    resposta=result.view.model_dump(mode="json"),
                    status_http=status,
                )
            )
        db.commit()
        return result

    def version(self, item: Interview, etag: str | None, allowed: tuple[State, ...]) -> None:
        if item.status in (State.EXPIRED, State.CANCELLED):
            raise AppError("sessao_encerrada", "A sessão expirou ou foi cancelada.", 409)
        if etag is None:
            raise AppError("revisao_obrigatoria", "Informe o ETag atual em If-Match.", 428)
        if etag != f'"{item.revisao}"':
            raise AppError(
                "edicao_concorrente", "A sessão mudou. Recarregue antes de continuar.", 412
            )
        if item.status not in allowed:
            raise AppError(
                "estado_incompativel", "Operação não permitida neste estado da sessão.", 409
            )

    def check_context(self, db: Session, item: Interview) -> None:
        if item.curriculo_id is None:
            raise AppError("curriculo_inexistente", "Currículo inexistente.", 404)
        resume = owned_resume(db, item.usuario_id, item.curriculo_id)
        if (
            not resume.texto_confirmado
            or context_hash(resume.texto_extraido, resume.descricao_vaga) != item.contexto_hash
        ):
            raise AppError(
                "contexto_alterado", "O currículo ou a vaga mudou. Inicie uma nova sessão.", 409
            )

    def check_ai(self, db: Session, user_id: UUID) -> None:
        if (
            not self.settings.openai_model
            or not self.settings.openai_api_key
            or not self.settings.openai_api_key.get_secret_value().strip()
        ):
            raise AppError("ia_nao_configurada", "A integração OpenAI não está configurada.", 503)
        if analysis_executions_today(db, user_id) >= self.settings.interview_executions_per_day:
            tomorrow = utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                days=1
            )
            raise AppError(
                "limite_analises",
                "Limite diário de análises atingido.",
                429,
                {"Retry-After": str(max(1, int((tomorrow - utcnow()).total_seconds())))},
            )

    def enqueue_analysis(self, db: Session, item: Interview, round_item: InterviewRound) -> Attempt:
        active = db.scalar(
            select(Attempt.id).where(
                Attempt.sessao_complementacao_id == item.id,
                Attempt.tipo_operacao == Operation.ANALYSIS,
                Attempt.status.in_(ACTIVE_STATUSES),
            )
        )
        if active:
            raise AppError("analise_em_andamento", "Uma análise já está em andamento.", 409)
        attempt = Attempt(
            usuario_id=item.usuario_id,
            curriculo_id=item.curriculo_id,
            tipo_operacao=Operation.ANALYSIS,
            sessao_complementacao_id=item.id,
            rodada_complementacao_id=round_item.id,
            sessao_revisao_esperada=item.revisao,
            request_hash=item.contexto_hash,
        )
        db.add(attempt)
        return attempt

    def start(
        self, db: Session, user_id: UUID, resume_id: UUID, data: StartInterview, key: str | None
    ) -> InterviewResult:
        lock_user(db, user_id)
        resume = owned_resume(db, user_id, resume_id, lock=True)
        fingerprint = self._hash("criar", resume_id, data.model_dump(mode="json"))
        replay = self.replay(db, user_id, key, fingerprint)
        if replay:
            return replay
        if not data.consentimento_envio_openai:
            raise AppError(
                "consentimento_obrigatorio",
                "Confirme o envio de currículo, vaga e respostas à OpenAI.",
                422,
            )
        if resume.tipo != "original" or not resume.texto_confirmado:
            raise AppError("texto_nao_confirmado", "Revise e confirme o texto original.", 422)
        for previous in db.scalars(
            select(Interview).where(
                Interview.usuario_id == user_id,
                Interview.curriculo_id == resume_id,
                Interview.status.in_(ACTIVE_INTERVIEWS),
            )
        ):
            self.expire(db, previous)
            if previous.status in ACTIVE_INTERVIEWS:
                raise AppError(
                    "sessao_ativa", "Já existe uma sessão ativa para este currículo.", 409
                )
        start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        count = (
            db.scalar(
                select(func.count())
                .select_from(IdempotencyRecord)
                .where(
                    IdempotencyRecord.usuario_id == user_id,
                    IdempotencyRecord.operacao == "criar",
                    IdempotencyRecord.created_at >= start,
                )
            )
            or 0
        )
        if count >= self.settings.interview_sessions_per_day:
            raise AppError(
                "limite_sessoes",
                "Limite diário de novas sessões atingido.",
                429,
                {"Retry-After": str(int((start + timedelta(days=1) - utcnow()).total_seconds()))},
            )
        if not QueueService(self.settings, self.storage).usage(db, user_id).restante:
            raise AppError("cota_excedida", "A cota mensal de otimizações está esgotada.", 429)
        self.check_ai(db, user_id)
        item = Interview(
            id=uuid4(),
            usuario_id=user_id,
            curriculo_id=resume_id,
            texto_confirmado_snapshot=resume.texto_extraido,
            descricao_vaga_snapshot=resume.descricao_vaga,
            contexto_hash=context_hash(resume.texto_extraido, resume.descricao_vaga),
            consentimento_versao=self.settings.interview_consent_version,
            expires_at=utcnow() + timedelta(seconds=self.settings.interview_ttl_seconds),
        )
        db.add(item)
        db.flush()
        round_item = InterviewRound(id=uuid4(), sessao_id=item.id, numero=1)
        db.add(round_item)
        db.flush()
        self.enqueue_analysis(db, item, round_item)
        return self.finish(db, item, key, fingerprint, "criar", 202)

    def _candidates(self, item: Interview, round_item: InterviewRound) -> None:
        candidates = [Complement.model_validate(c) for c in item.complementos]
        for raw in round_item.respostas:
            answer = RecordedAnswer.model_validate(raw)
            if (
                answer.texto
                and not answer.pulada
                and not answer.negativa
                and not NEGATIVE.search(answer.texto)
            ):
                candidates.append(
                    Complement(id=uuid4(), texto=answer.texto, resposta_origem_id=answer.id)
                )
        if round_item.complemento_livre and not NEGATIVE.search(round_item.complemento_livre):
            candidates.append(
                Complement(
                    id=uuid4(),
                    texto=round_item.complemento_livre,
                    resposta_origem_id=round_item.complemento_livre_id,
                )
            )
        item.complementos = [c.model_dump(mode="json") for c in candidates]

    def answers(
        self,
        db: Session,
        user_id: UUID,
        interview_id: UUID,
        data: SubmitAnswers,
        etag: str | None,
        key: str | None,
    ) -> InterviewResult:
        lock_user(db, user_id)
        item = self.owned(db, user_id, interview_id)
        fingerprint = self._hash("respostas", interview_id, data.model_dump(mode="json"))
        replay = self.replay(db, user_id, key, fingerprint)
        if replay:
            return replay
        self.version(item, etag, (State.ANSWERING, State.REVIEW, State.FAILED))
        if data.rodada != item.rodada_atual:
            raise AppError("rodada_invalida", "Informe a rodada atual.", 422)
        round_item = db.scalar(
            select(InterviewRound).where(
                InterviewRound.sessao_id == item.id, InterviewRound.numero == data.rodada
            )
        )
        assert round_item is not None
        if data.acao == "aprofundar":
            if data.rodada >= self.settings.interview_max_rounds:
                raise AppError(
                    "rodadas_esgotadas", "Limite de rodadas atingido. Encerre para confirmar.", 422
                )
            if item.status != State.ANSWERING:
                raise AppError("estado_incompativel", "Sem novas respostas para aprofundar.", 409)
        if item.status == State.FAILED and not data.respostas:
            if data.acao != "encerrar":
                raise AppError("estado_incompativel", "Encerre ou use a rota de retentativas.", 409)
        else:
            ids = [a.pergunta_id for a in data.respostas]
            expected = {UUID(str(q["id"])) for q in round_item.perguntas}
            if len(ids) != len(set(ids)) or set(ids) != expected:
                raise AppError(
                    "respostas_invalidas",
                    "Responda ou pule explicitamente cada pergunta atual.",
                    422,
                )
            if round_item.answered_at:
                raise AppError("rodada_respondida", "A rodada já foi respondida.", 409)
            round_item.respostas = [
                RecordedAnswer(id=uuid4(), **a.model_dump()).model_dump(mode="json")
                for a in data.respostas
            ]
            round_item.complemento_livre = data.complemento_livre
            round_item.complemento_livre_id = uuid4() if data.complemento_livre else None
            round_item.answered_at = utcnow()
            self._candidates(item, round_item)
        if (
            item.status == State.FAILED
            and data.complemento_livre
            and not NEGATIVE.search(data.complemento_livre)
        ):
            round_item.complemento_livre = data.complemento_livre
            round_item.complemento_livre_id = uuid4()
            # Failed rounds have no new answers; only append the spontaneous information.
            item.complementos = item.complementos + [
                Complement(
                    id=uuid4(),
                    texto=data.complemento_livre,
                    resposta_origem_id=round_item.complemento_livre_id,
                ).model_dump(mode="json")
            ]
        round_item.acao_apos_respostas = data.acao
        item.revisao += 1
        item.codigo_erro = None
        item.mensagem_erro = None
        positive = any(
            a.texto and not a.pulada and not a.negativa and not NEGATIVE.search(a.texto)
            for a in data.respostas
        ) or bool(data.complemento_livre and not NEGATIVE.search(data.complemento_livre))
        if data.acao == "aprofundar" and positive:
            self.check_context(db, item)
            self.check_ai(db, user_id)
            item.rodada_atual += 1
            item.status = State.ANALYZING
            next_round = InterviewRound(id=uuid4(), sessao_id=item.id, numero=item.rodada_atual)
            db.add(next_round)
            db.flush()
            self.enqueue_analysis(db, item, next_round)
            return self.finish(db, item, key, fingerprint, "respostas", 202)
        item.status = State.REVIEW
        return self.finish(db, item, key, fingerprint, "respostas")

    def revise(
        self,
        db: Session,
        user_id: UUID,
        interview_id: UUID,
        data: ReviseComplements,
        etag: str | None,
    ) -> InterviewResult:
        lock_user(db, user_id)
        item = self.owned(db, user_id, interview_id)
        self.version(item, etag, (State.REVIEW,))
        self.validate_complements(db, item, data.complementos)
        item.complementos = [c.model_dump(mode="json") for c in data.complementos]
        item.revisao += 1
        return self.finish(db, item)

    def validate_complements(self, db: Session, item: Interview, items: list[Complement]) -> None:
        if len({c.id for c in items}) != len(items):
            raise AppError("ids_duplicados", "IDs de complementos devem ser únicos.", 422)
        if sum(len(c.texto) for c in items) > self.settings.interview_max_confirmed_chars:
            raise AppError(
                "complementos_excessivos",
                "Os complementos excedem o limite total de caracteres.",
                422,
            )
        origins: dict[UUID, str] = {}
        blocked: set[UUID] = set()
        for r in db.scalars(select(InterviewRound).where(InterviewRound.sessao_id == item.id)):
            for raw in r.respostas:
                answer = RecordedAnswer.model_validate(raw)
                origins[answer.id] = answer.texto or ""
                if answer.pulada or answer.negativa or NEGATIVE.search(answer.texto or ""):
                    blocked.add(answer.id)
            if r.complemento_livre_id:
                origins[r.complemento_livre_id] = r.complemento_livre or ""
                if NEGATIVE.search(r.complemento_livre or ""):
                    blocked.add(r.complemento_livre_id)
        remaining_original = item.texto_confirmado_snapshot or ""
        for c in items:
            if c.resposta_origem_id and (
                c.resposta_origem_id not in origins or c.resposta_origem_id in blocked
            ):
                raise AppError(
                    "origem_invalida",
                    "A origem deve ser uma resposta afirmativa desta sessão.",
                    422,
                )
            if NEGATIVE.search(c.texto):
                raise AppError(
                    "complemento_negativo",
                    "Mantenha negativas como lacunas, não como fontes de realizações.",
                    422,
                )
            if c.substitui_trecho_original:
                if c.substitui_trecho_original not in remaining_original:
                    raise AppError(
                        "correcao_invalida",
                        "Correções devem indicar trechos literais sem sobreposição.",
                        422,
                    )
                remaining_original = remaining_original.replace(c.substitui_trecho_original, "\n")

    def confirm(
        self,
        db: Session,
        user_id: UUID,
        interview_id: UUID,
        data: ConfirmComplements,
        etag: str | None,
        key: str | None,
    ) -> InterviewResult:
        lock_user(db, user_id)
        item = self.owned(db, user_id, interview_id)
        fingerprint = self._hash("confirmacao", interview_id, data.model_dump(mode="json"))
        replay = self.replay(db, user_id, key, fingerprint)
        if replay:
            return replay
        self.version(item, etag, (State.REVIEW,))
        self.check_context(db, item)
        if not data.confirmacao_informacoes or not data.revisao_conflitos:
            raise AppError(
                "confirmacao_obrigatoria",
                "Confirme os complementos e a revisão de conflitos com o original.",
                422,
            )
        complements = [Complement.model_validate(c) for c in item.complementos]
        self.validate_complements(db, item, complements)
        conflicts = [Conflict.model_validate(c) for c in item.conflitos]
        resolutions = {r.conflito_id: r for r in data.resolucoes}
        if len(resolutions) != len(data.resolucoes) or set(resolutions) != {
            c.id for c in conflicts
        }:
            raise AppError(
                "conflitos_pendentes", "Resolva explicitamente cada conflito apontado.", 422
            )
        for conflict in conflicts:
            resolution = resolutions[conflict.id]
            if resolution.acao == "manter_original":
                if any(c.resposta_origem_id == conflict.resposta_origem_id for c in complements):
                    raise AppError(
                        "conflito_pendente",
                        "Remova o complemento conflitante para manter o original.",
                        422,
                    )
            elif not any(
                c.id == resolution.complemento_id
                and c.resposta_origem_id == conflict.resposta_origem_id
                and c.substitui_trecho_original == conflict.trecho_original
                for c in complements
            ):
                raise AppError(
                    "correcao_obrigatoria",
                    "O complemento escolhido deve indicar o trecho original substituído.",
                    422,
                )
        item.resolucoes = [r.model_dump(mode="json") for r in data.resolucoes]
        item.status = State.CONFIRMED
        item.confirmado_em = utcnow()
        item.expires_at = None
        item.revisao += 1
        return self.finish(db, item, key, fingerprint, "confirmacao")

    def cancel(self, db: Session, user_id: UUID, interview_id: UUID) -> InterviewResult:
        lock_user(db, user_id)
        item = self.owned(db, user_id, interview_id)
        if item.status == State.CONFIRMED:
            raise AppError(
                "sessao_confirmada", "Uma sessão confirmada não pode ser cancelada.", 409
            )
        if item.status not in (State.CANCELLED, State.EXPIRED):
            self.purge(db, item, State.CANCELLED)
        return self.finish(db, item)

    def retry(
        self, db: Session, user_id: UUID, interview_id: UUID, etag: str | None, key: str | None
    ) -> InterviewResult:
        lock_user(db, user_id)
        item = self.owned(db, user_id, interview_id)
        fingerprint = self._hash("retentativa", interview_id, {})
        replay = self.replay(db, user_id, key, fingerprint)
        if replay:
            return replay
        self.version(item, etag, (State.FAILED,))
        self.check_context(db, item)
        self.check_ai(db, user_id)
        attempt = db.scalar(
            select(Attempt)
            .where(
                Attempt.sessao_complementacao_id == item.id,
                Attempt.tipo_operacao == Operation.ANALYSIS,
                Attempt.rodada_complementacao_id.in_(
                    select(InterviewRound.id).where(
                        InterviewRound.sessao_id == item.id,
                        InterviewRound.numero == item.rodada_atual,
                    )
                ),
            )
            .with_for_update()
        )
        if attempt is None or attempt.status != Status.FAILED:
            raise AppError("analise_indisponivel", "Análise não disponível para retentativa.", 409)
        item.status = State.ANALYZING
        item.revisao += 1
        item.codigo_erro = None
        item.mensagem_erro = None
        attempt.status = Status.PENDING
        attempt.execucoes_ciclo = 0
        attempt.available_at = utcnow()
        attempt.completed_at = None
        attempt.sessao_revisao_esperada = item.revisao
        return self.finish(db, item, key, fingerprint, "retentativa", 202)

    def generation_sources(
        self,
        db: Session,
        user_id: UUID,
        resume_id: UUID,
        interview_id: UUID,
        *,
        validate_context: bool = True,
    ) -> dict[str, object]:
        item = self.owned(db, user_id, interview_id)
        if item.curriculo_id != resume_id:
            raise AppError("sessao_inexistente", "Sessão inexistente para este currículo.", 404)
        if item.status != State.CONFIRMED:
            raise AppError("sessao_nao_confirmada", "Confirme os complementos antes de gerar.", 422)
        if validate_context:
            self.check_context(db, item)
        return {
            "texto": item.texto_confirmado_snapshot,
            "vaga": item.descricao_vaga_snapshot,
            "sessao_complementacao_id": str(item.id),
            "sessao_revisao": item.revisao,
            "complementos": item.complementos,
        }
