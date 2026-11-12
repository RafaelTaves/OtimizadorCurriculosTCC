# Deploy no Railway — branch `production`

Este guia publica o frontend Next.js, a API FastAPI, os dois workers, o PostgreSQL e o bucket privado. Execute comandos locais na raiz do repositório. As configurações foram preparadas na branch `production`; criar os recursos e inserir os segredos na conta Railway são etapas do deploy.

## 1. Entenda os serviços

| Nome no Railway | Origem / pasta raiz | Processo | Exposição |
| --- | --- | --- | --- |
| `front` | GitHub / `/front` | Next.js standalone, `Dockerfile` | Único domínio público |
| `api` | GitHub / `/api` | FastAPI, `Dockerfile` | Rede privada, porta 8000 |
| `worker-ai` | GitHub / `/api` | Fila de otimizações e entrevistas | Sem domínio |
| `worker-pdf` | GitHub / `/api` | Fila de prévias e exportações, `docker/railway-pdf.Dockerfile` | Sem domínio |
| `Postgres` | Database → PostgreSQL | Banco e fila persistente | Rede privada |
| `curriculos` | Storage Bucket | Originais, LaTeX e PDFs privados | Credenciais S3 |

Os três serviços Python precisam usar **o mesmo banco, bucket e segredo JWT**. O navegador fala com o Next.js; o Next.js fala com a API. Não coloque chaves em variáveis `NEXT_PUBLIC_*`.

O Compose de desenvolvimento usa volume compartilhado e socket Docker. Não o importe como configuração de produção. Nesta implantação, os arquivos estão no bucket, e o PDF é compilado sem Docker dentro de Docker. A API e o worker de IA continuam como usuários sem privilégios. O worker de PDF inicia como root para criar uma raiz isolada (`chroot`); o processo Tectonic perde privilégios, recebe apenas fontes/cache e o documento da execução, não recebe segredos e tem rede bloqueada por seccomp, além de limites de CPU, memória, tamanho e tempo. Se o isolamento não puder ser ativado, a inicialização falha; não há fallback sem isolamento.

## 2. Envie as mudanças ao GitHub

Confira os arquivos e publique a branch:

```powershell
git switch production
git status
git add api front docs .railway
git commit -m "Configura deploy de produção no Railway"
git push -u origin production
```

O repositório atual é `RafaelTaves/OtimizadorCurriculosTCC`. Autorize o Railway a acessá-lo. Nas próximas atualizações, faça push em `production` para acionar o deploy automático dos serviços conectados a essa branch.

## 3. Crie o projeto, banco e bucket

1. No Railway, crie um **Empty Project** e use o ambiente `production`.
2. Adicione **Database → PostgreSQL** e mantenha o nome `Postgres`.
3. Adicione um **Storage Bucket** e chame-o de `curriculos`. Use um bucket exclusivo desta aplicação e ambiente.
4. Aguarde o banco e o bucket ficarem disponíveis. Na aba **Credentials** do bucket, confira endpoint, região e estilo de URL.
5. Mantenha os serviços na mesma região quando possível. O arquivo IaC opcional usa bucket em `iad`; no painel, selecione a região antes de criar o bucket.

As referências abaixo pressupõem exatamente esses nomes. Se renomear os recursos, ajuste as referências. O valor `BUCKET` é o identificador S3 completo; ele não é apenas o nome visual `curriculos`.

## 4. Cadastre os segredos compartilhados

Em **Project Settings → Shared Variables**, no ambiente `production`, crie:

| Variável | Valor |
| --- | --- |
| `JWT_SECRET` | Segredo aleatório de pelo menos 32 caracteres |
| `OPENAI_API_KEY` | Sua chave de API com acesso ao modelo escolhido |
| `OPENAI_MODEL` | Identificador exato de um modelo compatível com Structured Outputs, validado para esta aplicação |

Para gerar o JWT_SECRET localmente, por exemplo:

```powershell
node -e "console.log(require('node:crypto').randomBytes(48).toString('hex'))"
```

Copie o resultado apenas para o Railway. Não use o valor do `.env.example` nem versione arquivos `.env`. A chave de IA e o modelo precisam estar presentes tanto na API (que verifica a disponibilidade) quanto no `worker-ai` (que executa as chamadas). O `worker-pdf` não precisa da chave da OpenAI.

## 5. Configure a API

Adicione um serviço pelo repositório GitHub e renomeie-o para `api`. Configure:

| Campo | Valor |
| --- | --- |
| Source → Branch | `production` |
| Source → Root Directory | `/api` |
| Builder | Dockerfile, detectado em `/api/Dockerfile` |
| Build Command | Deixe vazio |
| Start Command | Deixe vazio; usa `python -m app.serve` da imagem |
| Pre-deploy Command | `alembic upgrade head` |
| Healthcheck Path | `/ready` |
| Healthcheck Timeout | `120` segundos |
| Replicas | `1`, inicialmente |
| Serverless / App Sleeping | Desativado |
| Public Networking | Não gere domínio |

Cole no editor de variáveis da API:

```dotenv
PORT=8000
DATABASE_URL=${{Postgres.DATABASE_URL}}
JWT_SECRET=${{shared.JWT_SECRET}}
OPENAI_API_KEY=${{shared.OPENAI_API_KEY}}
OPENAI_MODEL=${{shared.OPENAI_MODEL}}
STORAGE_BACKEND=s3
S3_BUCKET=${{curriculos.BUCKET}}
S3_ENDPOINT_URL=${{curriculos.ENDPOINT}}
S3_REGION=${{curriculos.REGION}}
S3_ACCESS_KEY_ID=${{curriculos.ACCESS_KEY_ID}}
S3_SECRET_ACCESS_KEY=${{curriculos.SECRET_ACCESS_KEY}}
S3_ADDRESSING_STYLE=virtual
PYTHONUNBUFFERED=1
```

Use a `DATABASE_URL` privada do Postgres, não `DATABASE_PUBLIC_URL`. A aplicação converte automaticamente `postgres://` e `postgresql://` para o driver instalado `postgresql+psycopg://`. Não precisa editar a senha ou montar a URL manualmente.

Para buckets antigos que indiquem **path-style** em Credentials, troque `S3_ADDRESSING_STYLE=path` nos três serviços Python. Não adicione o nome do bucket ao `S3_ENDPOINT_URL`: use o endpoint base informado pelo Railway.

Faça o deploy da API e confira que o pre-deploy concluiu as migrações. `/ready` exige acesso às tabelas da aplicação; `/health` apenas confirma que o processo HTTP está vivo. O healthcheck não testa a OpenAI nem faz chamadas cobradas.

## 6. Configure os workers

Crie mais dois serviços do **mesmo repositório**. Em ambos, selecione branch `production`, Root Directory `/api`, uma réplica e desative Serverless/App Sleeping. Não gere domínio nem configure healthcheck HTTP nos workers. Use política de reinício **On Failure**, com 10 tentativas, para API, workers e frontend.

### `worker-ai`

- Dockerfile: o padrão `Dockerfile`.
- Start Command: `python -m app.worker --lane ai`.
- Pre-deploy Command: vazio; só a API executa migrações.
- Variáveis: copie as da API, podendo omitir `PORT`.

### `worker-pdf`

- Adicione `RAILWAY_DOCKERFILE_PATH=docker/railway-pdf.Dockerfile` nas variáveis. O caminho é relativo à pasta raiz `/api`.
- Deixe Start Command vazio para usar a verificação de isolamento e o comando definidos na imagem.
- Pre-deploy Command: vazio.
- Copie `DATABASE_URL`, `JWT_SECRET`, `STORAGE_BACKEND`, todas as `S3_*` e `PYTHONUNBUFFERED` da API.
- Adicione `COMPILER_BACKEND=sandbox`.
- Não configure `RAILWAY_RUN_UID` como usuário sem privilégios: o launcher precisa de `chroot` e troca de UID. O Tectonic em si executa como UID 10002.
- Reserve pelo menos **1 GB de memória** inicialmente: o subprocesso tem limite de 512 MB e o worker/cache também usam memória. Ajuste segundo as métricas reais.

O primeiro build do PDF baixa o Tectonic e aquece o cache de fontes/pacotes. Pode demorar alguns minutos. O log `compiler_sandbox_ready` confirma uma compilação isolada do template antes de o worker começar a consumir a fila. A imagem é Linux **x86_64**. Não use `docker/worker.Dockerfile`, que pertence ao fluxo Docker local.

Suba os workers depois do primeiro deploy da API. Em redeploys simultâneos, eles toleram indisponibilidade temporária do banco e voltam a consultar a fila. Não existe Redis neste projeto: a fila está no PostgreSQL.

## 7. Configure e publique o frontend

Crie o serviço `front`, conectado à branch `production`, com Root Directory `/front`.

- Builder: Dockerfile detectado automaticamente.
- Build Command e Start Command: vazios; a imagem faz `npm ci`, `npm run build` e inicia `node server.js`.
- Pre-deploy: vazio.
- Healthcheck: `/login`.
- Porta: `3000`.

Defina:

```dotenv
PORT=3000
API_BASE_URL=http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000
APP_ORIGIN=https://SEU-DOMINIO.up.railway.app
```

Em **Settings → Networking → Generate Domain**, gere o domínio público para a porta `3000`. Substitua `APP_ORIGIN` pela URL HTTPS exata gerada, sem caminho e sem barra final. Aplique as alterações e faça deploy/redeploy do frontend. Se o painel exigir um primeiro deploy para gerar domínio, complete esse deploy, gere o domínio e atualize `APP_ORIGIN` antes de testar cadastro/login.

`APP_ORIGIN` é usado na proteção de origem das requisições. Um domínio incorreto causa `403 origem_invalida`. Se adicionar domínio próprio depois, configure o DNS mostrado pelo Railway, aguarde o HTTPS e atualize `APP_ORIGIN` para esse domínio. Use essa URL como endereço oficial da aplicação.

As variáveis do backend ficam no servidor Next.js e são lidas em runtime. Não precisa reconstruir com chaves da API. Os cookies de autenticação usam `Secure` quando `APP_ORIGIN` é HTTPS; use HTTPS ao testar o site público.

## 8. Valide o deploy completo

1. Confira API, frontend e os dois workers como ativos. Verifique migrações concluídas e `compiler_sandbox_ready`.
2. Abra o domínio HTTPS, cadastre uma conta de teste e faça login.
3. Envie um currículo **fictício de teste** em PDF com texto selecionável ou DOCX. Confira se o texto extraído aparece para revisão.
4. Revise e confirme o texto. Dê consentimento explícito antes de solicitar otimização. Esta etapa usa a OpenAI e pode gerar cobrança.
5. Confira que a tentativa sai da fila e a proposta aparece. Faça a revisão exigida.
6. No editor, gere uma prévia, salve uma edição e baixe PDF e LaTeX. Abra o PDF e confira acentos e texto selecionável.
7. Faça logout/login e confirme que o histórico e os arquivos permanecem disponíveis.
8. Redeploy da API e dos workers: confira novamente o histórico e um download. Os objetos devem continuar no bucket, não no filesystem efêmero dos contêineres.
9. Se for usar complementação por entrevista, teste também consentimento, perguntas e confirmação final.

## 9. Atualizações, dados existentes e operação

- Commits em `production` acionam os serviços conectados. Opcionalmente configure Watch Paths: `/api/**` para API/workers e `/front/**` para o frontend.
- Ao alterar o template ou cache de pacotes, reconstrua `worker-pdf`.
- Não mude `JWT_SECRET` a cada deploy; uma rotação invalida sessões existentes.
- O exemplo usa a cota padrão de cinco otimizações por mês. Para alterá-la, mantenha `MONTHLY_OPTIMIZATION_LIMIT` igual na API e nos workers. A decisão continua na API.
- Não habilite expiração automática de todos os objetos no bucket. O worker expurga temporários vencidos respeitando objetos protegidos; os documentos salvos permanecem até exclusão.
- Ative backups do PostgreSQL e estabeleça backup dos objetos. Rollback de uma imagem não desfaz migrações de banco. Teste restauração antes de depender dos backups.
- Este guia cria uma instalação nova. Se houver dados no ambiente local, migrar apenas o banco não basta: copie também os objetos, preservando exatamente as chaves `objects/<id>` e `temporary/<id>`. Pause escritas durante a migração. Não aponte a aplicação para um bucket vazio usando um banco que referencia arquivos antigos.
- Use limites de gasto do Railway e da conta de IA. Confira os preços e cotas atuais no painel antes de provisionar; este guia não pressupõe execução gratuita.

## 10. Provisionamento opcional por código

`.railway/railway.ts` descreve os mesmos seis recursos usando o formato **Infrastructure as Code**. O Railway atualmente orienta migrar do formato legado `railway.toml`/`railway.json` para esse fluxo. O caminho pelo painel acima funciona sem instalar o SDK IaC.

Para usar a CLI: instale uma versão atual de `@railway/cli` (mínimo 5.42.1), faça `railway login`, vincule o projeto com `railway link`, selecione o ambiente `production` e cadastre as variáveis compartilhadas `JWT_SECRET`, `OPENAI_API_KEY`, `OPENAI_MODEL` e `APP_ORIGIN`. Com Node.js 24, execute na raiz:

```powershell
npm ci --prefix .railway
railway config plan
railway config apply
```

Revise o plano antes de aplicar. O SDK oficial está fixado em `.railway/package-lock.json`. O domínio gerado do frontend é configurado no painel; depois atualize a variável compartilhada `APP_ORIGIN`. Ajuste o nome do projeto e repositório no arquivo se necessário. Não aplique este exemplo sobre um projeto existente com outros dados/recursos sem conferir o plano. A aplicação desse arquivo depende da sua autenticação Railway e não foi executada por este trabalho local.

## Diagnóstico rápido

| Sintoma | Verificação |
| --- | --- |
| `403 origem_invalida` | `APP_ORIGIN` deve coincidir com a origem HTTPS usada no navegador. |
| `502` / API indisponível | `api` ativa; `PORT=8000`; referência privada correta; serviços no mesmo ambiente. |
| `/ready` retorna 503 | Banco disponível e `alembic upgrade head` concluído. |
| Upload/download falha | Mesmo bucket nos três serviços; credenciais corretas; endpoint base; estilo virtual/path correto. |
| Otimização fica pendente | `worker-ai` ativo, sem suspensão, mesmo banco e bucket. |
| Prévia/exportação fica pendente | `worker-pdf` ativo e log de sandbox pronto. |
| `compilador_indisponivel` / `SANDBOX_UNAVAILABLE` | Dockerfile de produção correto, UID root no launcher e suporte a chroot/seccomp. Não remova o isolamento para contornar. |
| Falta pacote no LaTeX | O compilador só usa o cache incluído na imagem; atualize o aquecimento e reconstrua. |
| `429` de IA ou `503` de configuração | Crédito/limites da conta, chave e modelo configurados na API e no worker de IA. |
| Build usa arquivo errado | Root Directory `/api` e `RAILWAY_DOCKERFILE_PATH=docker/railway-pdf.Dockerfile` apenas no worker PDF. |

## Referências oficiais

- [Dockerfiles e RAILWAY_DOCKERFILE_PATH](https://docs.railway.com/builds/dockerfiles)
- [Deploy de monorepositórios](https://docs.railway.com/deployments/monorepo)
- [Migrações em pre-deploy](https://docs.railway.com/deployments/pre-deploy-command)
- [Rede privada](https://docs.railway.com/networking/private-networking)
- [Buckets, credenciais e estilo de URL](https://docs.railway.com/storage-buckets)
- [Infrastructure as Code](https://docs.railway.com/infrastructure-as-code/reference)
- [Aviso sobre o formato legado](https://docs.railway.com/config-as-code/reference)

Veja também [o registro de validação local](railway-validation.md).
