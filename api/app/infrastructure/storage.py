import os
import re
from pathlib import Path
from time import time
from uuid import uuid4

from app.service.errors import AppError


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
