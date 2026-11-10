# Front-end do otimizador de currículos

Estrutura inicial conforme `../plano-front.md`: Next.js 16 (App Router), React 19,
TypeScript strict, Tailwind CSS 4 e componentes locais no padrão shadcn/ui com
Radix. Node.js **24 LTS** e npm; dependências fixadas pelo `package-lock.json`.

## Executar

Na pasta `front`:

```powershell
npm ci
Copy-Item .env.example .env.local
npm run dev
```

Abra <http://localhost:3000>. A raiz encaminha para o painel ou login.
Cadastre uma conta em `/cadastro`; não existem credenciais padrão.

| Variável, somente no servidor | Padrão local            | Uso                              |
| ----------------------------- | ----------------------- | -------------------------------- |
| `API_BASE_URL`                | `http://127.0.0.1:8000` | FastAPI existente                |
| `APP_ORIGIN`                  | `http://localhost:3000` | Origem exata aceita nas mutações |

Use a mesma origem no navegador e na configuração (inclusive porta). Ao mudar
a porta, atualize `APP_ORIGIN`. HTTP destina-se somente ao desenvolvimento local.
Sob HTTPS, o cookie recebe `Secure`. Nunca colocar segredos em variáveis
`NEXT_PUBLIC_`. O front não precisa de chave OpenAI nem do segredo JWT.

A API deve estar ativa conforme [`../api/README.md`](../api/README.md), com
PostgreSQL e migrações. O worker processa análise, otimização, prévia e PDF; o
compilador isolado é necessário para as operações LaTeX. A chave OpenAI e o
modelo são configurados somente na API. O front sozinho mostra o login e não
inventa dados.

### Executar a jornada local

Na pasta `api`, configure `.env` com banco e segredo JWT. Para iniciar banco,
migrações, API e worker pela composição documentada:

```powershell
Copy-Item .env.example .env
# Edite .env e configure DATABASE_URL/JWT_SECRET e, para usar a IA, OPENAI_API_KEY/OPENAI_MODEL.
docker build -f docker/compiler.Dockerfile -t curriculo-tectonic:0.1 .
docker compose up --build -d
```

Na pasta `front`, use a mesma origem em `APP_ORIGIN` e no navegador:

```powershell
Copy-Item .env.example .env.local
npm ci
npm run dev
```

A migração `0002` habilita as sessões de entrevista. A extração aceita PDF com
texto selecionável e DOCX; OCR não está disponível. Consentimentos da interface
precedem cada envio de conteúdo à IA.

Se usa um PostgreSQL já configurado, como Supabase, pode iniciar o backend sem
Docker: na pasta `api`, execute `uv run alembic upgrade head` e depois
`uv run python -m app.dev` (ou `python -m app.dev` no ambiente virtual ativado).
Esse comando inicia **API e worker juntos**; mantenha `npm run dev` em outro
terminal. Pare a API anterior antes de iniciá-lo. Iniciar apenas Uvicorn e Next.js
deixa otimizações em “fila” e entrevistas sem perguntas, pois falta o worker.
Docker ainda é necessário para compilar o PDF.

```powershell
npm run build
npm start
```

O build usa webpack, pois a compilação Turbopack não progrediu no sandbox Windows
da validação. O desenvolvimento mantém o padrão do Next.js.

## Entregue

- Shell responsivo em português, menu lateral rotulado, menu móvel acessível e
  conta autenticada por cookie `HttpOnly`; logout limpa os caches privados.
- Upload PDF/DOCX com limite no cliente e no BFF, extração feita pela API,
  apresentação do resultado incerto e proteção contra reenvio sem confirmação.
- Revisão editável e confirmação obrigatória do texto extraído. O consentimento
  para otimização direta ou entrevista é separado e explícito.
- Entrevistas com retomada, respostas/pulos/negativas, complementos, resolução de
  conflitos, confirmação das fontes, estado assíncrono e cota consultada na API.
- Revisão da proposta com comparação antes/depois, evidências e lacunas. A versão
  otimizada só abre o editor após a confirmação humana da proposta.
- Editor LaTeX com CodeMirror e duas ações: “Atualizar prévia” salva por ETag
  antes de compilar; “Gerar PDF Final” salva, acompanha a geração e inicia o
  download autenticado. Conflitos preservam o rascunho para comparação.
  Não há botões separados de salvar ou baixar TEX/PDF no editor.
- Histórico paginado, retomada de entrevista/tentativa e exclusão com confirmação.
- BFF de lista fechada para dados e arquivos: autenticação, proteção de origem,
  limites de corpo, allowlist de consultas/cabeçalhos, preservação de status,
  ETag e `Retry-After`, respostas privadas sem cache e projeção de metadados.
- Tipos derivados do OpenAPI e schemas Zod nas fronteiras consumidas pelo front.

## Limitações atuais

- OCR de PDF escaneado não está disponível. A vaga é vinculada ao original e
  precisa ser reenviada com um novo arquivo para iniciar outra jornada.
- Rascunhos de formulário/editor ficam na página até serem salvos; o editor não
  possui autosave local persistente.
- O editor separa prévia temporária e PDF final da revisão salva. Alterações
  manuais de LaTeX não passam por nova revisão factual automática.
- A API continua sendo autoridade para cota, propriedade, prazos e limites. A
  configuração local do front apresenta os tetos publicados para a entrevista.
- O histórico depende da extensão da API que lista tentativas por currículo e da
  associação da versão otimizada à tentativa de origem; o contrato atual já as
  expõe. Dados sintéticos aparecem somente nas fixtures de teste/inspeção.
- Ainda não há landing pública. A raiz direciona para login/painel.

## Contratos

`openapi.json` é um snapshot exportado da API existente; não é mantido à mão.
Na raiz do repositório, usando o Python do ambiente da API:

```powershell
api/.venv314/Scripts/python.exe front/scripts/export-openapi.py
```

Ou, com uv instalado, na raiz:

```powershell
uv run --project api python front/scripts/export-openapi.py
```

Depois, em `front`:

```powershell
npm run api:types
```

Revise o diff de `openapi.json` e `src/generated/api.ts`. Não editar o arquivo
gerado manualmente. O exportador não lê `.env`, não consulta o banco e não inicia IA.

## Verificações

```powershell
npm run lint
npm run typecheck
npm run format:check
npm test
npm run build
npm run test:e2e
```

Playwright usa Edge instalado (`channel: msedge`), portas 3011/8011 e API
sintética em `tests/fixtures/api.mjs`. Essa fixture não é importada pelo app.
Dados identificados: `conta_demonstracao`, três arquivos contendo “sintéticos”,
“demonstração” ou “exemplo”, cota 2/5 e reinício em 01/11/2026 UTC. Não são dados
de uso ou de eficácia do produto. A aplicação normal não possui modo demo ou
atalho para ignorar autenticação.

Para inspecionar com a Taste Skill, mantenha em terminais separados a fixture
e o front de testes (configuração exclusiva desses processos):

```powershell
# Raiz do repositório
node front/tests/fixtures/api.mjs
```

```powershell
# Em front, depois do build
$env:API_BASE_URL='http://127.0.0.1:8011'
$env:APP_ORIGIN='http://localhost:3011'
npm start -- -p 3011
```

```powershell
# Raiz do repositório
node .agents/skills/design-taste-frontend/scripts/lint.mjs front/src --app
node front/tests/fixtures/inspect-auth.mjs http://localhost:3011/painel --app --out .taste-skill/inspect-final
```

O adaptador de inspeção apenas coloca a sessão sintética no perfil descartável
do navegador. O app continua validando-a pela API de testes. Nenhum arquivo da
skill foi alterado. Encerre os processos de teste ao concluir.

Para o smoke com FastAPI real, execute na raiz:

```powershell
api/.venv314/Scripts/python.exe front/tests/fixtures/real_api.py
```

Em outro terminal, em `front`, configure `API_BASE_URL=http://127.0.0.1:8012`,
`APP_ORIGIN=http://localhost:3012` e execute `npm start -- -p 3012`. Em um terceiro
terminal, em `front`, execute `node tests/fixtures/real-smoke.mjs`. A API usa SQLite
temporário, não acessa dados existentes nem chama IA. Ao encerrá-la normalmente,
o banco temporário é removido. Isso não substitui testes de concorrência com PostgreSQL.

Resultados, crítica visual e limitações: [docs/validation.md](docs/validation.md).
Decisões da Taste Skill: [docs/design.md](docs/design.md).

Referências consultadas: [instalação Next.js](https://nextjs.org/docs/app/getting-started/installation),
[autenticação Next.js](https://nextjs.org/docs/app/guides/authentication),
[shadcn/ui manual](https://ui.shadcn.com/docs/installation/manual) e
[Tailwind PostCSS](https://tailwindcss.com/docs/installation/using-postcss).
