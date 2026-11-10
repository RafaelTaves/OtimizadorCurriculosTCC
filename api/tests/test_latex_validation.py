import pytest

from app.service.errors import ProcessingError
from app.service.latex_validation import document_parts
from app.service.proposals import TEMPLATE, ProposalValidator
from tests.conftest import JOB, SOURCE, proposal


def model_latex():
    preamble = TEMPLATE.partition(r"\begin{document}")[0]
    return (
        preamble
        + r"""
\begin{document}
% The model may use the actual template's layout, not the server renderer's bytes.
\begin{center}
{\LARGE \textbf{Ana Silva}}
\end{center}
\section{Resumo}
Projeto acadêmico em \textbf{Python}
\section{Habilidades}
\begin{itemize}
  \item Python
\end{itemize}
\end{document}
"""
    )


def test_accepts_model_layout_without_replacing_its_latex():
    item = proposal()
    item.latex_gerado = model_latex()
    before = item.latex_gerado
    ProposalValidator().validate(item, SOURCE, JOB)
    assert item.latex_gerado == before


@pytest.mark.parametrize(
    "injected",
    [
        r"\input{file}",
        r"\include{file}",
        r"\write18{command}",
        r"\def\a{secret}",
        r"\csname input\endcsname{file}",
        r"\textcolor{white}{secret}",
        r"\begin{verbatim}hidden\end{verbatim}",
        r"^^5cinput{file}",
        r"\href{https://attacker.example}{Ana Silva}",
        r"\vspace{100cm}",
        r"\end{center}",
        r"\item Python",
        r"\section{\input{file}}",
        "{",
        r"\begin{center}",
    ],
)
def test_rejects_unsupported_commands_and_unbalanced_tex(injected):
    item = proposal()
    item.latex_gerado = model_latex().replace(
        r"\end{document}", injected + "\n" + r"\end{document}"
    )
    with pytest.raises(ProcessingError) as caught:
        ProposalValidator().validate(item, SOURCE, JOB)
    assert caught.value.code == "proposta_template_invalido"
    assert caught.value.transient
    assert injected not in caught.value.message


@pytest.mark.parametrize("change", ["omit", "add", "reorder_words", "abbreviate", "heading"])
def test_accepts_model_editorial_choices_without_replacing_latex(change):
    item = proposal()
    latex = model_latex()
    if change == "omit":
        latex = latex.replace("Ana Silva", "")
    elif change == "add":
        latex = latex.replace(r"  \item Python", r"  \item Python aplicado a projetos acadêmicos")
    elif change == "abbreviate":
        latex = latex.replace("Projeto acadêmico em", "Proj. acadêmico em")
    elif change == "heading":
        latex = latex.replace(r"\section{Resumo}", r"\section{Perfil profissional}")
    else:
        latex = latex.replace("Projeto acadêmico em", "Acadêmico projeto em")
    item.latex_gerado = latex
    ProposalValidator().validate(item, SOURCE, JOB)
    assert item.latex_gerado == latex


@pytest.mark.parametrize("change", ["preamble", "trailing", "empty"])
def test_document_must_preserve_technical_structure(change):
    item = proposal()
    latex = model_latex()
    if change == "preamble":
        latex = latex.replace("{article}", "{book}")
    elif change == "trailing":
        latex += "conteúdo escondido"
    else:
        preamble, _ = document_parts(latex)
        latex = preamble + r"\begin{document}\begin{center}\end{center}\end{document}"
    item.latex_gerado = latex
    with pytest.raises(ProcessingError):
        ProposalValidator().validate(item, SOURCE, JOB)


def test_comments_can_be_omitted_without_changing_the_template_commands():
    item = proposal()
    preamble, body = document_parts(model_latex())
    item.latex_gerado = preamble + r"\begin{document}" + body + r"\end{document}"
    ProposalValidator().validate(item, SOURCE, JOB)


def test_repeating_a_supported_field_does_not_invalidate_the_resume():
    item = proposal()
    item.latex_gerado = model_latex().replace(r"  \item Python", r"  \item Python Python")
    ProposalValidator().validate(item, SOURCE, JOB)
