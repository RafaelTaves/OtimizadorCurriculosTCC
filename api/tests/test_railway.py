import io
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.application import create_app
from app.config import Settings
from app.infrastructure.storage import S3Storage, create_storage
from app.service.errors import AppError


@pytest.mark.parametrize("prefix", ["postgres://", "postgresql://", "postgresql+psycopg://"])
def test_railway_database_url_uses_installed_driver(settings, prefix):
    config = Settings(
        _env_file=None,
        jwt_secret=settings.jwt_secret,
        database_url=prefix + "user:p%40ss@db.railway.internal:5432/app",
    )
    assert config.database_url == "postgresql+psycopg://user:p%40ss@db.railway.internal:5432/app"


def test_s3_requires_credentials(settings):
    with pytest.raises(ValidationError, match="Configure S3_BUCKET"):
        Settings(_env_file=None, jwt_secret=settings.jwt_secret, storage_backend="s3")


@pytest.fixture
def s3(settings):
    config = Settings(
        _env_file=None,
        jwt_secret=settings.jwt_secret,
        storage_backend="s3",
        s3_bucket="test-bucket",
        s3_endpoint_url="https://storage.example.invalid",
        s3_access_key_id="test-key",
        s3_secret_access_key="test-secret",
    )
    storage = create_storage(config)
    assert isinstance(storage, S3Storage)
    assert storage.client.meta.config.s3["addressing_style"] == "virtual"
    with Stubber(storage.client) as stub:
        yield storage, stub
        stub.assert_no_pending_responses()


def test_s3_roundtrip_and_delete(s3):
    storage, stub = s3
    key = "objects/" + "a" * 32
    stub.add_response("put_object", {}, {"Bucket": "test-bucket", "Key": key, "Body": b"CV"})
    with patch("app.infrastructure.storage.uuid4") as identifier:
        identifier.return_value.hex = "a" * 32
        assert storage.put(b"CV") == key
    raw = io.BytesIO(b"CV")
    stream = StreamingBody(raw, 2)
    stub.add_response("get_object", {"Body": stream}, {"Bucket": "test-bucket", "Key": key})
    assert storage.read(key) == b"CV"
    assert raw.closed
    stub.add_response("delete_object", {}, {"Bucket": "test-bucket", "Key": key})
    storage.delete(key)


def test_s3_missing_key_and_invalid_key(s3):
    storage, stub = s3
    key = "objects/" + "a" * 32
    stub.add_client_error(
        "get_object",
        service_error_code="NoSuchKey",
        http_status_code=404,
        expected_params={"Bucket": "test-bucket", "Key": key},
    )
    with pytest.raises(AppError) as caught:
        storage.read(key)
    assert caught.value.status == 404
    for action in (storage.read, storage.delete):
        with pytest.raises(AppError):
            action("../../secrets")


def test_s3_purge_respects_protected_objects_and_pagination(s3):
    storage, stub = s3
    old = datetime.now(UTC) - timedelta(hours=2)
    protected = "temporary/" + "a" * 32
    expired = "temporary/" + "b" * 32
    recent = "temporary/" + "c" * 32
    stub.add_response(
        "list_objects_v2",
        {
            "IsTruncated": True,
            "NextContinuationToken": "next",
            "Contents": [{"Key": protected, "LastModified": old}],
        },
        {"Bucket": "test-bucket", "Prefix": "temporary/"},
    )
    stub.add_response(
        "list_objects_v2",
        {
            "IsTruncated": False,
            "Contents": [
                {"Key": expired, "LastModified": old},
                {"Key": recent, "LastModified": datetime.now(UTC)},
            ],
        },
        {"Bucket": "test-bucket", "Prefix": "temporary/", "ContinuationToken": "next"},
    )
    stub.add_response("delete_object", {}, {"Bucket": "test-bucket", "Key": expired})
    assert storage.purge(3600, {protected}) == 1


def test_readiness_requires_migrated_database(settings, database):
    with TestClient(create_app(settings, database=database)) as client:
        assert client.get("/ready").status_code == 200
    from app.infrastructure.database import Database

    empty = Database("sqlite://")
    with TestClient(create_app(settings, database=empty)) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/ready")
        assert response.status_code == 503
        assert "SELECT" not in response.text
    empty.engine.dispose()
