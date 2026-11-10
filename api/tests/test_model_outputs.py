from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.infrastructure.model_diagnostics import invalid_model_output
from app.infrastructure.openai_optimizer import OpenAIOptimizer
from app.presentation.model_outputs import FirstRoundAnalysis, ModelAnalysis, ModelProposal
from app.service.errors import ProcessingError
from app.service.proposals import ProposalValidator
from tests.conftest import JOB, SOURCE, proposal


def test_provider_schema_has_no_redundant_metadata_and_maps_to_public_contract():
    data = proposal().model_dump(include=set(ModelProposal.model_fields))
    data["alteracoes"] = [
        {
            "secao": "Resumo",
            "antes": None,
            "depois": "Projeto acadêmico em Python",
            "justificativa": "Destacar projeto real",
            "trecho_fonte": "Projeto acadêmico em Python",
            "fonte": "curriculo_original",
        }
    ]
    data["palavras_chave_usadas"] = [
        {
            "termo": "Python",
            "trecho_fonte": "Python",
            "fonte": "curriculo_original",
        }
    ]
    result = ModelProposal.model_validate(data).to_proposal()
    assert result.alteracoes[0].tipo == "reescrita"
    assert result.alteracoes[0].antes == "Projeto acadêmico em Python"
    assert result.palavras_chave_usadas[0].evidencia_no_original == "Python"
    assert result.palavras_chave_usadas[0].trecho_fonte == "Python"
    ProposalValidator().validate(result, SOURCE, JOB)


def test_confirmed_complement_metadata_still_identifies_its_own_source():
    data = proposal().model_dump(include=set(ModelProposal.model_fields))
    source = "complemento:" + str(uuid4())
    data["alteracoes"] = [
        {
            "secao": "Resumo",
            "antes": None,
            "depois": "Projeto acadêmico em Python",
            "justificativa": "Informação confirmada",
            "trecho_fonte": "Projeto acadêmico em Python",
            "fonte": source,
        }
    ]
    data["palavras_chave_usadas"] = [
        {
            "termo": "Python",
            "trecho_fonte": "Python",
            "fonte": source,
        }
    ]
    result = ModelProposal.model_validate(data).to_proposal()
    assert result.alteracoes[0].tipo == "inclusao"
    assert result.alteracoes[0].antes is None
    assert result.palavras_chave_usadas[0].evidencia_no_original is None
    ProposalValidator().validate(
        result,
        {
            "curriculo_original": SOURCE,
            source: "Projeto acadêmico em Python",
        },
        JOB,
    )


def test_first_round_cannot_reference_answers_that_do_not_exist():
    data = {
        "perguntas": [
            {
                "pergunta": "Qual sua participação no projeto?",
                "justificativa": "Esclarecer contribuição individual",
                "categoria": "projeto",
                "termo_da_vaga": None,
                "resposta_origem_id": str(uuid4()),
            }
        ],
        "conflitos": [],
    }
    with pytest.raises(ValidationError):
        FirstRoundAnalysis.model_validate(data)
    data["perguntas"][0]["resposta_origem_id"] = None
    result = FirstRoundAnalysis.model_validate(data).to_analysis()
    assert result.pronta_para_confirmacao is False
    assert result.perguntas[0].resposta_origem_id is None
    assert ModelAnalysis(perguntas=[], conflitos=[]).to_analysis().pronta_para_confirmacao


def test_schema_failure_is_retryable_and_never_logs_provider_values(settings, caplog):
    data = proposal().model_dump(include=set(ModelProposal.model_fields))
    data["latex_gerado"] = {"SECRET_PRIVATE_CV": "private@example.com"}
    with pytest.raises(ValidationError) as invalid:
        ModelProposal.model_validate(data)
    with patch("app.infrastructure.openai_optimizer.OpenAI") as factory:
        factory.return_value.__enter__.return_value.responses.parse.side_effect = invalid.value
        with pytest.raises(ProcessingError) as caught:
            OpenAIOptimizer(settings).optimize(SOURCE, JOB)
    assert caught.value.transient
    assert "latex_gerado" in caught.value.message
    assert "SECRET_PRIVATE_CV" not in caplog.text + caught.value.message
    assert "private@example.com" not in caplog.text + caught.value.message
    data["latex_gerado"] = proposal().latex_gerado
    data["private@example.com"] = "secret"
    with pytest.raises(ValidationError) as invalid:
        ModelProposal.model_validate(data)
    assert (
        "private@example.com"
        not in invalid_model_output(invalid.value, "resposta_invalida").message
    )
