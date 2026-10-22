import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.infrastructure.database import Base, Database
from app.infrastructure.models import Attempt, Operation, Resume, Status, User
from app.infrastructure.storage import LocalStorage
from app.service.errors import AppError
from app.service.resumes import QueueService
from app.service.worker import Worker
from tests.conftest import JOB, SOURCE, FakeCompiler, FakeOptimizer

pytestmark = pytest.mark.postgres


@pytest.fixture
def postgres(tmp_path):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Configure TEST_DATABASE_URL para testar bloqueios reais do PostgreSQL.")
    # Dedicated schema, never drop or mutate existing application tables.
    admin = Database(url)
    schema = "test_" + uuid4().hex
    with admin.engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    db = Database(url)
    db.engine = db.engine.execution_options(schema_translate_map={None: schema})
    db.sessions.configure(bind=db.engine)
    Base.metadata.create_all(db.engine)
    settings = Settings(
        _env_file=None,
        database_url=url,
        jwt_secret="integration-secret-with-at-least-32-characters",
        openai_api_key="fake-key",
        openai_model="fake-model",
        storage_root=tmp_path / "storage",
    )
    storage = LocalStorage(settings.storage_root)
    with db.sessions.begin() as session:
        user = User(username="test", email="test@example.com", hashed_password="fake")
        session.add(user)
        session.flush()
        original = Resume(
            usuario_id=user.id,
            nome_arquivo="original.pdf",
            tipo="original",
            texto_extraido=SOURCE,
            texto_confirmado=True,
            descricao_vaga=JOB,
        )
        session.add(original)
        session.flush()
        user_id, resume_id = user.id, original.id
    yield db, settings, storage, user_id, resume_id
    db.engine.dispose()
    with admin.engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.engine.dispose()


def test_concurrent_quota_reservations_never_exceed_five(postgres):
    db, settings, storage, user_id, resume_id = postgres
    queue = QueueService(settings, storage)
    gate = Barrier(10)

    def reserve(index):
        gate.wait(timeout=10)
        with db.sessions() as session:
            try:
                queue.enqueue(
                    session,
                    user_id,
                    resume_id,
                    Operation.OPTIMIZATION,
                    idempotency_key=str(index),
                    consent=True,
                )
                return 202
            except AppError as error:
                return error.status

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(reserve, range(10)))
    assert results.count(202) == 5
    assert results.count(429) == 5
    with db.sessions() as session:
        assert queue.usage(session, user_id).usado == 5


def test_concurrent_idempotency_and_skip_locked_claims(postgres):
    db, settings, storage, user_id, resume_id = postgres
    queue = QueueService(settings, storage)
    gate = Barrier(5)

    def reserve(index):
        gate.wait(timeout=10)
        with db.sessions() as session:
            return queue.enqueue(
                session,
                user_id,
                resume_id,
                Operation.OPTIMIZATION,
                idempotency_key="same-key",
                consent=True,
            ).id

    with ThreadPoolExecutor(max_workers=5) as executor:
        ids = list(executor.map(reserve, range(5)))
    assert len(set(ids)) == 1
    worker = Worker(settings, db, storage, FakeOptimizer(), FakeCompiler())
    with db.sessions.begin() as session:
        # Hold the queue row; another worker must skip it instead of blocking or duplicating.
        session.get(Attempt, ids[0], with_for_update=True)
        with ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(worker.claim).result(timeout=5) is None
    first = worker.claim()
    assert first is not None
    assert worker.claim() is None


def test_database_rejects_cross_user_resume_reference(postgres):
    db, settings, storage, user_id, resume_id = postgres
    with db.sessions.begin() as session:
        other = User(username="other", email="other@example.com", hashed_password="fake")
        session.add(other)
        session.flush()
        other_id = other.id
    with pytest.raises(IntegrityError), db.sessions.begin() as session:
        session.add(
            Attempt(
                usuario_id=other_id,
                curriculo_id=resume_id,
                tipo_operacao=Operation.OPTIMIZATION,
                request_hash="a" * 64,
                status=Status.PENDING,
            )
        )
