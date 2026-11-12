"""Real Linux smoke test: docker run --rm --entrypoint python IMAGE /opt/check_sandbox.py."""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from app.config import Settings
from app.infrastructure.compiler import SandboxCompiler
from app.service.errors import ProcessingError
from app.service.proposals import TEMPLATE


def main() -> None:
    settings = Settings(_env_file=None, jwt_secret="sandbox-smoke-only-not-a-real-secret")
    compiler = SandboxCompiler(settings)
    with tempfile.TemporaryDirectory() as directory:
        secret = Path(directory) / "secret.tex"
        secret.write_text("HOST_SECRET_MUST_NOT_APPEAR")
        document = TEMPLATE.partition(r"\begin{document}")[0] + r"\begin{document}"
        document += "Pessoa de Teste — João, programação. "
        document += r"\url{github.com/perfil-de-teste} "
        document += r"\IfFileExists{" + str(secret) + r"}{\input{" + str(secret)
        document += r"}}{Host file unavailable}\end{document}"
        pdf = compiler.compile(document)
        text = unicodedata.normalize(
            "NFKC", "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
        )
        assert "João" in text and "Host file unavailable" in text
        assert "HOST_SECRET" not in text and "github.com/perfil-de-teste" in text
        assert not list(Path("/tmp").glob("tex-job-*"))
    try:
        compiler.compile(r"\documentclass{article}\begin{document}\invalidcommand\end{document}")
    except ProcessingError as exc:
        assert exc.code == "latex_invalido"
        assert "/work" not in exc.message
    else:
        raise AssertionError("Invalid TeX was accepted")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "root"
        shutil.copytree("/opt/tex-root", root, copy_function=os.link)
        (root / "work").mkdir()
        probe = """
import errno, os, runpy, socket, sys
enter = runpy.run_path('/opt/tex-sandbox.py')['enter']
enter(sys.argv[1])
assert os.getuid() == 10002 and os.getgid() == 10002
assert not os.path.exists('/proc') and not os.path.exists('/app')
try:
    socket.socket()
except OSError as exc:
    assert exc.errno == errno.EPERM
else:
    raise AssertionError('Network allowed')
try:
    open('/usr/local/bin/tectonic', 'wb')
except PermissionError:
    pass
else:
    raise AssertionError('Read-only binary was writable')
"""
        subprocess.run([sys.executable, "-c", probe, str(root)], check=True, timeout=10)
    print(
        "PASS: selectable PDF, accents, offline cache, host isolation, "
        "UID, network, read-only files"
    )


if __name__ == "__main__":
    main()
