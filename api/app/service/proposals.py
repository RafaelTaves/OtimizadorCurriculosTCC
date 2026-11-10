import re
from pathlib import Path

from app.presentation.schemas import Entry, Fact, Proposal, ResumeContent, SourceRecord
from app.service.errors import ProcessingError
from app.service.latex_validation import validate_model_latex

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
    # Support the original marker template and the user's generic template without
    # modifying its source, preamble or macros. Never publish example CV fields.
    if "@@CONTATO@@" in TEMPLATE:
        return re.sub(r"@@([A-Z]+)@@", lambda match: blocks[match[1]], TEMPLATE)
    preamble, separator, _ = TEMPLATE.partition(r"\begin{document}")
    if not separator:
        raise ProcessingError("template_invalido", "O template não possui início de documento.")
    order = ("CONTATO", "RESUMO", "EXPERIENCIAS", "PROJETOS", "COMPETENCIAS", "FORMACAO")
    if not content.experiencias:
        order = ("CONTATO", "RESUMO", "FORMACAO", "PROJETOS", "COMPETENCIAS", "EXPERIENCIAS")
    return (
        preamble
        + separator
        + "\n"
        + "\n".join(blocks[key] for key in order)
        + "\n\\end{document}\n"
    )


def canonical(text: str) -> str:
    return " ".join(text.casefold().split())


def confirmed_sources(text: str, complements: list[SourceRecord]) -> dict[str, str]:
    original = text
    for item in complements:
        if item.substitui_trecho_original:
            if item.substitui_trecho_original not in original:
                raise ProcessingError(
                    "correcao_invalida", "Correções sobrepostas ou sem trecho original."
                )
            original = original.replace(item.substitui_trecho_original, "\n")
    return {
        "curriculo_original": original,
        **{f"complemento:{item.id}": item.texto for item in complements},
    }


class ProposalValidator:
    def validate(self, proposal: Proposal, source: str | dict[str, str], job: str) -> None:
        sources = source if isinstance(source, dict) else {"curriculo_original": source}
        if len(proposal.latex_gerado.encode("utf-8")) > 200_000:
            raise ProcessingError("latex_excessivo", "O LaTeX gerado excedeu o limite de bytes.")

        def fail(message: str, *, code: str = "proposta_sem_evidencia") -> None:
            raise ProcessingError(
                code,
                message + " A proposta não foi salva. Solicite outra otimização.",
                transient=True,
            )

        def evidence(fonte: str, quote: str, field: str) -> str:
            original = sources.get(fonte)
            if original is None or canonical(quote) not in canonical(original):
                fail(f"A IA citou uma fonte ou um trecho não confirmado em {field}.")
            return canonical(quote)

        def check(fact: Fact, field: str, *, immutable: bool = False) -> None:
            quote = evidence(fact.fonte, fact.trecho_fonte, field)
            if immutable and canonical(fact.texto) not in quote:
                fail(f"A IA alterou um dado que deve ser literal em {field}.")
            # Dates, quantities and metrics may not be introduced during paraphrasing.
            if set(re.findall(r"\d+(?:[.,/]\d+)*%?", fact.texto)) - set(
                re.findall(r"\d+(?:[.,/]\d+)*%?", fact.trecho_fonte)
            ):
                fail(f"A IA incluiu números ou datas sem comprovação em {field}.")

        content = proposal.curriculo
        for field in ("contato", "competencias"):
            for index, fact in enumerate(getattr(content, field)):
                check(fact, f"curriculo.{field}[{index}]", immutable=True)
        if content.resumo:
            check(content.resumo, "curriculo.resumo")
        for field in ("formacao", "experiencias", "projetos"):
            for index, entry in enumerate(getattr(content, field)):
                path = f"curriculo.{field}[{index}]"
                for name in ("titulo", "instituicao", "periodo"):
                    anchor = getattr(entry, name)
                    if anchor:
                        check(anchor, f"{path}.{name}", immutable=True)
                for item_index, fact in enumerate(entry.itens):
                    check(fact, f"{path}.itens[{item_index}]")
        for index, change in enumerate(proposal.alteracoes):
            field = f"alteracoes[{index}]"
            evidence(change.fonte, change.trecho_fonte, field)
            if change.antes is not None:
                evidence(change.fonte, change.antes, field + ".antes")
            if change.tipo == "inclusao" and not change.fonte.startswith("complemento:"):
                fail(f"A IA declarou uma inclusão sem complemento confirmado em {field}.")
        rendered = render_content(content)
        for index, change in enumerate(proposal.alteracoes):
            if canonical(escape_latex(change.depois)) not in canonical(rendered):
                fail(
                    f"A IA descreveu uma alteração ausente do currículo em alteracoes[{index}].",
                    code="proposta_alteracao_invalida",
                )
        # Keyword annotations are accepted as returned by the model for human review.
        # They do not gate publication or require literal matches across the inputs.
        for index, gap in enumerate(proposal.lacunas):
            if canonical(gap.termo_da_vaga) not in canonical(job):
                fail(
                    f"A IA indicou um requisito ausente da vaga em lacunas[{index}].",
                    code="proposta_lacuna_invalida",
                )
        validate_model_latex(proposal.latex_gerado, TEMPLATE, content)
