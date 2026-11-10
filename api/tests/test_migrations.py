import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings


@pytest.mark.postgres
def test_postgres_migration_preserves_existing_records_and_restricts_browser_roles():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configure TEST_DATABASE_URL para validar migration no PostgreSQL.")
    engine = create_engine(url)
    schema = "migration_test_" + uuid4().hex
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    try:
        with engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            config.attributes["connection"] = connection
            command.upgrade(config, "0001")
            identifier = uuid4()
            connection.execute(
                text(
                    "INSERT INTO usuarios "
                    "(id, username, email, hashed_password, created_at, updated_at) "
                    "VALUES (:id, 'fixture', 'fixture@example.com', 'synthetic', now(), now())"
                ),
                {"id": identifier},
            )
            connection.execute(
                text(
                    "INSERT INTO tentativas_geracao "
                    "(id, usuario_id, tipo_operacao, request_hash, status, etapa, executions, "
                    "available_at, created_at) VALUES "
                    "(:attempt, :user, 'otimizacao', :hash, 'concluida', 'finalizada', "
                    "1, now(), now())"
                ),
                {"attempt": uuid4(), "user": identifier, "hash": "a" * 64},
            )
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT id FROM usuarios")) == identifier
            assert connection.execute(
                text("SELECT status, execucoes_analise, execucoes_ciclo FROM tentativas_geracao")
            ).one() == ("concluida", [], 0)
            command.check(config)
            for table in (
                "sessoes_complementacao",
                "rodadas_complementacao",
                "registros_idempotencia",
            ):
                assert connection.scalar(
                    text(
                        "SELECT relrowsecurity FROM pg_class WHERE oid = CAST(:table AS regclass)"
                    ),
                    {"table": f"{schema}.{table}"},
                )
                for role in connection.scalars(
                    text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")
                ):
                    assert not connection.scalar(
                        text("SELECT has_table_privilege(:role, :table, 'SELECT')"),
                        {"role": role, "table": f"{schema}.{table}"},
                    )
            command.downgrade(config, "base")
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        engine.dispose()


def test_initial_migration_up_down_and_schema_drift(tmp_path, monkeypatch):
    url = "sqlite:///" + str(tmp_path / "migration.db")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET", "migration-test-secret-with-32-characters")
    get_settings.cache_clear()
    try:
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        command.upgrade(config, "head")
        engine = create_engine(url)
        assert set(inspect(engine).get_table_names()) == {
            "alembic_version",
            "usuarios",
            "curriculos",
            "tentativas_geracao",
            "sessoes_complementacao",
            "rodadas_complementacao",
            "registros_idempotencia",
        }
        engine.dispose()
        command.check(config)
        command.downgrade(config, "base")
        engine = create_engine(url)
        assert inspect(engine).get_table_names() == ["alembic_version"]
        engine.dispose()
    finally:
        get_settings.cache_clear()
