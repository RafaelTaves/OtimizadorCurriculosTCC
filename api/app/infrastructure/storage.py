import os
import re
from pathlib import Path
from time import time
from uuid import uuid4

from app.config import Settings
from app.service.errors import AppError
from app.service.ports import Storage


class LocalStorage:
    """Private objects; identifiers never incorporate client filenames."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"(?:objects|temporary)/[a-f0-9]{32}", key):
            raise AppError("objeto_invalido", "Objeto inexistente.", 404)
        path = self.root / key
        if not path.resolve().is_relative_to(self.root):
            raise AppError("objeto_invalido", "Objeto inexistente.", 404)
        return path

    def put(self, data: bytes, *, temporary: bool = False) -> str:
        prefix = "temporary" if temporary else "objects"
        key = f"{prefix}/{uuid4().hex}"
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as output:
            output.write(data)
        return key

    def read(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as exc:
            raise AppError("objeto_inexistente", "Arquivo indisponível ou expirado.", 404) from exc

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def purge(self, ttl_seconds: int, protected: set[str] | None = None) -> int:
        count = 0
        for path in (self.root / "temporary").glob("*"):
            if f"temporary/{path.name}" in (protected or set()):
                continue
            if path.is_file() and path.stat().st_mtime < time() - ttl_seconds:
                path.unlink(missing_ok=True)
                count += 1
        return count


class S3Storage:
    """Private shared objects; downloads still pass through API authorization."""

    def __init__(self, settings: Settings) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=(
                settings.s3_access_key_id.get_secret_value() if settings.s3_access_key_id else None
            ),
            aws_secret_access_key=(
                settings.s3_secret_access_key.get_secret_value()
                if settings.s3_secret_access_key
                else None
            ),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": settings.s3_addressing_style},
                connect_timeout=5,
                read_timeout=20,
                retries={"mode": "standard", "total_max_attempts": 2},
            ),
        )

    @staticmethod
    def _validate(key: str) -> str:
        if not re.fullmatch(r"(?:objects|temporary)/[a-f0-9]{32}", key):
            raise AppError("objeto_invalido", "Objeto inexistente.", 404)
        return key

    def put(self, data: bytes, *, temporary: bool = False) -> str:
        key = f"{'temporary' if temporary else 'objects'}/{uuid4().hex}"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return key

    def read(self, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._validate(key))
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                raise AppError(
                    "objeto_inexistente", "Arquivo indisponível ou expirado.", 404
                ) from exc
            raise
        with response["Body"] as body:
            return bytes(body.read())

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._validate(key))

    def purge(self, ttl_seconds: int, protected: set[str] | None = None) -> int:
        count = 0
        cutoff = time() - ttl_seconds
        pages = self.client.get_paginator("list_objects_v2")
        for page in pages.paginate(Bucket=self.bucket, Prefix="temporary/"):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if (
                    re.fullmatch(r"temporary/[a-f0-9]{32}", key)
                    and key not in (protected or set())
                    and obj["LastModified"].timestamp() < cutoff
                ):
                    self.delete(key)
                    count += 1
        return count


def create_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    return LocalStorage(settings.storage_root)
