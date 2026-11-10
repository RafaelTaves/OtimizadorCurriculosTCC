import argparse
import logging
import signal
from threading import Event
from types import FrameType

from app.config import get_settings
from app.infrastructure.compiler import DockerCompiler
from app.infrastructure.database import Database
from app.infrastructure.openai_interviewer import OpenAIInterviewAnalyzer
from app.infrastructure.openai_optimizer import OpenAIOptimizer
from app.infrastructure.storage import LocalStorage
from app.service.worker import Worker


def main() -> None:
    parser = argparse.ArgumentParser(description="Consome a fila de processamento.")
    parser.add_argument("--lane", choices=("all", "ai", "pdf"), default="all")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    database = Database(settings.database_url)
    worker = Worker(
        settings,
        database,
        LocalStorage(settings.storage_root),
        OpenAIOptimizer(settings),
        DockerCompiler(settings),
        analyzer=OpenAIInterviewAnalyzer(settings),
        lane=args.lane,
        cleanup_interval_seconds=30,
    )
    stop = Event()

    def shutdown(signum: int, frame: FrameType | None) -> None:
        stop.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    try:
        while not stop.is_set():
            try:
                worked = worker.run_once()
            except Exception:
                logging.getLogger(__name__).error("worker_database_unavailable")
                worked = False
            if not worked:
                stop.wait(settings.worker_poll_seconds)
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
