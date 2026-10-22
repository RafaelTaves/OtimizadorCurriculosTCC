# API de otimização de currículos

Monólito Python 3.14/FastAPI, organizado nas camadas `app/api` (HTTP e dependências), `app/service` (regras e portas), `app/presentation` (contratos) e `app/infrastructure` (PostgreSQL, extração, OpenAI, arquivos e compilação). `tests` cobre regras, rotas e integrações. Não inclui frontend; os contratos atendem ao editor LaTeX com visualizador de PDF.

As três entidades persistidas são `usuarios`, `curriculos` e `tentativas_geracao`. A mesma tabela de tentativas implementa a fila, o histórico e a cota. As migrações são explícitas e versionadas com Alembic. O lockfile `uv.lock` fixa as dependências diretas e transitivas.

## Executar com Docker Desktop

Instale Docker Desktop com contêineres Linux. Na pasta `api`:

```powershell
Copy-Item .env.example .env
```

Edite `.env`: defina `JWT_SECRET` aleatório com ao menos 32 caracteres, `OPENAI_API_KEY` e `OPENAI_MODEL` compatível com Structured Outputs. A API inicia sem chave/modelo de IA, mas recusa novas otimizações com `503` até a configuração estar completa. Não é feita chamada de IA na inicialização.

```powershell
docker build -f docker/compiler.Dockerfile -t curriculo-tectonic:0.1 .
docker compose up --build -d
```

A imagem Tectonic fornecida destina-se a Linux x86_64. A primeira construção baixa o binário e os pacotes do template; compilações de usuários rodam offline usando somente o cache. Pacotes adicionais fora desse cache exigem reconstruir a imagem. O worker recebe acesso ao Docker do host para criar um contêiner descartável por compilação; use essa composição apenas na máquina de desenvolvimento confiável. O compilador não recebe o socket, variáveis de ambiente da API, diretórios compartilhados nem credenciais.

Acesse [Swagger](http://localhost:8000/docs), [OpenAPI](http://localhost:8000/openapi.json) e [health](http://localhost:8000/health). A composição espera o PostgreSQL ficar saudável e as migrações terminarem antes de iniciar API/worker. O banco e os arquivos ficam em volumes privados. `docker compose down` preserva os dados.

## Executar API e worker pelo terminal

Instale Python 3.14 e uv. Configure `.env` e um PostgreSQL; Docker continua necessário para compilar LaTeX.

```powershell
uv sync --frozen
docker compose up -d db
uv run alembic upgrade head
uv run uvicorn app.main:create_app --factory --reload
```

Em outro terminal, na mesma pasta e com o mesmo `.env`:

```powershell
uv run python -m app.worker
```

O diretório `storage` é privado e nunca é servido estaticamente. Não o coloque na pasta pública de um servidor web. Esta instalação foi projetada para uso local do TCC, sem implantação em produção.

## Usar o fluxo no Swagger

1. Cadastre em `POST /v1/auth/register`. Faça login em **Authorize** com username ou e-mail e senha. Tokens duram 30 minutos; não há refresh token neste MVP.
2. Envie `arquivo` PDF/DOCX e `descricao_vaga` em `POST /v1/curriculos`. PDF deve conter texto selecionável. Revise o texto retornado.
3. Confirme ou corrija o texto com `PATCH /v1/curriculos/{id}/texto-extraido`, JSON `{"texto":"..."}`. Essa etapa é obrigatória, mesmo sem correções.
4. Inicie `POST /v1/curriculos/{id}/otimizacoes` com `Idempotency-Key` exclusivo e `{"consentimento_envio_openai":true}`. O texto confirmado e a vaga serão enviados à OpenAI; a aplicação usa `store=false`, que não equivale a retenção zero do provedor.
5. Consulte a URL em `Location`/`acompanhamento`. O worker entrega `aguardando_revisao`, proposta, evidências, alterações, lacunas e `.tex`. O `curriculo_gerado_id` identifica a versão para o editor. Confira o conteúdo e registre a revisão em `POST /v1/otimizacoes/{id}/confirmacao`.
6. Consulte `GET /v1/curriculos/{id}` para receber código e `ETag`. Use `POST /v1/curriculos/{id}/preview` com `{"latex":"..."}` para uma prévia sem salvar ou chamar a IA. Consulte `/v1/previews/{id}` e o endereço autenticado `download_pdf` para visualizar.
7. Salve com `PUT /v1/curriculos/{id}/latex`, JSON `{"latex":"..."}` e `If-Match: "1"` (aspas fazem parte do ETag). A API retorna uma nova revisão. ETag antigo recebe `412`; ausente, `428`. Editar invalida o PDF anterior e a revisão factual automática não abrange alterações manuais.
8. Chame `POST /v1/curriculos/{id}/renderizacoes` para compilar a revisão salva. Acompanhe em `/v1/renderizacoes/{id}`. Baixe `/v1/curriculos/{id}/download?formato=pdf` ou `formato=tex`. Se o código mudar durante a compilação, o resultado antigo não será publicado como atual.
9. Consulte histórico paginado com `GET /v1/curriculos?pagina=1&tamanho=20` e consumo em `GET /v1/uso`. Exclua em `DELETE /v1/curriculos/{id}`.

Todas as rotas de dados exigem Bearer token e verificam a propriedade. Recursos de outra conta retornam `404`. O download de PDF final exige renderização da revisão atual; o download `.tex` entrega o código salvo.

## Regras definidas

- **5 otimizações por usuário por mês civil em UTC**, renovando no primeiro dia às 00:00 UTC. Reservas pendentes/em processamento, propostas aguardando revisão e gerações concluídas contam no mês de criação da tentativa. Requisições simultâneas bloqueiam a linha do usuário antes da contagem/reserva no PostgreSQL. Limite retorna `429`, próximo reinício e `Retry-After`.
- Falhas de validação não reservam cota. Falha definitiva interna, do provedor ou da validação da proposta libera a reserva. Falhas transitórias têm backoff e até três execuções da mesma tentativa, sem consumir novas reservas. Excluir uma geração concluída não reembolsa a cota; o registro técnico sem currículo permanece para auditoria.
- A chave de idempotência é única por usuário. Reenvio com a mesma entrada devolve a mesma tentativa, inclusive após falha; entrada diferente com a mesma chave recebe `409`. Para uma nova tentativa, use outra chave. O worker usa bloqueio `SKIP LOCKED`, prazo de execução e token por execução para impedir publicação duplicada ou por um worker antigo.
- As chamadas ao provedor podem ser repetidas após falha de conexão ou interrupção do worker; uma transação local não garante cobrança única no provedor. A cota da aplicação continua usando uma única tentativa.
- Originais, versões, LaTeX, PDF e vagas são mantidos **sem prazo de expurgo**, até exclusão solicitada. Excluir um original remove também suas versões e os arquivos associados. Excluir uma versão remove apenas ela. Uma tentativa em execução é cancelada e não pode republicar arquivos após exclusão.
- Prévias são temporárias: expiram em uma hora, retornam `410` depois disso e são expurgadas pelo worker. Entradas de fila são snapshots temporários apagados ao terminar; entradas ainda aguardando execução são protegidas do expurgo. Códigos de prévia e exportação não consomem cota de IA. Há limites de frequência e de compilações pendentes por conta.
- Upload: até 10 MB, PDF com até 10 páginas, texto até 60000 caracteres, DOCX até 40 MB descompactados, descrição da vaga de 30 a 20000 caracteres, LaTeX até 200000 bytes. A extração usa processo separado com timeout; no contêiner Linux há limites de memória e CPU. DOCX não tem paginação estável sem renderização; aplica-se limite de conteúdo, sem estimar páginas.
- LaTeX livre é compilado com `--untrusted`, contêiner sem rede, root somente leitura, usuário sem privilégios, CPU/memória/processos/arquivos/tempo limitados e sem mounts. Diagnósticos externos incluem somente mensagem e linha de erro permitida, nunca o log bruto.
- A proposta inicial exige evidência literal para cada fato, preserva datas e números, mantém campos de identidade/competências literais e confere o `.tex` inteiro contra o preenchimento determinístico do template. Isso reduz introdução de fatos, mas não prova a veracidade de toda paráfrase; revisão humana é necessária.

## Testes e qualidade

```powershell
uv run pytest -q
uv run ruff check app tests migrations docker evaluation
uv run ruff format --check app tests migrations docker evaluation
uv run mypy app
```

Testes unitários e de rotas usam SQLite com integridade referencial e simulam OpenAI/compilação. Os testes de extração executam parsers reais. Não usam chave de IA nem fazem chamadas pagas.

Para testar concorrência, idempotência, `SKIP LOCKED` e integridade no banco real, use um PostgreSQL de testes com permissão para criar schemas:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://curriculo:curriculo@localhost:5432/curriculo'
uv run pytest -q -m postgres
$env:RUN_COMPILER_TESTS='1'
uv run pytest -q -m compiler
```

Esses testes ficam explicitamente ignorados se as dependências não forem disponibilizadas. A CI em `.github/workflows/api.yml` executa migrações de ida e volta, verificação de drift, tipagem, lint, testes com PostgreSQL e compilação real isolada. Consulte `evaluation/README.md` para dados sintéticos, rubrica e geração dos relatórios do TCC. Ainda será necessário executar a avaliação real e humana para produzir conclusões acadêmicas.

Integração baseada na [documentação oficial de Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) e no [modo não confiável do Tectonic](https://tectonic-typesetting.github.io/book/latest/v2cli/compile.html).
