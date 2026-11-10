"""Real FastAPI + disposable SQLite; no OpenAI key or worker, local smoke test only."""
import sys
import tempfile
from pathlib import Path
import uvicorn

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "api"))
from app.api.application import create_app  # noqa: E402
from app.config import Settings  # noqa: E402
from app.infrastructure.database import Base, Database  # noqa: E402

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(
            _env_file=None,
            database_url="sqlite:///" + str(Path(directory) / "test.db"),
            jwt_secret="real-api-smoke-only-not-a-production-secret",
            storage_root=Path(directory) / "storage",
        )
        database = Database(settings.database_url)
        Base.metadata.create_all(database.engine)
        try:
            uvicorn.run(create_app(settings, database=database), host="127.0.0.1", port=8012, access_log=False)
        finally:
            database.engine.dispose()
