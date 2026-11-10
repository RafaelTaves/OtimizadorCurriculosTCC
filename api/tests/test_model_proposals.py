"""Regression fixtures: synthetic content, SQLite and a simulated OpenAI response."""

import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import pytest

from app.infrastructure.models import Attempt, utcnow
from app.infrastructure.openai_optimizer import OpenAIOptimizer
from app.presentation.model_outputs import ModelKeyword, ModelProposal
from app.presentation.schemas import Fact
from tests.conftest import enqueue, proposal, upload_confirm


def test_model_keywords_are_preserved_without_literal_validation(client, auth, worker, settings):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    content = ModelProposal.model_validate(
        proposal().model_dump(include=set(ModelProposal.model_fields))
    )
    content.palavras_chave_usadas = [
        ModelKeyword(termo="Python", trecho_fonte="Python", fonte="curriculo_original")
        for _ in range(5)
    ] + [
        ModelKeyword(
            termo="Desenvolvimento backend",
            trecho_fonte="Construção de APIs para sistemas de biblioteca",
            fonte="curriculo_original",
        )
    ]
    worker.optimizer = OpenAIOptimizer(settings)
    with patch("app.infrastructure.openai_optimizer.OpenAI") as factory:
        parse = factory.return_value.__enter__.return_value.responses.parse
        parse.return_value = SimpleNamespace(
            status="completed",
            output_parsed=content,
            model="fake-model",
            usage=SimpleNamespace(input_tokens=100, output_tokens=200),
        )
        assert worker.run_once()
        assert parse.call_count == 1
        assert not worker.run_once()
    state = client.get(queued.headers["location"], headers=auth).json()
    assert state["status"] == "aguardando_revisao"
    assert state["codigo_erro"] is None
    assert state["curriculo_gerado_id"] is not None
    assert state["proposta"]["palavras_chave_usadas"] == [
        {**keyword.model_dump(), "evidencia_no_original": keyword.trecho_fonte}
        for keyword in content.palavras_chave_usadas
    ]
    assert state["proposta"]["latex_gerado"] == content.latex_gerado.strip()
    assert state["tokens_entrada"] == 100
    assert state["tokens_saida"] == 200
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1


@pytest.mark.parametrize("unsupported_fact", [False, True])
@pytest.mark.parametrize("latex_variant", ["original", "rewritten", "omitted"])
def test_worker_publishes_model_latex_only_after_evidence_validation(
    client, auth, worker, settings, database, unsupported_fact, latex_variant
):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    assert queued.status_code == 202
    content = ModelProposal.model_validate(
        proposal().model_dump(include=set(ModelProposal.model_fields))
    )
    if latex_variant == "rewritten":
        content.latex_gerado = content.latex_gerado.replace(
            "Projeto acadêmico em Python", "Desenvolvimento acadêmico usando Python"
        )
    elif latex_variant == "omitted":
        content.latex_gerado = content.latex_gerado.replace("Projeto acadêmico em Python", "")
    if unsupported_fact:
        content.curriculo.competencias = [Fact(texto="Kubernetes", trecho_fonte="Python")]
    worker.optimizer = OpenAIOptimizer(settings)
    with patch("app.infrastructure.openai_optimizer.OpenAI") as factory:
        factory.return_value.__enter__.return_value.responses.parse.return_value = SimpleNamespace(
            status="completed",
            output_parsed=content,
            model="fake-model",
            usage=SimpleNamespace(input_tokens=100, output_tokens=200),
        )
        assert worker.run_once()
        if unsupported_fact:
            for _ in range(settings.worker_max_executions - 1):
                with database.sessions.begin() as db:
                    attempt = db.get(Attempt, UUID(queued.json()["id"]))
                    attempt.available_at = utcnow() - timedelta(seconds=1)
                assert worker.run_once()
        else:
            assert factory.return_value.__enter__.return_value.responses.parse.call_count == 1
            assert not worker.run_once()
    response = client.get(queued.headers["location"], headers=auth)
    assert response.status_code == 200
    attempt = response.json()
    if unsupported_fact:
        assert attempt["status"] == "falhou"
        assert attempt["codigo_erro"] == "proposta_sem_evidencia"
        assert "curriculo.competencias[0]" in attempt["mensagem_erro"]
        assert attempt["curriculo_gerado_id"] is None
        assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
    else:
        assert attempt["status"] == "aguardando_revisao"
        assert attempt["codigo_erro"] is None
        assert attempt["proposta"]["latex_gerado"] == content.latex_gerado.strip()
        generated = client.get(
            f"/v1/curriculos/{attempt['curriculo_gerado_id']}", headers=auth
        ).json()
        assert generated["latex_gerado"] == content.latex_gerado.strip()
        assert attempt["proposta"]["versao_schema"] == 2
        assert client.get("/v1/uso", headers=auth).json()["usado"] == 1


def test_validation_failure_retries_same_attempt_with_feedback_then_succeeds(
    client, auth, worker, settings, database
):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    good = ModelProposal.model_validate(
        proposal().model_dump(include=set(ModelProposal.model_fields))
    )
    bad = good.model_copy(deep=True)
    bad.latex_gerado += r"\input{private}"
    worker.optimizer = OpenAIOptimizer(settings)
    with patch("app.infrastructure.openai_optimizer.OpenAI") as factory:
        parse = factory.return_value.__enter__.return_value.responses.parse
        parse.side_effect = [
            SimpleNamespace(status="completed", output_parsed=item, model="fake", usage=None)
            for item in (bad, good)
        ]
        assert worker.run_once()
        state = client.get(queued.headers["location"], headers=auth).json()
        assert state["status"] == "pendente"
        assert state["etapa"] == "nova_execucao"
        assert state["curriculo_gerado_id"] is None
        with database.sessions.begin() as db:
            attempt = db.get(Attempt, UUID(state["id"]))
            attempt.available_at = utcnow() - timedelta(seconds=1)
        assert worker.run_once()
        inputs = [json.loads(call.kwargs["input"]) for call in parse.call_args_list]
    assert inputs[0]["correcao_anterior"] is None
    assert "fim de documento" in inputs[1]["correcao_anterior"]
    state = client.get(queued.headers["location"], headers=auth).json()
    assert state["id"] == queued.json()["id"]
    assert state["status"] == "aguardando_revisao"
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
