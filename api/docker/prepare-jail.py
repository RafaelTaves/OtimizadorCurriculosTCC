"""Build the read-only compiler filesystem; never include application files."""

import re
import shutil
import subprocess
from pathlib import Path

root = Path("/opt/tex-root")
paths = [
    Path("/usr/local/bin/tectonic"),
    Path("/etc/fonts"),
    Path("/usr/share/fonts"),
    Path("/usr/share/fontconfig"),
    Path("/home/compiler/.cache"),
]
libraries = subprocess.run(
    ["ldd", "/usr/local/bin/tectonic"], capture_output=True, text=True, check=False
).stdout
paths += [Path(path) for path in re.findall(r"(/[^\s()]+)", libraries)]
for source in paths:
    target = root / source.relative_to("/")
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        shutil.copy2(source, target)
for path in root.rglob("*"):
    path.chmod(0o755 if path.is_dir() or path.name == "tectonic" else 0o644)
