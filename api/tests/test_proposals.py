from datetime import UTC, datetime

import pytest

from app.presentation.schemas import Change, Fact, Gap
from app.service.errors import ProcessingError
from app.service.proposals import ProposalValidator, escape_latex, render_content
from app.service.resumes import month_window
from tests.conftest import JOB, SOURCE, proposal


def test_supported_proposal_and_latex_accents():
    result = proposal()
    ProposalValidator().validate(result, SOURCE, JOB)
    assert "utf8" in result.latex_gerado
    assert escape_latex("João & C# 100% _ $ {x} ~ ^ \\") == (
        r"João \& C\# 100\% \_ \$ \{x\} \textasciitilde{} \textasciicircum{} \textbackslash{}"
    )


@pytest.mark.parametrize("change", ["evidence", "skill", "metric", "preamble", "hidden"])
def test_rejects_unsupported_facts_and_template_changes(change):
    result = proposal()
    if change == "evidence":
        result.curriculo.resumo.trecho_fonte = "gerente na empresa Inventada"
    elif change == "skill":
        result.curriculo.competencias = [Fact(texto="Kubernetes", trecho_fonte="Python")]
        result.latex_gerado = render_content(result.curriculo)
    elif change == "metric":
        result.curriculo.resumo.texto = "Melhorou desempenho em 90%"
        result.latex_gerado = render_content(result.curriculo)
    elif change == "preamble":
        result.latex_gerado = result.latex_gerado.replace("article", "book")
    elif change == "hidden":
        result.latex_gerado += r"\input{/etc/passwd}"
    with pytest.raises(ProcessingError):
        ProposalValidator().validate(result, SOURCE, JOB + " Kubernetes")


def test_month_window_december_leap_year_and_utc():
    assert month_window(datetime(2026, 12, 31, tzinfo=UTC)) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert month_window(datetime(2028, 2, 29, tzinfo=UTC))[1] == datetime(2028, 3, 1, tzinfo=UTC)


@pytest.mark.parametrize(
    "kind,code,field",
    [
        ("evidence", "proposta_sem_evidencia", "curriculo.resumo"),
        ("metric", "proposta_sem_evidencia", "curriculo.resumo"),
        ("template", "proposta_template_invalido", "template"),
        ("change", "proposta_alteracao_invalida", "alteracoes[0]"),
        ("gap", "proposta_lacuna_invalida", "lacunas[0]"),
    ],
)
def test_validation_reports_the_failed_rule_without_disclosing_private_content(kind, code, field):
    result = proposal()
    private = "CONTEUDO_PRIVADO"
    if kind == "evidence":
        result.curriculo.resumo.trecho_fonte = private
    elif kind == "metric":
        result.curriculo.resumo.texto = "Crescimento de 99%"
    elif kind == "template":
        result.latex_gerado += "\n" + private
    elif kind == "change":
        result.alteracoes = [
            Change(
                secao="Resumo",
                antes="Python",
                depois=private,
                justificativa="Teste",
                trecho_fonte="Python",
            )
        ]
    else:
        result.lacunas = [Gap(termo_da_vaga=private, motivo_para_nao_incluir="Teste")]
    with pytest.raises(ProcessingError) as caught:
        ProposalValidator().validate(result, SOURCE, JOB)
    assert caught.value.code == code
    assert field in caught.value.message
    assert private not in caught.value.message
    assert "Revise o texto original" not in caught.value.message
