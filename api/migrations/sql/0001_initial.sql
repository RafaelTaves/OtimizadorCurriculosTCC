BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE TABLE usuarios (
    id UUID NOT NULL, 
    username VARCHAR(50) NOT NULL, 
    email VARCHAR(254) NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (email), 
    UNIQUE (username)
);

CREATE TABLE curriculos (
    id UUID NOT NULL, 
    usuario_id UUID NOT NULL, 
    curriculo_origem_id UUID, 
    tipo VARCHAR(12) NOT NULL, 
    nome_arquivo VARCHAR(255) NOT NULL, 
    arquivo_objeto_key VARCHAR(255), 
    pdf_objeto_key VARCHAR(255), 
    descricao_vaga TEXT, 
    texto_extraido TEXT, 
    texto_confirmado BOOLEAN NOT NULL, 
    latex_gerado TEXT, 
    latex_revisao INTEGER NOT NULL, 
    pdf_revisao INTEGER, 
    template_versao VARCHAR(30), 
    conteudo_estruturado JSONB, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_origem_tipo CHECK ((tipo = 'original' AND curriculo_origem_id IS NULL) OR (tipo = 'otimizado' AND curriculo_origem_id IS NOT NULL)), 
    FOREIGN KEY(curriculo_origem_id, usuario_id) REFERENCES curriculos (id, usuario_id), 
    FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
    UNIQUE (id, usuario_id)
);

CREATE INDEX ix_curriculos_usuario_data ON curriculos (usuario_id, created_at);

CREATE TABLE tentativas_geracao (
    id UUID NOT NULL, 
    usuario_id UUID NOT NULL, 
    curriculo_id UUID, 
    curriculo_gerado_id UUID, 
    tipo_operacao VARCHAR(12) NOT NULL, 
    idempotency_key VARCHAR(128), 
    request_hash VARCHAR(64) NOT NULL, 
    status VARCHAR(24) NOT NULL, 
    etapa VARCHAR(30) NOT NULL, 
    codigo_erro VARCHAR(60), 
    mensagem_erro VARCHAR(500), 
    modelo VARCHAR(100), 
    tokens_entrada INTEGER, 
    tokens_saida INTEGER, 
    entrada_temporaria_key VARCHAR(255), 
    resultado_temporario_key VARCHAR(255), 
    revisao_solicitada INTEGER, 
    executions INTEGER NOT NULL, 
    lease_token UUID, 
    lease_until TIMESTAMP WITH TIME ZONE, 
    available_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    started_at TIMESTAMP WITH TIME ZONE, 
    completed_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CHECK (status IN ('pendente','processando','aguardando_revisao','concluida','falhou','cancelada')), 
    CHECK (tipo_operacao IN ('otimizacao','preview','exportacao')), 
    FOREIGN KEY(curriculo_gerado_id, usuario_id) REFERENCES curriculos (id, usuario_id), 
    FOREIGN KEY(curriculo_id, usuario_id) REFERENCES curriculos (id, usuario_id), 
    FOREIGN KEY(usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE, 
    UNIQUE (usuario_id, idempotency_key)
);

CREATE INDEX ix_tentativas_cota ON tentativas_geracao (usuario_id, tipo_operacao, created_at, status);

CREATE INDEX ix_tentativas_fila ON tentativas_geracao (status, available_at);

ALTER TABLE "usuarios" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "curriculos" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "tentativas_geracao" ENABLE ROW LEVEL SECURITY;

ALTER TABLE "alembic_version" ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE usuarios, curriculos, tentativas_geracao, alembic_version FROM PUBLIC;

DO $migration$
            DECLARE client_role name;
            BEGIN
                FOR client_role IN
                    SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')
                LOOP
                    EXECUTE format(
                        'REVOKE ALL PRIVILEGES ON TABLE usuarios, curriculos, '
                        'tentativas_geracao, alembic_version FROM %I', client_role
                    );
                END LOOP;
            END $migration$;;

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

COMMIT;

