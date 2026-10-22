"""Executed inside the disposable compiler only. Stdout is exclusively PDF bytes."""

import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    latex = sys.stdin.buffer.read(200_001)
    if len(latex) > 200_000:
        return 1
    Path("main.tex").write_bytes(latex)
    with Path("/work/compile.log").open("wb") as log:
        result = subprocess.run(
            [
                "tectonic",
                "-X",
                "compile",
                "--untrusted",
                "--only-cached",
                "--reruns",
                "1",
                "--outdir",
                "/work",
                "/work/main.tex",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=35,
            check=False,
        )
    if result.returncode:
        log_text = Path("/work/compile.log").read_bytes()[:100_000].decode(errors="replace")
        match = re.search(r"(?:main\.tex:|l\.)(\d{1,6})", log_text)
        sys.stderr.write("CURRICULO_TEX_ERROR:" + (match[1] if match else "0"))
        return 1
    pdf = Path("/work/main.pdf")
    if not pdf.is_file() or pdf.stat().st_size > 10 * 1024**2:
        return 1
    sys.stdout.buffer.write(pdf.read_bytes())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Do not propagate raw LaTeX, internal paths or tracebacks outside the container.
        sys.exit(1)
