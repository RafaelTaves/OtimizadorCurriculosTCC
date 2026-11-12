import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from time import monotonic
from uuid import uuid4

from app.config import Settings
from app.service.errors import ProcessingError

logger = logging.getLogger(__name__)


class SandboxCompiler:
    """Railway: per-job chroot, dropped UID, seccomp and resource limits.

    The PDF worker alone runs as root to enter chroot. The TeX process gets
    neither the worker filesystem nor its credentials. No Docker socket needed.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def compile(self, latex: str) -> bytes:
        if len(latex.encode("utf-8")) > self.settings.max_latex_bytes:
            raise ProcessingError("latex_excessivo", "O LaTeX excede o limite.")
        try:
            with tempfile.TemporaryDirectory(prefix="tex-job-") as directory:
                root = Path(directory) / "root"
                shutil.copytree("/opt/tex-root", root, copy_function=os.link)
                work = root / "work"
                work.mkdir(mode=0o700)
                (work / "main.tex").write_text(latex, encoding="utf-8")
                os.chown(work, 10002, 10002)
                with tempfile.TemporaryFile() as log:
                    result = subprocess.run(
                        [sys.executable, "/opt/tex-sandbox.py", str(root)],
                        stdin=subprocess.DEVNULL,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
                        timeout=self.settings.compiler_timeout_seconds,
                        check=False,
                    )
                    if result.returncode:
                        log.seek(0)
                        diagnostic = log.read(100_000).decode(errors="replace")
                        if "SANDBOX_UNAVAILABLE" in diagnostic:
                            raise ProcessingError(
                                "compilador_indisponivel",
                                "O isolamento do compilador está indisponível.",
                                transient=True,
                            )
                        match = re.search(r"(?:main\.tex:|l\.)(\d{1,6})", diagnostic)
                        message = (
                            "Não foi possível compilar. Confira os comandos e pacotes do LaTeX."
                        )
                        if match:
                            message += f" Verifique a linha {match[1]}."
                        raise ProcessingError("latex_invalido", message)
                pdf = work / "main.pdf"
                if not pdf.is_file() or pdf.is_symlink():
                    raise ProcessingError(
                        "pdf_invalido", "O compilador não produziu um PDF válido."
                    )
                if pdf.stat().st_size > self.settings.max_pdf_bytes:
                    raise ProcessingError("pdf_excessivo", "O PDF gerado excede o limite.")
                data = pdf.read_bytes()
                if not data.startswith(b"%PDF-"):
                    raise ProcessingError(
                        "pdf_invalido", "O compilador não produziu um PDF válido."
                    )
                return data
        except subprocess.TimeoutExpired as exc:
            raise ProcessingError(
                "compilacao_timeout", "A compilação excedeu o tempo limite."
            ) from exc
        except OSError as exc:
            raise ProcessingError(
                "compilador_indisponivel", "O compilador está indisponível.", transient=True
            ) from exc


class DockerCompiler:
    """Each compilation gets a fresh container with no mounts or network."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def compile(self, latex: str) -> bytes:
        name = "curriculo-" + uuid4().hex
        command = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            name,
            "--interactive",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--user=10001:10001",
            "--memory=512m",
            "--memory-swap=512m",
            "--cpus=1",
            "--pids-limit=32",
            "--ulimit",
            "fsize=20000000:20000000",
            "--ulimit",
            "cpu=35:35",
            "--tmpfs",
            "/work:rw,noexec,nosuid,size=64m,uid=10001,gid=10001,mode=700",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=32m,uid=10001,gid=10001,mode=700",
            self.settings.compiler_image,
        ]
        needs_cleanup = True
        try:
            with tempfile.TemporaryFile() as pdf_file, tempfile.TemporaryFile() as log:
                started = monotonic()
                result = subprocess.run(
                    command,
                    input=latex.encode("utf-8"),
                    stdout=pdf_file,
                    stderr=log,
                    timeout=self.settings.compiler_timeout_seconds,
                    check=False,
                )
                logger.info("compiler docker_run_ms=%d", int((monotonic() - started) * 1000))
                needs_cleanup = result.returncode in (125, 126, 127)
                if result.returncode != 0:
                    if result.returncode in (125, 126, 127):
                        raise ProcessingError(
                            "compilador_indisponivel",
                            "A imagem ou o serviço de compilação está indisponível.",
                            transient=True,
                        )
                    log.seek(0)
                    # Only accept the compiler's allowlisted line-number diagnostic, never raw logs.
                    diagnostic = log.read(4096).decode("utf-8", errors="replace")
                    match = re.search(r"CURRICULO_TEX_ERROR:(\d{1,6})", diagnostic)
                    message = "Não foi possível compilar. Confira os comandos e pacotes do LaTeX."
                    if match:
                        message += f" Verifique a linha {match[1]}."
                    raise ProcessingError("latex_invalido", message)
                if pdf_file.tell() > self.settings.max_pdf_bytes:
                    raise ProcessingError("pdf_excessivo", "O PDF gerado excede o limite.")
                pdf_file.seek(0)
                pdf = pdf_file.read(self.settings.max_pdf_bytes + 1)
                if not pdf.startswith(b"%PDF-"):
                    raise ProcessingError(
                        "pdf_invalido", "O compilador não produziu um PDF válido."
                    )
                return pdf
        except subprocess.TimeoutExpired as exc:
            raise ProcessingError(
                "compilacao_timeout", "A compilação excedeu o tempo limite."
            ) from exc
        except OSError as exc:
            raise ProcessingError(
                "compilador_indisponivel", "O compilador está indisponível.", transient=True
            ) from exc
        finally:
            if needs_cleanup:
                started = monotonic()
                try:
                    subprocess.run(
                        ["docker", "rm", "--force", name],
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                except OSError, subprocess.TimeoutExpired:
                    pass
                logger.info("compiler docker_cleanup_ms=%d", int((monotonic() - started) * 1000))
