"""Synthetic interview fixtures; no real provider calls or private CVs."""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.infrastructure.models import (
    Attempt,
    IdempotencyRecord,
    Interview,
    InterviewRound,
    Operation,
    utcnow,
)
from app.infrastructure.openai_interviewer import OpenAIInterviewAnalyzer
from app.presentation.interviews import AnalysisConflict, AnalysisQuestion, InterviewAnalysis
from app.presentation.model_outputs import FirstRoundAnalysis
from app.presentation.schemas import Change, Entry, Fact, Keyword, SourceRecord
from app.service.errors import ProcessingError
from app.service.ports import AnalysisResult, ModelResult
from app.service.proposals import ProposalValidator, confirmed_sources, render_content
from tests.conftest import JOB, SOURCE, docx_bytes, proposal, register, upload_confirm


class FakeAnalyzer:
    def __init__(self):
        self.calls = []

    def analyze(self, context):
        self.calls.append(context)
        if context["rodada"] == 1:
            analysis = InterviewAnalysis(
                perguntas=[
                    AnalysisQuestion(
                        pergunta="Você tem algum projeto de API que deseja detalhar?",
                        justificativa="A vaga pede API e sua contribuição pode ser esclarecida.",
                        categoria="projeto",
                        termo_da_vaga="API",
                    )
                ],
                pronta_para_confirmacao=False,
            )
        else:
            analysis = InterviewAnalysis(perguntas=[], pronta_para_confirmacao=True)
        return AnalysisResult(analysis, "fake-interview", 50, 70)


@pytest.fixture
def interview_setup(client, auth, worker):
    original = upload_confirm(client, auth)
    worker.interviews.analyzer = FakeAnalyzer()
    return original


def start(client, auth, original, key="interview-start"):
    return client.post(
        f"/v1/curriculos/{original}/complementacoes",
        headers={**auth, "Idempotency-Key": key},
        json={"consentimento_envio_openai": True},
    )


def current(client, auth, identifier):
    result = client.get(f"/v1/complementacoes/{identifier}", headers=auth)
    assert result.status_code == 200, result.text
    return result


def answer(
    client,
    auth,
    view,
    text="Projeto de biblioteca com FastAPI e PostgreSQL.",
    action="encerrar",
    key="answer-1",
    skip=False,
):
    questions = view.json()["rodadas"][-1]["perguntas"]
    return client.post(
        f"/v1/complementacoes/{view.json()['id']}/respostas",
        headers={**auth, "If-Match": view.headers["etag"], "Idempotency-Key": key},
        json={
            "rodada": view.json()["rodada_atual"],
            "respostas": [
                {"pergunta_id": q["id"], "texto": None if skip else text, "pulada": skip}
                for q in questions
            ],
            "acao": action,
        },
    )


def confirm(client, auth, view, key="confirm-1", resolutions=None):
    return client.post(
        f"/v1/complementacoes/{view.json()['id']}/confirmacao",
        headers={**auth, "If-Match": view.headers["etag"], "Idempotency-Key": key},
        json={
            "confirmacao_informacoes": True,
            "revisao_conflitos": True,
            "resolucoes": resolutions or [],
        },
    )


def prepared(client, auth, worker, original):
    created = start(client, auth, original)
    assert created.status_code == 202, created.text
    assert worker.run_once()
    state = current(client, auth, created.json()["id"])
    assert state.json()["status"] == "aguardando_respostas", state.text
    return state


def generate(client, auth, original, identifier, key="generate-with-interview"):
    return client.post(
        f"/v1/curriculos/{original}/otimizacoes",
        headers={**auth, "Idempotency-Key": key},
        json={"consentimento_envio_openai": True, "sessao_complementacao_id": identifier},
    )


def test_full_interview_confirmed_project_enters_generation(
    client, auth, worker, database, interview_setup
):
    state = prepared(client, auth, worker, interview_setup)
    assert generate(client, auth, interview_setup, state.json()["id"]).status_code == 422
    reviewed = answer(client, auth, state)
    assert reviewed.status_code == 200, reviewed.text
    assert (
        reviewed.json()["complementos"][0]["texto"]
        == "Projeto de biblioteca com FastAPI e PostgreSQL."
    )
    confirmed = confirm(client, auth, reviewed)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmada"

    class SourceAwareOptimizer:
        def optimize(self, text, job, *, sources=None, feedback=None):
            assert text == SOURCE
            key = next(key for key in sources if key.startswith("complemento:"))
            result = proposal()
            fact = Fact(
                texto="Projeto de biblioteca com FastAPI", trecho_fonte=sources[key], fonte=key
            )
            result.curriculo.projetos = [
                Entry(titulo=fact, instituicao=None, periodo=None, itens=[])
            ]
            result.alteracoes = [
                Change(
                    secao="Projetos",
                    antes=None,
                    depois=fact.texto,
                    justificativa="Inclusão confirmada",
                    trecho_fonte=fact.trecho_fonte,
                    fonte=key,
                    tipo="inclusao",
                )
            ]
            result.palavras_chave_usadas = [
                Keyword(termo="PostgreSQL", trecho_fonte=sources[key], fonte=key)
            ]
            # Include the keyword in the actual proposed CV as well.
            result.curriculo.competencias.append(
                Fact(texto="PostgreSQL", trecho_fonte=sources[key], fonte=key)
            )
            result.latex_gerado = render_content(result.curriculo)
            return ModelResult(result, "fake-model", 10, 20)

    worker.optimizer = SourceAwareOptimizer()
    queued = generate(client, auth, interview_setup, state.json()["id"])
    assert queued.status_code == 202, queued.text
    assert worker.run_once()
    result = client.get(queued.headers["location"], headers=auth)
    assert result.json()["status"] == "aguardando_revisao", result.text
    assert result.json()["proposta"]["versao_schema"] == 2
    assert (
        result.json()["proposta"]["fontes_confirmadas"][0]["id"]
        == confirmed.json()["complementos"][0]["id"]
    )
    assert "FastAPI" in result.json()["proposta"]["latex_gerado"]
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
    assert (
        client.get(f"/v1/curriculos/{interview_setup}", headers=auth).json()["texto_extraido"]
        == SOURCE
    )
    duplicate = generate(client, auth, interview_setup, state.json()["id"])
    assert duplicate.status_code == 202 and duplicate.json()["id"] == queued.json()["id"]
    assert (
        generate(
            client, auth, interview_setup, state.json()["id"], "different-generation"
        ).status_code
        == 409
    )
    assert (
        client.get(f"/v1/curriculos/{interview_setup}/complementacoes", headers=auth).json()[
            "total"
        ]
        == 1
    )


def test_two_rounds_then_review_and_budget_is_separate(
    client, auth, worker, database, interview_setup
):
    first = prepared(client, auth, worker, interview_setup)
    second = answer(client, auth, first, action="aprofundar")
    assert second.status_code == 202, second.text
    assert worker.run_once()
    state = current(client, auth, first.json()["id"])
    assert state.json()["status"] == "aguardando_confirmacao"
    assert state.json()["rodada_atual"] == 2
    assert len(worker.interviews.analyzer.calls[1]["historico"][0]["respostas"]) == 1
    assert answer(client, auth, state, action="aprofundar", key="too-many").status_code == 422
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
    with database.sessions() as db:
        attempts = list(db.scalars(select(Attempt)))
        assert sum(a.executions for a in attempts) == 2
        assert all(a.tipo_operacao == Operation.ANALYSIS for a in attempts)


def test_idempotency_result_replays_after_revision_advances(client, auth, worker, interview_setup):
    initial = start(client, auth, interview_setup)
    worker.run_once()
    replay = start(client, auth, interview_setup)
    assert replay.json() == initial.json()
    state = current(client, auth, initial.json()["id"])
    reviewed = answer(client, auth, state)
    confirmed = confirm(client, auth, reviewed)
    assert confirmed.status_code == 200
    replay_answer = answer(client, auth, state)
    assert replay_answer.status_code == 200
    assert replay_answer.json() == reviewed.json()
    changed = answer(client, auth, state, text="Outro conteúdo.")
    assert changed.status_code == 409
    replay_confirmation = confirm(client, auth, reviewed)
    assert replay_confirmation.json() == confirmed.json()


def test_consent_and_confirmed_text_are_required(client, auth, worker, database, interview_setup):
    denied = client.post(
        f"/v1/curriculos/{interview_setup}/complementacoes",
        headers={**auth, "Idempotency-Key": "no-consent"},
        json={"consentimento_envio_openai": False},
    )
    assert denied.status_code == 422
    upload = client.post(
        "/v1/curriculos",
        headers=auth,
        files={"arquivo": ("base.docx", docx_bytes())},
        data={"descricao_vaga": JOB},
    )
    assert start(client, auth, upload.json()["id"]).status_code == 422
    assert not worker.run_once()
    with database.sessions() as db:
        assert not list(db.scalars(select(Interview)))


def test_partial_answers_must_skip_and_negative_not_used(client, auth, worker, interview_setup):
    state = prepared(client, auth, worker, interview_setup)
    invalid = client.post(
        f"/v1/complementacoes/{state.json()['id']}/respostas",
        headers={**auth, "If-Match": state.headers["etag"], "Idempotency-Key": "incomplete"},
        json={"rodada": 1, "respostas": [], "acao": "encerrar"},
    )
    assert invalid.status_code == 422
    negative = answer(client, auth, state, text="Não tenho projetos nessa área.")
    assert negative.status_code == 200, negative.text
    assert negative.json()["complementos"] == []
    assert confirm(client, auth, negative).status_code == 200


def test_skip_all_is_allowed_without_fabricating_projects(client, auth, worker, interview_setup):
    state = prepared(client, auth, worker, interview_setup)
    reviewed = answer(client, auth, state, skip=True)
    assert reviewed.status_code == 200
    assert reviewed.json()["complementos"] == []


def test_no_questions_allows_spontaneous_complement(client, auth, worker, interview_setup):
    class ReadyAnalyzer:
        def analyze(self, context):
            return AnalysisResult(
                InterviewAnalysis(perguntas=[], pronta_para_confirmacao=True), "fake", 1, 1
            )

    worker.interviews.analyzer = ReadyAnalyzer()
    created = start(client, auth, interview_setup)
    worker.run_once()
    state = current(client, auth, created.json()["id"])
    result = client.post(
        f"/v1/complementacoes/{state.json()['id']}/respostas",
        headers={**auth, "If-Match": state.headers["etag"], "Idempotency-Key": "free"},
        json={
            "rodada": 1,
            "respostas": [],
            "complemento_livre": "Participei de uma atividade voluntária.",
            "acao": "encerrar",
        },
    )
    assert result.status_code == 200, result.text
    assert len(result.json()["complementos"]) == 1


def test_etag_cross_user_and_frozen_confirmation(client, auth, worker, interview_setup):
    state = prepared(client, auth, worker, interview_setup)
    other = register(client, "another")
    url = f"/v1/complementacoes/{state.json()['id']}"
    assert client.get(url, headers=other).status_code == 404
    assert client.post(url + "/cancelamento", headers=other).status_code == 404
    assert (
        client.get(f"/v1/curriculos/{interview_setup}/complementacoes", headers=other).status_code
        == 404
    )
    reviewed = answer(client, auth, state)
    missing = client.put(url + "/complementos", headers=auth, json={"complementos": []})
    assert missing.status_code == 428
    old = client.put(
        url + "/complementos",
        headers={**auth, "If-Match": state.headers["etag"]},
        json={"complementos": []},
    )
    assert old.status_code == 412
    confirmed = confirm(client, auth, reviewed)
    assert confirmed.status_code == 200
    frozen = client.put(
        url + "/complementos",
        headers={**auth, "If-Match": confirmed.headers["etag"]},
        json={"complementos": []},
    )
    assert frozen.status_code == 409


def test_original_change_conflicts_with_confirmation_and_generation(
    client, auth, worker, database, interview_setup
):
    state = prepared(client, auth, worker, interview_setup)
    reviewed = answer(client, auth, state)
    client.patch(
        f"/v1/curriculos/{interview_setup}/texto-extraido",
        headers=auth,
        json={"texto": SOURCE + " Outra informação confirmada."},
    )
    assert confirm(client, auth, reviewed).status_code == 409
    with database.sessions() as db:
        assert db.get(Interview, UUID(state.json()["id"])).texto_confirmado_snapshot == SOURCE


def test_cancel_and_expire_discard_late_results_and_purge(
    client, auth, worker, database, interview_setup
):
    created = start(client, auth, interview_setup)
    claim = worker.claim()
    assert claim is not None
    cancelled = client.post(
        f"/v1/complementacoes/{created.json()['id']}/cancelamento", headers=auth
    )
    assert cancelled.json()["status"] == "cancelada"
    worker.interviews.execute(claim)
    assert (
        client.post(f"/v1/complementacoes/{created.json()['id']}/cancelamento", headers=auth).json()
        == cancelled.json()
    )
    second = start(client, auth, interview_setup, "second")
    with database.sessions.begin() as db:
        item = db.get(Interview, UUID(second.json()["id"]))
        item.expires_at = utcnow() - timedelta(seconds=1)
    worker.cleanup()
    state = current(client, auth, second.json()["id"])
    assert state.json()["status"] == "expirada"
    with database.sessions() as db:
        item = db.get(Interview, UUID(second.json()["id"]))
        assert item.texto_confirmado_snapshot is None and item.complementos == []
        assert all(record.resposta is None for record in db.scalars(select(IdempotencyRecord)))


def test_fail_retry_recovery_and_daily_execution_budget(
    client, auth, worker, settings, database, interview_setup
):
    settings.interview_executions_per_day = 2

    class FailingAnalyzer:
        def analyze(self, context):
            raise ProcessingError("provider_down", "Indisponível", transient=True)

    worker.interviews.analyzer = FailingAnalyzer()
    created = start(client, auth, interview_setup)
    assert worker.run_once()
    with database.sessions.begin() as db:
        attempt = db.scalar(select(Attempt))
        attempt.available_at = utcnow() - timedelta(seconds=1)
    assert worker.run_once()
    state = current(client, auth, created.json()["id"])
    assert state.json()["status"] == "falhou", state.text
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
    retry = client.post(
        f"/v1/complementacoes/{state.json()['id']}/retentativas",
        headers={**auth, "If-Match": state.headers["etag"], "Idempotency-Key": "manual-retry"},
    )
    assert retry.status_code == 429
    ended = answer(client, auth, state, key="end-failed")
    assert ended.status_code == 200, ended.text
    assert ended.json()["status"] == "aguardando_confirmacao"


def test_daily_session_limit_survives_cancellation(client, auth, worker, interview_setup):
    for i in range(3):
        created = start(client, auth, interview_setup, f"session-{i}")
        assert created.status_code == 202
        client.post(f"/v1/complementacoes/{created.json()['id']}/cancelamento", headers=auth)
    assert start(client, auth, interview_setup, "fourth").status_code == 429


def test_deletion_removes_interview_contents_keeps_technical_counters(
    client, auth, worker, database, interview_setup
):
    state = prepared(client, auth, worker, interview_setup)
    answer(client, auth, state)
    deleted = client.delete(f"/v1/curriculos/{interview_setup}", headers=auth)
    assert deleted.status_code == 204, deleted.text
    with database.sessions() as db:
        assert not list(db.scalars(select(Interview)))
        assert not list(db.scalars(select(InterviewRound)))
        record = db.scalar(select(IdempotencyRecord))
        assert record.sessao_id is None and record.resposta is None
        attempt = db.scalar(select(Attempt))
        assert attempt.sessao_complementacao_id is None and attempt.curriculo_id is None
        assert len(attempt.execucoes_analise) == 1


def test_evidence_sources_cannot_be_mixed_or_use_corrected_original():
    identifier = uuid4()
    complement = SourceRecord(
        id=identifier, texto="Projeto em 2025", substitui_trecho_original="Projeto em 2024"
    )
    sources = confirmed_sources("Ana Silva\nProjeto em 2024", [complement])
    assert "2024" not in sources["curriculo_original"]
    result = proposal()
    result.curriculo.resumo = Fact(
        texto="Projeto em 2025", trecho_fonte="Projeto em 2025", fonte="curriculo_original"
    )
    result.latex_gerado = render_content(result.curriculo)
    with pytest.raises(ProcessingError):
        ProposalValidator().validate(result, sources, JOB)
    result.curriculo.resumo.fonte = f"complemento:{identifier}"
    result.curriculo.competencias = []
    result.latex_gerado = render_content(result.curriculo)
    ProposalValidator().validate(result, sources, JOB)


def test_only_negative_or_skipped_answers_do_not_enqueue_more_analysis(
    client, auth, worker, database, interview_setup
):
    state = prepared(client, auth, worker, interview_setup)
    result = answer(client, auth, state, action="aprofundar", skip=True)
    assert result.status_code == 200, result.text
    assert result.json()["status"] == "aguardando_confirmacao"
    assert not worker.run_once()
    with database.sessions() as db:
        assert len(list(db.scalars(select(Attempt)))) == 1


def test_lease_recovery_counts_execution_and_discards_old_result(
    client, auth, worker, database, interview_setup
):
    created = start(client, auth, interview_setup)
    first = worker.claim()
    assert first is not None
    with database.sessions.begin() as db:
        db.get(Attempt, first.id).lease_until = utcnow() - timedelta(seconds=1)
    second = worker.claim()
    assert second is not None and second.id == first.id
    assert first.lease_token != second.lease_token
    worker.interviews.execute(first)
    assert worker.interviews.analyzer.calls == []
    worker.interviews.execute(second)
    assert current(client, auth, created.json()["id"]).json()["status"] == "aguardando_respostas"
    with database.sessions() as db:
        assert len(db.get(Attempt, first.id).execucoes_analise) == 2


def test_manual_retry_reuses_attempt_and_original_response(
    client, auth, worker, database, interview_setup
):
    class InvalidAnalyzer:
        def analyze(self, context):
            raise ProcessingError("analise_invalida", "Análise inválida.")

    worker.interviews.analyzer = InvalidAnalyzer()
    created = start(client, auth, interview_setup)
    worker.run_once()
    state = current(client, auth, created.json()["id"])
    headers = {**auth, "If-Match": state.headers["etag"], "Idempotency-Key": "retry"}
    url = f"/v1/complementacoes/{created.json()['id']}/retentativas"
    retried = client.post(url, headers=headers)
    assert retried.status_code == 202, retried.text
    assert retried.json()["tentativa_id"] == created.json()["tentativa_id"]
    worker.interviews.analyzer = FakeAnalyzer()
    worker.run_once()
    assert client.post(url, headers=headers).json() == retried.json()
    with database.sessions() as db:
        assert len(list(db.scalars(select(Attempt)))) == 1
        assert len(db.get(Attempt, UUID(created.json()["tentativa_id"])).execucoes_analise) == 2


def test_conflicting_answer_requires_explicit_correction(client, auth, worker, interview_setup):
    class ConflictAnalyzer(FakeAnalyzer):
        def analyze(self, context):
            if context["rodada"] == 1:
                return super().analyze(context)
            answer_id = context["historico"][0]["respostas"][0]["id"]
            return AnalysisResult(
                InterviewAnalysis(
                    perguntas=[],
                    pronta_para_confirmacao=True,
                    conflitos=[
                        AnalysisConflict(
                            resposta_origem_id=answer_id,
                            trecho_original="Projeto acadêmico em Python e PostgreSQL em 2024.",
                            trecho_resposta="O projeto ocorreu em 2025.",
                            descricao="Confirme o ano do projeto.",
                        )
                    ],
                ),
                "fake",
                1,
                1,
            )

    worker.interviews.analyzer = ConflictAnalyzer()
    state = prepared(client, auth, worker, interview_setup)
    assert (
        answer(
            client, auth, state, text="O projeto ocorreu em 2025.", action="aprofundar"
        ).status_code
        == 202
    )
    worker.run_once()
    review = current(client, auth, state.json()["id"])
    conflict = review.json()["conflitos"][0]
    assert confirm(client, auth, review).status_code == 422
    complement = review.json()["complementos"][0]
    resolutions = [
        {
            "conflito_id": conflict["id"],
            "acao": "usar_complemento",
            "complemento_id": complement["id"],
        }
    ]
    assert confirm(client, auth, review, resolutions=resolutions).status_code == 422
    complement["substitui_trecho_original"] = conflict["trecho_original"]
    revised = client.put(
        f"/v1/complementacoes/{state.json()['id']}/complementos",
        headers={**auth, "If-Match": review.headers["etag"]},
        json={"complementos": [complement]},
    )
    assert revised.status_code == 200, revised.text
    assert confirm(client, auth, revised, resolutions=resolutions).status_code == 200


def test_expired_replay_cannot_restore_purged_private_content(
    client, auth, worker, database, interview_setup
):
    created = start(client, auth, interview_setup)
    worker.run_once()
    with database.sessions.begin() as db:
        db.get(Interview, UUID(created.json()["id"])).expires_at = utcnow() - timedelta(seconds=1)
    assert start(client, auth, interview_setup).status_code == 410
    with database.sessions() as db:
        assert db.get(Interview, UUID(created.json()["id"])).texto_confirmado_snapshot is None


def test_changed_original_after_confirmation_blocks_new_generation(
    client, auth, worker, interview_setup
):
    state = prepared(client, auth, worker, interview_setup)
    assert confirm(client, auth, answer(client, auth, state)).status_code == 200
    client.patch(
        f"/v1/curriculos/{interview_setup}/texto-extraido",
        headers=auth,
        json={"texto": SOURCE + " Mais detalhes."},
    )
    assert generate(client, auth, interview_setup, state.json()["id"]).status_code == 409


@pytest.mark.parametrize("problem", ["repeated", "new_topic", "foreign_origin", "false_conflict"])
def test_analysis_rejects_repeated_questions_and_untrusted_references(worker, problem):
    question_id, answer_id = uuid4(), uuid4()
    context = {
        "curriculo_confirmado": SOURCE,
        "descricao_vaga": JOB,
        "rodada": 2,
        "historico": [
            {
                "perguntas": [
                    {
                        "id": str(question_id),
                        "pergunta": "Qual sua participação na API?",
                        "justificativa": "Esclarecer contribuição",
                        "categoria": "projeto",
                        "termo_da_vaga": "API",
                    }
                ],
                "respostas": [
                    {
                        "id": str(answer_id),
                        "pergunta_id": str(question_id),
                        "texto": "Implementei endpoints.",
                        "pulada": False,
                    }
                ],
            }
        ],
    }
    data = {
        "pergunta": "Como funcionavam esses endpoints?",
        "justificativa": "Esclarecer trabalho real",
        "categoria": "projeto",
        "resposta_origem_id": answer_id,
        "termo_da_vaga": "API",
    }
    if problem == "repeated":
        data["pergunta"] = "QUAL SUA PARTICIPAÇÃO NA API?"
    elif problem == "new_topic":
        data["termo_da_vaga"] = "Kubernetes"
    elif problem == "foreign_origin":
        data["resposta_origem_id"] = uuid4()
    conflicts = []
    if problem == "false_conflict":
        conflicts = [
            AnalysisConflict(
                resposta_origem_id=answer_id,
                trecho_original="Inventado no original",
                trecho_resposta="Implementei endpoints.",
                descricao="Sem suporte",
            )
        ]
    analysis = InterviewAnalysis(
        perguntas=[AnalysisQuestion(**data)], pronta_para_confirmacao=False, conflitos=conflicts
    )
    with pytest.raises(ProcessingError) as caught:
        worker.interviews.validate(analysis, context)
    assert caught.value.code == "analise_invalida"


def test_revising_complements_enforces_total_and_nonoverlapping_corrections(
    client, auth, worker, interview_setup
):
    state = prepared(client, auth, worker, interview_setup)
    review = answer(client, auth, state)
    url = f"/v1/complementacoes/{state.json()['id']}/complementos"
    headers = {**auth, "If-Match": review.headers["etag"]}
    excess = [{"id": str(uuid4()), "texto": "x" * 7000} for _ in range(2)]
    result = client.put(url, headers=headers, json={"complementos": excess})
    assert result.status_code == 422
    assert result.json()["erro"]["codigo"] == "complementos_excessivos"
    overlapping = [
        {"id": str(uuid4()), "texto": "Em 2025", "substitui_trecho_original": text}
        for text in ("PostgreSQL em 2024", "em 2024")
    ]
    result = client.put(url, headers=headers, json={"complementos": overlapping})
    assert result.status_code == 422
    assert result.json()["erro"]["codigo"] == "correcao_invalida"


def test_model_analysis_is_corrected_in_same_attempt_with_budget_and_feedback(
    client, auth, worker, settings, database, interview_setup
):
    worker.interviews.analyzer = OpenAIInterviewAnalyzer(settings)
    created = start(client, auth, interview_setup)
    bad = FirstRoundAnalysis.model_validate(
        {
            "perguntas": [
                {
                    "pergunta": "Qual foi sua contribuição individual no projeto?",
                    "justificativa": "Esclarecer participação",
                    "categoria": "projeto",
                    "termo_da_vaga": "desenvolvimento de aplicações",
                    "resposta_origem_id": None,
                }
            ],
            "conflitos": [],
        }
    )
    good = bad.model_copy(deep=True)
    good.perguntas[0].termo_da_vaga = "API"
    with patch("app.infrastructure.openai_interviewer.OpenAI") as factory:
        parse = factory.return_value.__enter__.return_value.responses.parse
        parse.side_effect = [
            SimpleNamespace(
                status="completed",
                output_parsed=item,
                model="fake",
                usage=SimpleNamespace(input_tokens=10, output_tokens=20),
            )
            for item in (bad, good)
        ]
        assert worker.run_once()
        state = current(client, auth, created.json()["id"])
        assert state.json()["status"] == "analisando"
        with database.sessions.begin() as db:
            attempt = db.scalar(select(Attempt))
            identifier = attempt.id
            assert attempt.execucoes_ciclo == 1
            assert len(attempt.execucoes_analise) == 1
            attempt.available_at = utcnow() - timedelta(seconds=1)
        assert worker.run_once()
        inputs = [json.loads(call.kwargs["input"]) for call in parse.call_args_list]
    assert inputs[0]["correcao_anterior"] is None
    assert "trecho literal" in inputs[1]["correcao_anterior"]
    state = current(client, auth, created.json()["id"])
    assert state.json()["status"] == "aguardando_respostas"
    with database.sessions() as db:
        attempt = db.get(Attempt, identifier)
        assert attempt.execucoes_ciclo == 2
        assert len(attempt.execucoes_analise) == 2
        assert attempt.tokens_entrada == 20
        assert attempt.tokens_saida == 40
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
