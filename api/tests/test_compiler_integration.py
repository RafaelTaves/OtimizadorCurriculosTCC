import io
import os
import unicodedata
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.infrastructure.compiler import DockerCompiler
from app.service.proposals import TEMPLATE
from tests.conftest import proposal

pytestmark = pytest.mark.compiler


def test_generated_header_urls_and_entries_compile_offline(settings):
    if os.getenv("RUN_COMPILER_TESTS") != "1":
        pytest.skip("Configure RUN_COMPILER_TESTS=1 e construa a imagem Tectonic.")
    # Fictional fixture: url activates font metrics not exercised by href labels.
    body = r"""
\begin{center}
{\LARGE \textbf{Pessoa de Teste}} \\
{\large Desenvolvedor de Software Júnior} \\
São Paulo, SP {\textbullet}
\href{mailto:teste@example.com}{teste@example.com} \\
\url{linkedin.com/in/perfil-de-teste} {\textbullet}
\url{github.com/perfil-de-teste}
\end{center}
\section{Experiência}
\cventry{Organização de Teste}{}{Desenvolvedor Júnior}{2024 – Atual}
\begin{itemize}\item Aplicações em JavaScript e PostgreSQL.\end{itemize}
\section{Projetos}
\cventry{Projeto de Teste}{}{}{}
\section{Educação}
\cventry{Instituição de Teste}{}{Sistemas de Informação}{2022 – 2026}
"""
    latex = TEMPLATE.partition(r"\begin{document}")[0]
    latex += r"\begin{document}" + body + r"\end{document}"
    pdf = DockerCompiler(settings).compile(latex)
    reader = PdfReader(io.BytesIO(pdf))
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    assert "Pessoa de Teste" in extracted
    assert "github.com/perfil-de-teste" in extracted
    assert "Sistemas de Informação" in extracted


def test_real_pdf_is_selectable_and_special_characters_compile(settings):
    if os.getenv("RUN_COMPILER_TESTS") != "1":
        pytest.skip("Configure RUN_COMPILER_TESTS=1 e construa a imagem Tectonic.")
    latex = proposal().latex_gerado.replace("Ana Silva", r"João Silva C\# 100\% \& SQL\_API")
    pdf = DockerCompiler(settings).compile(latex)
    reader = PdfReader(io.BytesIO(pdf))
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    assert "João" in extracted and "C#" in extracted and "SQL_API" in extracted


def test_compiler_cannot_read_host_files(settings, tmp_path: Path):
    if os.getenv("RUN_COMPILER_TESTS") != "1":
        pytest.skip("Configure RUN_COMPILER_TESTS=1 e construa a imagem Tectonic.")
    marker = "THIS_HOST_SECRET_MUST_NEVER_APPEAR"
    secret = tmp_path / "host-secret.tex"
    secret.write_text(marker)
    latex = proposal().latex_gerado.replace(
        r"\end{document}",
        r"\IfFileExists{"
        + secret.as_posix()
        + r"}{\input{"
        + secret.as_posix()
        + r"}}{Host file unavailable}\end{document}",
    )
    pdf = DockerCompiler(settings).compile(latex)
    extracted = "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    assert marker not in extracted
    # PDF text extraction can preserve the typographic fi ligature as U+FB01.
    assert "Host file unavailable" in unicodedata.normalize("NFKC", extracted)
