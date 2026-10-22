from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://curriculo:curriculo@localhost:5432/curriculo"
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_issuer: str = "curriculo-api"
    token_minutes: int = Field(default=30, ge=1, le=120)
    openai_api_key: SecretStr | None = None
    openai_model: str = ""
    openai_timeout_seconds: int = Field(default=90, ge=1)
    storage_root: Path = Path("storage")
    monthly_optimization_limit: int = Field(default=5, ge=1)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    max_pages: int = Field(default=10, ge=1)
    max_extracted_chars: int = Field(default=60_000, ge=100)
    extraction_timeout_seconds: int = Field(default=15, ge=1)
    max_docx_unpacked_bytes: int = Field(default=40 * 1024 * 1024, ge=1)
    max_latex_bytes: int = Field(default=200_000, ge=100)
    preview_ttl_seconds: int = Field(default=3600, ge=60)
    previews_per_minute: int = Field(default=6, ge=1)
    max_active_compilations: int = Field(default=3, ge=1)
    compiler_image: str = "curriculo-tectonic:0.1"
    compiler_timeout_seconds: int = Field(default=40, ge=1)
    max_pdf_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    worker_poll_seconds: float = Field(default=2.0, gt=0)
    worker_lease_seconds: int = Field(default=300, ge=10)
    worker_max_executions: int = Field(default=3, ge=1)
    retry_base_seconds: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_worker_lease(self) -> Settings:
        longest_operation = max(self.openai_timeout_seconds, self.compiler_timeout_seconds + 10)
        if self.worker_lease_seconds <= longest_operation + 15:
            raise ValueError(
                "WORKER_LEASE_SECONDS deve exceder os timeouts de processamento em 15s"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
