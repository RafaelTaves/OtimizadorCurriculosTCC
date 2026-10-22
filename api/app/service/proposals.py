import re
from pathlib import Path

from app.presentation.schemas import Entry, Fact, Proposal, ResumeContent
from app.service.errors import ProcessingError

TEMPLATE_VERSION = "resume-v1"
TEMPLATE = (Path(__file__).parent.parent / "templates" / "resume-v1.tex").read_text("utf-8")
ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def escape_latex(text: str) -> str:
    return "".join(ESCAPES.get(char, char) for char in " ".join(text.split()))


def bullet_list(items: list[Fact]) -> str:
    if not items:
        return ""
    return (
        "\\begin{itemize}\n"
        + "\n".join("\\item " + escape_latex(item.texto) for item in items)
        + "\n\\end{itemize}"
    )


def entries(title: str, values: list[Entry]) -> str:
    if not values:
        return ""
    blocks: list[str] = ["\\section*{" + title + "}"]
    for value in values:
        heading = escape_latex(value.titulo.texto)
        if value.instituicao:
            heading += " --- " + escape_latex(value.instituicao.texto)
        if value.periodo:
            heading += " (" + escape_latex(value.periodo.texto) + ")"
        blocks.extend(["\\textbf{" + heading + "}\\par", bullet_list(value.itens)])
    return "\n".join(blocks)


def render_content(content: ResumeContent) -> str:
    blocks = {
        "CONTATO": "\\par\n".join(escape_latex(f.texto) for f in content.contato) + "\\par",
        "RESUMO": "\\section*{Resumo}\n" + escape_latex(content.resumo.texto)
        if content.resumo
        else "",
        "FORMACAO": entries("Formação", content.formacao),
        "EXPERIENCIAS": entries("Experiências", content.experiencias),
        "PROJETOS": entries("Projetos", content.projetos),
        "COMPETENCIAS": "\\section*{Competências}\n" + bullet_list(content.competencias)
        if content.competencias
        else "",
    }
    # One substitution pass prevents user data from becoming a second template placeholder.
    return re.sub(r"@@([A-Z]+)@@", lambda match: blocks[match[1]], TEMPLATE)


def canonical(text: str) -> str:
    return " ".join(text.casefold().split())


class ProposalValidator:
    def validate(self, proposal: Proposal, source: str, job: str) -> None:
        original = canonical(source)
        if len(proposal.latex_gerado.encode("utf-8")) > 200_000:
            raise ProcessingError("latex_excessivo", "O LaTeX gerado excedeu o limite de bytes.")

        def fail() -> None:
            raise ProcessingError(
                "proposta_sem_evidencia",
                "A proposta não preservou as evidências ou o template. "
                "Revise o texto original e solicite outra otimização.",
            )

        def check(fact: Fact, *, immutable: bool = False) -> None:
            evidence = canonical(fact.trecho_fonte)
            if evidence not in original:
                fail()
            if immutable and canonical(fact.texto) not in evidence:
                fail()
            # Dates, quantities and metrics may not be introduced during paraphrasing.
            if set(re.findall(r"\d+(?:[.,/]\d+)*%?", fact.texto)) - set(
                re.findall(r"\d+(?:[.,/]\d+)*%?", fact.trecho_fonte)
            ):
                fail()

        content = proposal.curriculo
        for fact in content.contato + content.competencias:
            check(fact, immutable=True)
        if content.resumo:
            check(content.resumo)
        for entry in content.formacao + content.experiencias + content.projetos:
            for anchor in (entry.titulo, entry.instituicao, entry.periodo):
                if anchor:
                    check(anchor, immutable=True)
            for fact in entry.itens:
                check(fact)
        for change in proposal.alteracoes:
            if (
                canonical(change.trecho_fonte) not in original
                or canonical(change.antes) not in original
            ):
                fail()
        rendered = render_content(content)
        for change in proposal.alteracoes:
            if canonical(escape_latex(change.depois)) not in canonical(rendered):
                fail()
        for keyword in proposal.palavras_chave_usadas:
            evidence = canonical(keyword.evidencia_no_original)
            if (
                evidence not in original
                or canonical(keyword.termo) not in evidence
                or canonical(keyword.termo) not in canonical(job)
                or canonical(escape_latex(keyword.termo)) not in canonical(rendered)
            ):
                fail()
        for gap in proposal.lacunas:
            if canonical(gap.termo_da_vaga) not in canonical(job):
                fail()
        # The initial model-generated LaTeX must correspond exactly to validated structured facts.
        # This checks the entire fixed preamble AND prevents hidden material after the document.
        if proposal.latex_gerado.replace("\r\n", "\n").strip() != rendered.strip():
            fail()
