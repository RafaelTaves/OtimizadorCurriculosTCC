import io
import os
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.infrastructure.compiler import DockerCompiler
from tests.conftest import proposal

pytestmark = pytest.mark.compiler


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
    assert "Host file unavailable" in extracted
