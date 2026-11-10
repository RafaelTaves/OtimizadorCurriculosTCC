"""Export the existing FastAPI contract without running a server or reading .env."""
import json
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "api"))
from app.api.application import create_app  # noqa: E402
from app.config import Settings  # noqa: E402

temporary_root = root / ".test-tmp"
temporary_root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="openapi-", dir=temporary_root) as temporary:
    app = create_app(Settings(
        _env_file=None,
        jwt_secret="schema-export-only-not-an-authentication-secret",
        storage_root=Path(temporary),
    ))
    (root / "front/openapi.json").write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
