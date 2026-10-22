from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import get_settings


def test_initial_migration_up_down_and_schema_drift(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "migration.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET", "migration-test-secret-with-32-characters")
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "head")
        engine = create_engine(url)
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "usuarios",
            "curriculos",
            "tentativas_geracao",
        }
        engine.dispose()
        command.check(config)
        command.downgrade(config, "base")
        engine = create_engine(url)
        assert inspect(engine).get_table_names() == ["alembic_version"]
        engine.dispose()
    finally:
        get_settings.cache_clear()
