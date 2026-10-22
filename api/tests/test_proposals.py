from datetime import UTC, datetime

import pytest

from app.presentation.schemas import Fact, Keyword
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


@pytest.mark.parametrize("change", ["evidence", "skill", "metric", "preamble", "hidden", "keyword"])
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
    else:
        result.palavras_chave_usadas = [Keyword(termo="Kubernetes", evidencia_no_original="Python")]
    with pytest.raises(ProcessingError):
        ProposalValidator().validate(result, SOURCE, JOB + " Kubernetes")


def test_month_window_december_leap_year_and_utc():
    assert month_window(datetime(2026, 12, 31, tzinfo=UTC)) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert month_window(datetime(2028, 2, 29, tzinfo=UTC))[1] == datetime(2028, 3, 1, tzinfo=UTC)
