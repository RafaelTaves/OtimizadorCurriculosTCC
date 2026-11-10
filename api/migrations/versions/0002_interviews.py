"""Optional interviews, per-operation idempotency and source-aware generation."""

import sqlalchemy as sa
from alembic import context, op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def json_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "sessoes_complementacao",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("curriculo_id", sa.Uuid()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("revisao", sa.Integer(), nullable=False),
        sa.Column("rodada_atual", sa.Integer(), nullable=False),
        sa.Column("texto_confirmado_snapshot", sa.Text()),
        sa.Column("descricao_vaga_snapshot", sa.Text()),
        sa.Column("contexto_hash", sa.String(64), nullable=False),
        sa.Column("complementos", json_type(), nullable=False),
        sa.Column("conflitos", json_type(), nullable=False),
        sa.Column("resolucoes", json_type(), nullable=False),
        sa.Column("consentimento_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consentimento_versao", sa.String(60), nullable=False),
        sa.Column("confirmado_em", sa.DateTime(timezone=True)),
        sa.Column("codigo_erro", sa.String(60)),
        sa.Column("mensagem_erro", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("id", "usuario_id"),
        sa.UniqueConstraint("id", "curriculo_id", "usuario_id"),
        sa.ForeignKeyConstraint(
            ["curriculo_id", "usuario_id"], ["curriculos.id", "curriculos.usuario_id"]
        ),
        sa.CheckConstraint(
            "status IN ('analisando','aguardando_respostas','aguardando_confirmacao',"
            "'confirmada','falhou','cancelada','expirada')",
            name="ck_sessao_status",
        ),
    )
    op.create_index(
        "ix_sessoes_usuario_data", "sessoes_complementacao", ["usuario_id", "created_at"]
    )
    op.create_table(
        "rodadas_complementacao",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sessao_id",
            sa.Uuid(),
            sa.ForeignKey("sessoes_complementacao.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("perguntas", json_type(), nullable=False),
        sa.Column("respostas", json_type(), nullable=False),
        sa.Column("complemento_livre", sa.Text()),
        sa.Column("complemento_livre_id", sa.Uuid()),
        sa.Column("acao_apos_respostas", sa.String(12)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("sessao_id", "numero"),
        sa.UniqueConstraint("id", "sessao_id"),
    )
    op.create_table(
        "registros_idempotencia",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sessao_id", sa.Uuid()),
        sa.Column("chave", sa.String(128), nullable=False),
        sa.Column("operacao", sa.String(32), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resposta", json_type()),
        sa.Column("status_http", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("usuario_id", "chave"),
        sa.ForeignKeyConstraint(
            ["sessao_id", "usuario_id"],
            ["sessoes_complementacao.id", "sessoes_complementacao.usuario_id"],
        ),
    )
    op.create_index(
        "ix_idempotencia_limite", "registros_idempotencia", ["usuario_id", "operacao", "created_at"]
    )
    connection = op.get_bind()
    sqlite = connection.dialect.name == "sqlite"
    previous = None
    if sqlite:
        previous = sa.Table("tentativas_geracao", sa.MetaData(), autoload_with=connection)
        for constraint in list(previous.constraints):
            if isinstance(constraint, sa.CheckConstraint) and "tipo_operacao" in str(
                constraint.sqltext
            ):
                previous.constraints.remove(constraint)
            elif isinstance(constraint, sa.CheckConstraint) and constraint.name is None:
                constraint.name = "tentativas_geracao_status_check"
    elif context.is_offline_mode():
        op.drop_constraint(
            "tentativas_geracao_tipo_operacao_check", "tentativas_geracao", type_="check"
        )
    else:
        for constraint in sa.inspect(connection).get_check_constraints("tentativas_geracao"):
            if "tipo_operacao" in constraint["sqltext"]:
                op.drop_constraint(constraint["name"], "tentativas_geracao", type_="check")
    with op.batch_alter_table("tentativas_geracao", copy_from=previous) as batch:
        batch.alter_column(
            "tipo_operacao", type_=sa.String(32), existing_type=sa.String(12), nullable=False
        )
        batch.add_column(sa.Column("sessao_complementacao_id", sa.Uuid()))
        batch.add_column(sa.Column("rodada_complementacao_id", sa.Uuid()))
        batch.add_column(sa.Column("sessao_revisao_esperada", sa.Integer()))
        batch.add_column(
            sa.Column("execucoes_analise", json_type(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column("execucoes_ciclo", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_check_constraint(
            "ck_tentativas_operacao",
            "tipo_operacao IN ('otimizacao','preview','exportacao','analise_complementacao')",
        )
        batch.create_foreign_key(
            "fk_tentativa_sessao_dono",
            "sessoes_complementacao",
            ["sessao_complementacao_id", "curriculo_id", "usuario_id"],
            ["id", "curriculo_id", "usuario_id"],
        )
        batch.create_foreign_key(
            "fk_tentativa_rodada_sessao",
            "rodadas_complementacao",
            ["rodada_complementacao_id", "sessao_complementacao_id"],
            ["id", "sessao_id"],
        )
    # Defaults only backfill older technical records; app defaults remain authoritative.
    with op.batch_alter_table("tentativas_geracao") as batch:
        batch.alter_column("execucoes_analise", server_default=None)
        batch.alter_column("execucoes_ciclo", server_default=None)
    op.create_index(
        "uq_otimizacao_sessao",
        "tentativas_geracao",
        ["sessao_complementacao_id"],
        unique=True,
        postgresql_where=sa.text("tipo_operacao = 'otimizacao'"),
        sqlite_where=sa.text("tipo_operacao = 'otimizacao'"),
    )
    if not sqlite:
        for table in ("sessoes_complementacao", "rodadas_complementacao", "registros_idempotencia"):
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
            op.execute(sa.text(f'REVOKE ALL PRIVILEGES ON TABLE "{table}" FROM PUBLIC'))
        op.execute(
            sa.text("""DO $migration$ DECLARE r name; BEGIN
            FOR r IN SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated') LOOP
                EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE sessoes_complementacao, '
                    'rodadas_complementacao, registros_idempotencia FROM %I', r);
            END LOOP; END $migration$;""")
        )


def downgrade() -> None:
    # Never silently destroy interview history or technical quota accounting.
    count = op.get_bind().scalar(sa.text("SELECT count(*) FROM sessoes_complementacao"))
    analyses = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM tentativas_geracao WHERE tipo_operacao = 'analise_complementacao'"
        )
    )
    if count or analyses:
        raise RuntimeError(
            "Downgrade exige exportar/remover explicitamente as sessões e análises primeiro"
        )
    op.drop_index("uq_otimizacao_sessao", table_name="tentativas_geracao")
    with op.batch_alter_table("tentativas_geracao") as batch:
        batch.drop_constraint("fk_tentativa_rodada_sessao", type_="foreignkey")
        batch.drop_constraint("fk_tentativa_sessao_dono", type_="foreignkey")
        batch.drop_constraint("ck_tentativas_operacao", type_="check")
        for column in (
            "sessao_complementacao_id",
            "rodada_complementacao_id",
            "sessao_revisao_esperada",
            "execucoes_analise",
            "execucoes_ciclo",
        ):
            batch.drop_column(column)
        batch.alter_column("tipo_operacao", type_=sa.String(12), existing_type=sa.String(32))
        batch.create_check_constraint(
            "tentativas_geracao_tipo_operacao_check",
            "tipo_operacao IN ('otimizacao','preview','exportacao')",
        )
    op.drop_index("ix_idempotencia_limite", table_name="registros_idempotencia")
    op.drop_table("registros_idempotencia")
    op.drop_table("rodadas_complementacao")
    op.drop_index("ix_sessoes_usuario_data", table_name="sessoes_complementacao")
    op.drop_table("sessoes_complementacao")
