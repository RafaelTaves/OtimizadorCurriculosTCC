import subprocess
from pathlib import Path

template = Path("/opt/template.tex").read_text(encoding="utf-8")
# Exercise generated-document commands as well as the template itself. The template
# uses href labels, while model output also uses url (and its separate font metrics).
# Old @@ markers are no longer present in resume-v1, so replacing them warmed nothing.
sample = r"""\begin{center}
{\LARGE \textbf{Pessoa de Teste}} \\
{\large Desenvolvedor de Software Júnior} \\
São Paulo, SP {\textbullet} (11) 00000-0000 {\textbullet}
\href{mailto:teste@example.com}{teste@example.com} \\
\url{linkedin.com/in/perfil-de-teste} {\textbullet}
\url{github.com/perfil-de-teste}
\end{center}
\section*{Formação, Experiências, Projetos, Competências}
João, programação, ação, educação, início. C\# e C\_\&\%\$\{\}
\textbackslash{}\textasciitilde{}\textasciicircum{}
\textbf{Universidade --- 2024 (2020--2024)}\par
\section{Experiência}
\cventry{Organização de Teste}{}{Desenvolvedor Júnior}{2024 – Atual}
\begin{itemize}\item Python e PostgreSQL\end{itemize}
\section{Projetos}
\cventry{Projeto de Teste}{}{}{}
\section{Educação}
\cventry{Instituição de Teste}{}{Sistemas de Informação}{2022 – 2026}
"""
preamble, separator, _ = template.partition(r"\begin{document}")
if not separator:
    raise ValueError("Template sem início de documento")
for document in (template, preamble + separator + "\n" + sample + r"\end{document}"):
    Path("warm.tex").write_text(document, encoding="utf-8")
    subprocess.run(["tectonic", "-X", "compile", "--untrusted", "warm.tex"], check=True)
    # Verify the cache suffices without consulting the network.
    subprocess.run(
        ["tectonic", "-X", "compile", "--untrusted", "--only-cached", "warm.tex"], check=True
    )
for path in Path(".").glob("warm.*"):
    path.unlink()
