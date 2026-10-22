import re
import subprocess
import tempfile
from uuid import uuid4

from app.config import Settings
from app.service.errors import ProcessingError


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
        try:
            with tempfile.TemporaryFile() as pdf_file, tempfile.TemporaryFile() as log:
                result = subprocess.run(
                    command,
                    input=latex.encode("utf-8"),
                    stdout=pdf_file,
                    stderr=log,
                    timeout=self.settings.compiler_timeout_seconds,
                    check=False,
                )
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
            try:
                subprocess.run(
                    ["docker", "rm", "--force", name], capture_output=True, timeout=10, check=False
                )
            except OSError, subprocess.TimeoutExpired:
                pass
