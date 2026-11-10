"""Start the local API and its queue consumer together: python -m app.dev."""

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from time import sleep

logger = logging.getLogger(__name__)
API_ROOT = Path(__file__).resolve().parents[1]


def stop_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    # Signal all children first, so a slow worker does not delay API shutdown.
    for process in processes:
        if process.poll() is None:
            process.terminate()
    for process in processes:
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run(host: str = "127.0.0.1", port: int = 8000) -> int:
    processes: list[subprocess.Popen[bytes]] = []
    commands = {
        "API": [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:create_app",
            "--factory",
            "--host",
            host,
            "--port",
            str(port),
        ],
        "worker IA": [sys.executable, "-m", "app.worker", "--lane", "ai"],
        "worker PDF": [sys.executable, "-m", "app.worker", "--lane", "pdf"],
    }
    try:
        for name, command in commands.items():
            # The same interpreter, environment and working directory are essential:
            # both services must use the same .env, database and private storage.
            processes.append(subprocess.Popen(command, cwd=API_ROOT))
            logger.info("%s iniciado", name)
        logger.info("API e workers ativos. Ctrl+C encerra os três. Reinicie após editar o backend.")
        while True:
            for name, process in zip(commands, processes, strict=True):
                code = process.poll()
                if code is not None:
                    logger.error("%s encerrou (código %s); encerrando o outro serviço.", name, code)
                    return code or 1
            sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        stop_processes(processes)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicia a API e o worker da fila juntos.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    raise SystemExit(run(args.host, args.port))


if __name__ == "__main__":
    main()
