import io
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.api.application import create_app
from app.config import Settings
from app.infrastructure.database import Base, Database
from app.infrastructure.models import Resume
from app.infrastructure.storage import LocalStorage
from app.presentation.schemas import Fact, Proposal, ResumeContent
from app.service.ports import ModelResult
from app.service.proposals import render_content
from app.service.worker import Worker

SOURCE = (
    "Ana Silva\nana@example.com\nEstudante de computação. Projeto acadêmico em Python "
    "e PostgreSQL em 2024. Desenvolvimento de API para biblioteca."
)
JOB = "Vaga de estágio em desenvolvimento de API com Python e PostgreSQL."


def docx_bytes(text: str = SOURCE) -> bytes:
    document = Document()
    document.add_paragraph(text)
    stream = io.BytesIO()
    document.save(stream)
    return stream.getvalue()


def proposal() -> Proposal:
    content = ResumeContent(
        contato=[Fact(texto="Ana Silva", trecho_fonte="Ana Silva")],
        resumo=Fact(
            texto="Projeto acadêmico em Python", trecho_fonte="Projeto acadêmico em Python"
        ),
        formacao=[],
        experiencias=[],
        projetos=[],
        competencias=[Fact(texto="Python", trecho_fonte="Python")],
    )
    return Proposal(
        curriculo=content,
        latex_gerado=render_content(content),
        alteracoes=[],
        palavras_chave_usadas=[],
        lacunas=[],
    )


class FakeOptimizer:
    calls = 0

    def optimize(self, text: str, job: str) -> ModelResult:
        self.calls += 1
        return ModelResult(proposal(), "fake-model", 100, 200)


class FakeCompiler:
    calls = 0

    def compile(self, latex: str) -> bytes:
        self.calls += 1
        return b"%PDF-1.7\nfake selectable test PDF"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        database_url="sqlite:///" + str(tmp_path / "test.db"),
        jwt_secret="unit-test-secret-with-at-least-32-characters",
        openai_api_key="fake-key",
        openai_model="fake-model",
        storage_root=tmp_path / "objects",
    )


@pytest.fixture
def database(settings: Settings) -> Iterator[Database]:
    db = Database(settings.database_url)

    @event.listens_for(db.engine, "connect")
    def foreign_keys(connection: Any, record: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(db.engine)
    yield db
    db.engine.dispose()


@pytest.fixture
def client(settings: Settings, database: Database) -> Iterator[TestClient]:
    with TestClient(create_app(settings, database=database)) as test_client:
        yield test_client


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return register(client, "ana")


def register(client: TestClient, name: str) -> dict[str, str]:
    result = client.post(
        "/v1/auth/register",
        json={
            "username": name,
            "email": name + "@example.com",
            "password": "very-secret-password",
        },
    )
    assert result.status_code == 201, result.text
    result = client.post(
        "/v1/auth/token", data={"username": name, "password": "very-secret-password"}
    )
    assert result.status_code == 200, result.text
    return {"Authorization": "Bearer " + result.json()["access_token"]}


def upload_confirm(client: TestClient, auth: dict[str, str]) -> str:
    result = client.post(
        "/v1/curriculos",
        headers=auth,
        files={"arquivo": ("curriculo.docx", docx_bytes())},
        data={"descricao_vaga": JOB},
    )
    assert result.status_code == 201, result.text
    resume_id = result.json()["id"]
    result = client.patch(
        f"/v1/curriculos/{resume_id}/texto-extraido", headers=auth, json={"texto": SOURCE}
    )
    assert result.status_code == 200, result.text
    return str(resume_id)


def enqueue(client: TestClient, auth: dict[str, str], resume_id: str, key: str = "test-key") -> Any:
    return client.post(
        f"/v1/curriculos/{resume_id}/otimizacoes",
        headers={**auth, "Idempotency-Key": key},
        json={"consentimento_envio_openai": True},
    )


@pytest.fixture
def worker(settings: Settings, database: Database) -> Worker:
    return Worker(
        settings, database, LocalStorage(settings.storage_root), FakeOptimizer(), FakeCompiler()
    )


def generated_resume(database: Database, user_id: UUID) -> UUID:
    with database.sessions.begin() as session:
        original = Resume(usuario_id=user_id, tipo="original", nome_arquivo="original.pdf")
        session.add(original)
        session.flush()
        resume = Resume(
            usuario_id=user_id,
            curriculo_origem_id=original.id,
            tipo="otimizado",
            nome_arquivo="curriculo.tex",
            latex_gerado=proposal().latex_gerado,
            latex_revisao=1,
        )
        session.add(resume)
        session.flush()
        return resume.id
