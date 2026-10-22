from datetime import timedelta

import jwt

from app.infrastructure.models import utcnow
from tests.conftest import JOB, docx_bytes, enqueue


def test_auth_normalization_invalid_login_and_duplicates(client, settings):
    data = {"username": "TestUser", "email": "TEST@example.com", "password": " with spaces "}
    registered = client.post("/v1/auth/register", json=data)
    assert registered.status_code == 201
    assert registered.json()["username"] == "testuser"
    assert "password" not in registered.text
    assert client.post("/v1/auth/register", json=data).status_code == 409
    assert (
        client.post(
            "/v1/auth/token", data={"username": "TEST@example.com", "password": " with spaces "}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/auth/token", data={"username": "testuser", "password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/v1/auth/token", data={"username": "nonexistent", "password": "wrong"}
        ).status_code
        == 401
    )
    expired = jwt.encode(
        {
            "sub": registered.json()["id"],
            "iat": utcnow() - timedelta(hours=2),
            "exp": utcnow() - timedelta(hours=1),
            "iss": settings.jwt_issuer,
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    assert (
        client.get("/v1/auth/me", headers={"Authorization": "Bearer " + expired}).status_code == 401
    )


def test_upload_must_be_confirmed_and_validation_does_not_echo_secrets(client, auth):
    result = client.post(
        "/v1/curriculos",
        headers=auth,
        files={"arquivo": ("../../user.docx", docx_bytes())},
        data={"descricao_vaga": JOB},
    )
    assert result.status_code == 201
    assert result.json()["nome_arquivo"] == "user.docx"
    assert enqueue(client, auth, result.json()["id"]).status_code == 422
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
    invalid = client.post("/v1/auth/register", json={"password": "SENSITIVE-SECRET"})
    assert invalid.status_code == 422 and "SENSITIVE-SECRET" not in invalid.text


def test_request_limit_and_openapi_contract(client):
    response = client.post(
        "/v1/curriculos", content=b"not parsed", headers={"Content-Length": "99999999"}
    )
    assert response.status_code == 413
    schema = client.get("/openapi.json").json()
    assert "/v1/curriculos/{resume_id}/preview" in schema["paths"]
    assert "OAuth2PasswordBearer" in schema["components"]["securitySchemes"]


def test_request_limit_without_content_length(client):
    def chunks():
        yield b"{" + b" " * 11_000_000

    response = client.post(
        "/v1/auth/register", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413
