"""Validate model-written LaTeX structure without enforcing literal content parity.

This is a deliberately limited reader for the commands used by resume-v1, not a
TeX interpreter or a replacement for the isolated compiler.
"""

import re

from app.presentation.schemas import Fact, ResumeContent
from app.service.errors import ProcessingError

ESCAPED = {
    "&": "&",
    "%": "%",
    "$": "$",
    "#": "#",
    "_": "_",
    "{": "{",
    "}": "}",
    "textbackslash": "\\",
    "textasciitilde": "~",
    "textasciicircum": "^",
}


def invalid(reason: str) -> None:
    raise ProcessingError(
        "proposta_template_invalido",
        "O LaTeX da IA não atende às regras técnicas do template: " + reason + ".",
        transient=True,
    )


def without_comments(value: str) -> str:
    # Consume escaped commands first, distinguishing \% from \\ followed by %.
    return re.sub(
        r"\\(?:[A-Za-z]+|[\s\S])|%[^\n]*",
        lambda m: "" if m[0].startswith("%") else m[0],
        value,
    )


def document_parts(value: str) -> tuple[str, str]:
    clean = without_comments(value.replace("\r\n", "\n"))
    if "^^" in clean:
        invalid("sequência de controle não permitida")
    parts = re.split(r"\\begin\s*\{document\}", clean)
    if len(parts) != 2:
        invalid("início de documento inválido")
    end = re.split(r"\\end\s*\{document\}", parts[1])
    if len(end) != 2 or end[1].strip():
        invalid("fim de documento inválido ou conteúdo após o documento")
    return parts[0], end[0]


class BodyReader:
    def __init__(self, body: str, contacts: list[Fact]) -> None:
        self.body = body
        self.contacts = contacts
        self.pos = 0
        self.environments: list[str] = []
        self.depth = 0

    def spaces(self) -> None:
        while self.pos < len(self.body) and self.body[self.pos].isspace():
            self.pos += 1

    def group(self) -> str:
        self.spaces()
        if self.pos >= len(self.body) or self.body[self.pos] != "{":
            invalid("argumento de comando inválido")
        self.pos += 1
        self.depth += 1
        if self.depth > 40:
            invalid("grupos excessivamente aninhados")
        result = self.read(group=True)
        self.depth -= 1
        return result

    def size(self, value: str) -> None:
        if not re.fullmatch(r"(?:0|1|2)(?:\.\d+)?(?:cm|mm|em|ex|pt)", value.strip()):
            invalid("espaçamento não permitido")

    def command(self) -> str:
        match = re.match(r"\\([A-Za-z]+|[\s\S])", self.body[self.pos :])
        if not match:
            invalid("comando incompleto")
            return ""
        self.pos += len(match[0])
        name = match[1]
        if name in ESCAPED:
            return ESCAPED[name]
        if name in ("textbf", "textit", "emph", "textrm", "textnormal"):
            return self.group()
        if name == "cventry":
            return " " + " ".join(self.group() for _ in range(4)) + " "
        if name in ("section", "subsection"):
            if self.body[self.pos : self.pos + 1] == "*":
                self.pos += 1
            self.group()
            return " "
        if name in ("begin", "end"):
            environment = self.group().strip()
            if environment not in ("center", "itemize"):
                invalid("ambiente não permitido")
            if name == "begin":
                self.environments.append(environment)
            elif not self.environments or self.environments.pop() != environment:
                invalid("ambientes desbalanceados")
            return " "
        if name == "href":
            target, label = self.group(), self.group()
            address = target.removeprefix("mailto:")
            if not (
                target.startswith(("mailto:", "https://", "http://"))
                and any(address in contact.texto for contact in self.contacts)
            ):
                invalid("link sem correspondência nos contatos confirmados")
            return label
        if name == "url":
            address = self.group()
            if not any(address in contact.texto for contact in self.contacts):
                invalid("endereço sem correspondência nos contatos")
            return address
        if name in ("vspace", "hspace"):
            self.size(self.group())
            return " "
        if name == "\\":
            self.spaces()
            if self.body[self.pos : self.pos + 1] == "[":
                end = self.body.find("]", self.pos)
                if end < 0:
                    invalid("espaçamento incompleto")
                self.size(self.body[self.pos + 1 : end])
                self.pos = end + 1
            return " "
        if name in ("par", "noindent", "hfill", "textbullet", "textbar", "quad", "qquad", " "):
            return " "
        if name == "item":
            if not self.environments or self.environments[-1] != "itemize":
                invalid("item fora de lista")
            return " "
        if name in ("LARGE", "Large", "large", "small", "normalsize", "bfseries", "itshape"):
            return ""
        invalid("comando não permitido no corpo")
        return ""

    def read(self, *, group: bool = False) -> str:
        output: list[str] = []
        while self.pos < len(self.body):
            char = self.body[self.pos]
            if char == "\\":
                output.append(self.command())
            elif char == "{":
                output.append(self.group())
            elif char == "}":
                if not group:
                    invalid("fechamento de grupo inesperado")
                self.pos += 1
                return "".join(output)
            else:
                if char in "&$#_^":
                    invalid("caractere especial sem escape")
                output.append(" " if char == "~" else char)
                self.pos += 1
        if group:
            invalid("grupo não fechado")
        return "".join(output)


def validate_model_latex(latex: str, template: str, content: ResumeContent) -> None:
    preamble, body = document_parts(latex)
    template_preamble, _ = document_parts(template)
    # Ignore comments and whitespace, but preserve every command and argument.
    pattern = r"\\[A-Za-z]+|\\.|[^\s]"
    if re.findall(pattern, preamble) != re.findall(pattern, template_preamble):
        invalid("preâmbulo alterado")
    reader = BodyReader(body, content.contato)
    visible = reader.read()
    if reader.environments:
        invalid("ambiente não fechado")
    if not visible.strip():
        invalid("documento sem conteúdo")
    # Wording, omissions and section labels are accepted for human review.
    # Preserve the model's document instead of reconstructing or matching fields.
