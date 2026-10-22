from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import UTCDateTime


def utcnow() -> datetime:
    return datetime.now(UTC)


class Operation(StrEnum):
    OPTIMIZATION = "otimizacao"
    PREVIEW = "preview"
    EXPORT = "exportacao"


class Status(StrEnum):
    PENDING = "pendente"
    PROCESSING = "processando"
    REVIEW = "aguardando_revisao"
    COMPLETED = "concluida"
    FAILED = "falhou"
    CANCELLED = "cancelada"


QUOTA_STATUSES = (Status.PENDING, Status.PROCESSING, Status.REVIEW, Status.COMPLETED)
ACTIVE_STATUSES = (Status.PENDING, Status.PROCESSING)


class User(Base):
    __tablename__ = "usuarios"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Resume(Base):
    __tablename__ = "curriculos"
    __table_args__ = (
        UniqueConstraint("id", "usuario_id"),
        ForeignKeyConstraint(
            ["curriculo_origem_id", "usuario_id"], ["curriculos.id", "curriculos.usuario_id"]
        ),
        CheckConstraint(
            "(tipo = 'original' AND curriculo_origem_id IS NULL) OR "
            "(tipo = 'otimizado' AND curriculo_origem_id IS NOT NULL)",
            name="ck_origem_tipo",
        ),
        Index("ix_curriculos_usuario_data", "usuario_id", "created_at"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    curriculo_origem_id: Mapped[UUID | None] = mapped_column(Uuid)
    tipo: Mapped[str] = mapped_column(String(12), default="original")
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    arquivo_objeto_key: Mapped[str | None] = mapped_column(String(255))
    pdf_objeto_key: Mapped[str | None] = mapped_column(String(255))
    descricao_vaga: Mapped[str | None] = mapped_column(Text)
    texto_extraido: Mapped[str | None] = mapped_column(Text)
    texto_confirmado: Mapped[bool] = mapped_column(default=False)
    latex_gerado: Mapped[str | None] = mapped_column(Text)
    latex_revisao: Mapped[int] = mapped_column(Integer, default=0)
    pdf_revisao: Mapped[int | None] = mapped_column(Integer)
    template_versao: Mapped[str | None] = mapped_column(String(30))
    conteudo_estruturado: Mapped[dict[str, object] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql")
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class Attempt(Base):
    __tablename__ = "tentativas_geracao"
    __table_args__ = (
        UniqueConstraint("usuario_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["curriculo_id", "usuario_id"], ["curriculos.id", "curriculos.usuario_id"]
        ),
        ForeignKeyConstraint(
            ["curriculo_gerado_id", "usuario_id"], ["curriculos.id", "curriculos.usuario_id"]
        ),
        Index("ix_tentativas_cota", "usuario_id", "tipo_operacao", "created_at", "status"),
        Index("ix_tentativas_fila", "status", "available_at"),
        CheckConstraint("tipo_operacao IN ('otimizacao','preview','exportacao')"),
        CheckConstraint(
            "status IN ('pendente','processando','aguardando_revisao',"
            "'concluida','falhou','cancelada')"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    usuario_id: Mapped[UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"))
    # Nullable after deletion: preserve only technical quota/audit records until account deletion.
    curriculo_id: Mapped[UUID | None] = mapped_column(Uuid)
    curriculo_gerado_id: Mapped[UUID | None] = mapped_column(Uuid)
    tipo_operacao: Mapped[str] = mapped_column(String(12))
    idempotency_key: Mapped[str | None] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default=Status.PENDING)
    etapa: Mapped[str] = mapped_column(String(30), default="fila")
    codigo_erro: Mapped[str | None] = mapped_column(String(60))
    mensagem_erro: Mapped[str | None] = mapped_column(String(500))
    modelo: Mapped[str | None] = mapped_column(String(100))
    tokens_entrada: Mapped[int | None] = mapped_column(Integer)
    tokens_saida: Mapped[int | None] = mapped_column(Integer)
    entrada_temporaria_key: Mapped[str | None] = mapped_column(String(255))
    resultado_temporario_key: Mapped[str | None] = mapped_column(String(255))
    revisao_solicitada: Mapped[int | None] = mapped_column(Integer)
    executions: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    available_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
