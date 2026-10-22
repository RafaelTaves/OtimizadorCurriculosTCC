import subprocess
from pathlib import Path

template = Path("/opt/template.tex").read_text()
sample = r"""\section*{Formação, Experiências, Projetos, Competências}
João, programação, ação, educação, início. C\# e C\_\&\%\$\{\}
\textbackslash{}\textasciitilde{}\textasciicircum{}
\textbf{Universidade --- 2024 (2020--2024)}\par
\begin{itemize}\item Python e PostgreSQL\end{itemize}
"""
for marker in ("CONTATO", "RESUMO", "FORMACAO", "EXPERIENCIAS", "PROJETOS", "COMPETENCIAS"):
    template = template.replace("@@" + marker + "@@", sample)
Path("warm.tex").write_text(template)
subprocess.run(["tectonic", "-X", "compile", "--untrusted", "warm.tex"], check=True)
# Verify the cache suffices without consulting the network.
subprocess.run(
    ["tectonic", "-X", "compile", "--untrusted", "--only-cached", "warm.tex"], check=True
)
for path in Path(".").glob("warm.*"):
    path.unlink()
