import logging
import signal
from threading import Event
from types import FrameType

from app.config import get_settings
from app.infrastructure.compiler import DockerCompiler
from app.infrastructure.database import Database
from app.infrastructure.openai_optimizer import OpenAIOptimizer
from app.infrastructure.storage import LocalStorage
from app.service.worker import Worker


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    settings = get_settings()
    database = Database(settings.database_url)
    worker = Worker(
        settings,
        database,
        LocalStorage(settings.storage_root),
        OpenAIOptimizer(settings),
        DockerCompiler(settings),
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
