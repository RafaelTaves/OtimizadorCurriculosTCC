# Validação das configurações Railway

Data: 12/11/2026. Branch de trabalho: `production`.

## Executado com sucesso

| Verificação | Resultado |
| --- | --- |
| Build Docker `front/Dockerfile` | Next.js standalone gerado; compilação e TypeScript concluídos |
| Build Docker `api/Dockerfile` | Imagem da API/worker de IA construída com lockfile congelado |
| Build Docker `api/docker/railway-pdf.Dockerfile` | Tectonic/cache e imagem do worker construídos |
| `pytest api/tests` | **131 passaram, 9 ignorados** por dependerem de flags/serviços de integração |
| `pytest -m postgres api/tests` com banco descartável | **6 passaram**, cobrindo migrações e concorrência |
| `docker run --network none ... /opt/check_sandbox.py` | PDF real com texto selecionável, acentos e URLs; cache offline; arquivo externo inacessível; UID sem privilégios; criação de socket bloqueada; binário protegido contra escrita |
| API em contêiner | `/ready` respondeu 200 por IPv4 e IPv6 depois de `alembic upgrade head` |
| Workers de produção | Ambos iniciaram; worker PDF publicou `compiler_sandbox_ready` |
| S3 pela rede | Gravação, leitura e exclusão via boto3 contra servidor Moto local |
| Frontend → API → Postgres/S3 | Cadastro, login, cookie HttpOnly/Secure, upload DOCX, extração, confirmação de texto e histórico com dados fictícios |
| Proteção de origem | Requisição com Origin incorreto retornou 403 |
| Fila PDF entre contêineres | Registro sintético enfileirado no Postgres; worker PDF leu LaTeX no S3 e gravou PDF válido no S3 |
| IaC | SDK oficial `railway@3.12.0` instalado com lockfile; TypeScript e avaliação local dos seis recursos passaram |
| Ruff nos arquivos Python adicionados/alterados | Passou |
| Formatação dos arquivos Python adicionados/alterados | Passou |
| Prettier do Next config e IaC | Passou |
| `git diff --check` | Passou |

As primeiras execuções de pytest no sandbox restrito do Windows ficaram bloqueadas. A suíte foi encerrada e executada novamente fora dessa restrição, com os resultados acima. O teste de fechamento do stream S3 foi corrigido para verificar o stream subjacente, que é o recurso fechado pelo context manager do botocore.

O smoke HTTP local usou uma origem HTTPS fictícia para validar a configuração do cookie, encaminhando o cookie explicitamente sobre o transporte HTTP local. Isso não é um teste de certificado TLS nem substitui o teste pelo domínio HTTPS do Railway.

O S3 de integração foi **simulado pelo Moto**; nenhum currículo real ou credencial de produção foi usado. O smoke da fila criou registros fictícios de proposta já revisada, sem solicitar geração à OpenAI. O teste real do compilador usou contêiner Linux sem modo privilegiado, sem Docker socket e sem rede.

## Limitações e pendências externas

- Nenhum recurso foi provisionado na conta Railway, nenhum domínio foi publicado e nenhum segredo real foi cadastrado.
- O plano/aplicação IaC remoto (`railway config plan/apply`) depende de autenticação e não foi executado. A checagem local validou tipos e a avaliação do arquivo com o SDK.
- O bucket real Railway, DNS privado Railway, certificado HTTPS e permissões do runtime Railway precisam ser conferidos no primeiro deploy. O worker faz uma compilação de verificação e falha se não conseguir aplicar chroot/seccomp; não executa LaTeX sem isolamento.
- Não houve chamada real à OpenAI, nem teste de cobrança/cota da conta externa. Faça o fluxo descrito no guia após configurar chave e modelo.
- A suíte geral de Ruff identifica problemas preexistentes em `api/app/api/routes.py` (ordem de imports e duas linhas longas). O mypy geral identifica uma subtração com `started_at` opcional em `api/app/service/worker.py:182`. Esses arquivos não foram alterados nesta configuração de deploy. As verificações dos arquivos novos/alterados passaram; isso não significa que o CI geral esteja integralmente verde.
- O build npm informou sete vulnerabilidades moderadas nas dependências existentes. Não foi executado `npm audit fix` nem alterada a stack para este deploy.

## Comandos reproduzíveis

Na raiz do projeto, com Docker Desktop em modo Linux:

```powershell
docker build -t curriculo-railway-api:test api
docker build -t curriculo-railway-front:test front
docker build -f api/docker/railway-pdf.Dockerfile -t curriculo-railway-pdf:test api
docker run --rm --network none --entrypoint python curriculo-railway-pdf:test /opt/check_sandbox.py
```

Com Python 3.14 e uv instalados:

```powershell
uv sync --project api --frozen --group dev
uv run --project api pytest -q api/tests
```

Para os seis testes PostgreSQL, defina `TEST_DATABASE_URL` apontando para um **banco de teste**, com prefixo `postgresql+psycopg://`, antes de executar `pytest -m postgres`. Não use dados de produção.

Para conferir tipos da configuração IaC com o TypeScript já instalado no frontend:

```powershell
npm ci --prefix .railway
node front/node_modules/typescript/bin/tsc .railway/railway.ts --noEmit --module nodenext --target es2022 --skipLibCheck
```
