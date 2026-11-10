import io
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path('api').resolve()))
from app.config import Settings
from app.infrastructure.compiler import DockerCompiler
from app.service.errors import ProcessingError
from pypdf import PdfReader

settings = Settings(_env_file=Path('api/.env'))
latex = Path('tmp/compiler-repro.tex').read_text(encoding='utf-8')
original_run = subprocess.run
diagnostic = '''import pathlib, subprocess, sys
pathlib.Path('/work/main.tex').write_bytes(sys.stdin.buffer.read())
r = subprocess.run(['tectonic', '-X', 'compile', '--untrusted', '--only-cached', '--reruns', '1', '--outdir', '/work', '/work/main.tex'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
sys.stderr.buffer.write(r.stdout)
if r.returncode == 0:
    sys.stdout.buffer.write(pathlib.Path('/work/main.pdf').read_bytes())
sys.exit(r.returncode)
'''

def run(command, **kwargs):
    if command[1] == 'run' and '--diagnostic' in sys.argv:
        command = command[:-1] + ['--entrypoint', 'python', command[-1], '-c', diagnostic]
    result = original_run(command, **kwargs)
    if command[1] == 'run' and result.returncode:
        kwargs['stderr'].seek(0)
        log = kwargs['stderr'].read().decode('utf-8', errors='replace')
        Path('tmp/compiler-diagnostic.log').write_text(log, encoding='utf-8')
        print(log)
    return result

with patch('app.infrastructure.compiler.subprocess.run', side_effect=run):
    try:
        pdf = DockerCompiler(settings).compile(latex)
        Path('tmp/compiler-repro.pdf').write_bytes(pdf)
        reader = PdfReader(io.BytesIO(pdf))
        extracted = '\n'.join(p.extract_text() for p in reader.pages)
        print('PDF_OK', 'pages=', len(reader.pages), 'bytes=', len(pdf))
        print('expected_name_present=', 'Lucas Ferreira Martins' in extracted)
    except ProcessingError as exc:
        print('FAIL', exc.code, exc.message)
        sys.exit(1)
