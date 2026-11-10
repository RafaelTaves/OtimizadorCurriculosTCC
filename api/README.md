# API de otimização de currículos

Monólito Python 3.14/FastAPI, organizado nas camadas `app/api` (HTTP e dependências), `app/service` (regras e portas), `app/presentation` (contratos) e `app/infrastructure` (PostgreSQL, extração, OpenAI, arquivos e compilação). `tests` cobre regras, rotas e integrações. Não inclui frontend; os contratos atendem ao editor LaTeX com visualizador de PDF.

As entidades persistidas são `usuarios`, `curriculos`, `tentativas_geracao`, `sessoes_complementacao`, `rodadas_complementacao` e `registros_idempotencia`. A tabela de tentativas implementa a fila, o histórico e a cota; análises de entrevista têm orçamento técnico separado. As migrações são explícitas e versionadas com Alembic. O lockfile `uv.lock` fixa as dependências diretas e transitivas.

No PostgreSQL, a migração inicial habilita RLS sem políticas públicas e remove permissões de `PUBLIC` e, quando existirem, dos papéis Supabase `anon` e `authenticated`, nas tabelas da aplicação e do Alembic. A API e o worker usam a conexão do proprietário das tabelas; o acesso dos usuários passa pela autenticação da API. Isso evita expor currículos e senhas pela Data API do Supabase. Para usar um usuário de banco diferente do proprietário, será necessário definir suas permissões e políticas explicitamente.

Para Supabase em redes IPv4, copie a URI de **Connect → Session pooler**, porta `5432`, e use o prefixo `postgresql+psycopg://` em `DATABASE_URL`, com `sslmode=require`. O parâmetro `pgbouncer=true`, usado por outros clientes, não é aceito pelo driver psycopg. Esse modo usa o mesmo banco em nuvem e não requer o adicional de IPv4 dedicado.

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

O aquecimento do cache compila o template e uma amostra fictícia com `\url`,
contatos, títulos e `\cventry`, incluindo as fontes desses comandos. Ao atualizar
`docker/warm_cache.py` ou o template, reconstrua a imagem com o comando acima.
Uma imagem antiga pode retornar `latex_invalido` mesmo para código válido, caso
faltem fontes no cache offline. A nova imagem é usada na próxima compilação;
solicite outra prévia/exportação, pois tentativas já encerradas não são retomadas.

Acesse [Swagger](http://localhost:8000/docs), [OpenAPI](http://localhost:8000/openapi.json) e [health](http://localhost:8000/health). A composição espera o PostgreSQL ficar saudável e as migrações terminarem antes de iniciar API/worker. O banco e os arquivos ficam em volumes privados. `docker compose down` preserva os dados.

## Executar API e worker pelo terminal

Instale Python 3.14 e uv. Configure `.env` e um PostgreSQL; Docker continua necessário para compilar LaTeX.

```powershell
uv sync --frozen
docker compose up -d db
uv run alembic upgrade head
uv run python -m app.dev
```

`app.dev` inicia a API e o worker juntos, usando o mesmo Python, `.env` e
diretório de armazenamento. Ctrl+C encerra os dois; se um processo terminar,
o outro também será encerrado. Reinicie o comando após editar o backend (sem
reload automático). O front continua em outro terminal com `npm run dev`.
Encerre a API anterior antes de usar esse comando para liberar a porta 8000.

Se já usa um ambiente virtual ativado, execute `python -m app.dev`. Neste
checkout, também é possível usar `.\.venv314\Scripts\python.exe -m app.dev`
na pasta `api`, caso esse seja seu ambiente instalado.

Para executar os serviços separadamente, mantenha **dois terminais** na pasta
`api`, com o mesmo ambiente: `uv run uvicorn app.main:create_app --factory --reload`
em um e, no outro:

```powershell
uv run python -m app.worker
```

### Proposta parada em “fila” ou entrevista sem perguntas

Iniciar somente FastAPI e o front não processa a fila. A API registra o pedido;
`app.worker` faz as chamadas à OpenAI para otimizações e entrevistas, além das
compilações. `/health` confirma apenas que a API responde, não que o worker está
ativo. Use `app.dev` para iniciar os dois juntos.

Para recuperar uma tentativa ainda pendente, basta iniciar o worker na pasta
`api`: ele retoma a mesma tentativa, sem solicitar outra otimização nem criar
outra reserva de cota. Uma entrevista cancelada não é retomada; inicie outra
pela interface, com o consentimento habitual. Não é necessário Docker para
entrevista e geração do texto/LaTeX quando o PostgreSQL já está disponível;
Docker continua necessário para a compilação de PDF.

O diretório `storage` é privado e nunca é servido estaticamente. Não o coloque na pasta pública de um servidor web. Esta instalação foi projetada para uso local do TCC, sem implantação em produção.

## Usar o fluxo no Swagger

1. Cadastre em `POST /v1/auth/register`. Faça login em **Authorize** com username ou e-mail e senha. Tokens duram 30 minutos; não há refresh token neste MVP.
2. Envie `arquivo` PDF/DOCX e `descricao_vaga` em `POST /v1/curriculos`. PDF deve conter texto selecionável. Revise o texto retornado.
3. Confirme ou corrija o texto com `PATCH /v1/curriculos/{id}/texto-extraido`, JSON `{"texto":"..."}`. Essa etapa é obrigatória, mesmo sem correções.
4. Inicie `POST /v1/curriculos/{id}/otimizacoes` com `Idempotency-Key` exclusivo e `{"consentimento_envio_openai":true}`. O texto confirmado e a vaga serão enviados à OpenAI; a aplicação usa `store=false`, que não equivale a retenção zero do provedor.
5. Consulte a URL em `Location`/`acompanhamento`. O worker entrega `aguardando_revisao`, proposta, evidências, alterações, lacunas e `.tex`. A OpenAI recebe o template e retorna o documento LaTeX completo com o conteúdo estruturado otimizado. O servidor valida as fontes do conteúdo estruturado e a estrutura técnica do LaTeX antes de salvar o código recebido, sem exigir correspondência literal entre ambos. O `curriculo_gerado_id` identifica a versão para o editor. Confira o conteúdo e registre a revisão em `POST /v1/otimizacoes/{id}/confirmacao`.
6. Consulte `GET /v1/curriculos/{id}` para receber código e `ETag`. Use `POST /v1/curriculos/{id}/preview` com `{"latex":"..."}` para uma prévia sem salvar ou chamar a IA. Consulte `/v1/previews/{id}` e o endereço autenticado `download_pdf` para visualizar.
7. Salve com `PUT /v1/curriculos/{id}/latex`, JSON `{"latex":"..."}` e `If-Match: "1"` (aspas fazem parte do ETag). A API retorna uma nova revisão. ETag antigo recebe `412`; ausente, `428`. Editar invalida o PDF anterior e a revisão factual automática não abrange alterações manuais.
8. Chame `POST /v1/curriculos/{id}/renderizacoes` para compilar a revisão salva. Acompanhe em `/v1/renderizacoes/{id}`. Baixe `/v1/curriculos/{id}/download?formato=pdf` ou `formato=tex`. Se o código mudar durante a compilação, o resultado antigo não será publicado como atual.
9. Consulte histórico paginado com `GET /v1/curriculos?pagina=1&tamanho=20` e consumo em `GET /v1/uso`. Exclua em `DELETE /v1/curriculos/{id}`.

Todas as rotas de dados exigem Bearer token e verificam a propriedade. Recursos de outra conta retornam `404`. O download de PDF final exige renderização da revisão atual; o download `.tex` entrega o código salvo.

As palavras-chave são aceitas conforme a resposta do modelo, incluindo sinônimos,
siglas e equivalências. O backend preserva os termos e as evidências recebidas,
sem exigir correspondência literal com a vaga, a fonte ou o currículo e sem
rejeitar ou repetir a geração por esses metadados. O formato estruturado continua
obrigatório, assim como as demais validações do conteúdo e do LaTeX e a revisão
humana. Reinicie o worker para carregar esta regra; tentativas já encerradas com
falha precisam de uma nova solicitação de otimização.

## Entrevista opcional antes da geração

Os schemas internos do provedor evitam metadados redundantes: o tipo da alteração
e a evidência de palavras-chave são derivados para o contrato público; o estado
da entrevista é calculado a partir das perguntas. Na primeira rodada não são
permitidas referências a respostas nem conflitos, pois ainda não há respostas.

Uma resposta de formato ou conteúdo inválido recebe uma correção automática na
mesma tentativa, com o diagnóstico seguro da falha anterior. O limite padrão é
de três execuções (`WORKER_MAX_EXECUTIONS`), respeitando também o orçamento diário
da entrevista. Cada execução pode consumir tokens na OpenAI; a cota de otimização
mantém uma única reserva, liberada se todas falharem. Os fatos estruturados ainda
exigem fonte; não há novas chamadas depois de atingir esses limites.

O LaTeX retornado pelo modelo é preservado e pode resumir, reescrever, abreviar,
omitir campos e usar outros títulos de seção. Essas diferenças em relação ao JSON
não rejeitam a proposta nem provocam nova chamada à IA. A revisão do texto final
fica com a pessoa; o backend não atesta a equivalência factual entre JSON e LaTeX.
O preâmbulo deve preservar os comandos do template; o corpo aceita apenas comandos
conhecidos, grupos e ambientes balanceados, links correspondentes aos contatos e
conteúdo não vazio. A compilação continua isolada e a revisão humana é obrigatória.
O template em disco não é alterado pela geração. Reinicie o worker para aplicar a
regra; tentativas já falhadas precisam de uma nova solicitação.

A migration `0002` acrescenta sessões, rodadas, idempotência persistida e vínculos nas tentativas. Execute `uv run alembic upgrade head` antes de reiniciar API e worker. O fluxo direto de otimização continua disponível. A interface do front em `../front/` cobre upload, revisão, entrevista, proposta e editor; os contratos permanecem publicados no Swagger e nos tipos gerados.

1. Depois de revisar o texto extraído, chame `POST /v1/curriculos/{id}/complementacoes`, com `Idempotency-Key` e `{"consentimento_envio_openai":true}`. Esse consentimento abrange currículo, vaga e respostas. A resposta `202` fornece `id`, `tentativa_id`, `acompanhamento`, `Location` e `ETag`.
2. Consulte `GET /v1/complementacoes/{id}` até receber `aguardando_respostas` ou `aguardando_confirmacao`. Também é possível retomar pelo histórico paginado `GET /v1/curriculos/{id}/complementacoes`.
3. Envie `POST /v1/complementacoes/{id}/respostas`, com `If-Match` e uma nova `Idempotency-Key`. Cada pergunta deve ter texto ou `pulada:true`; `negativa:true` identifica explicitamente ausência de experiência. Os IDs são UUIDs retornados pela API. Exemplo fictício:

```json
{
  "rodada": 1,
  "respostas": [
    {
      "pergunta_id": "00000000-0000-4000-8000-000000000001",
      "texto": "Implementei endpoints de empréstimos em um projeto acadêmico com FastAPI.",
      "pulada": false,
      "negativa": false
    }
  ],
  "complemento_livre": null,
  "acao": "encerrar"
}
```

4. `acao:"aprofundar"` permite uma segunda análise, somente quando há resposta afirmativa ou informação espontânea para esclarecer. Sem essas informações, a API encerra para revisão sem outra chamada. Há até três perguntas por rodada e duas rodadas; a IA pode terminar sem perguntas. A segunda rodada deve referenciar uma resposta afirmativa anterior.
5. Revise os textos literais propostos em `complementos`. Use `PUT /v1/complementacoes/{id}/complementos`, com `If-Match`, para substituir a lista completa. Cada item tem UUID estável, `texto`, `resposta_origem_id` opcional e `substitui_trecho_original` opcional. Itens espontâneos podem não ter resposta de origem. Não é feita chamada à IA nessa revisão.
6. Chame `POST /v1/complementacoes/{id}/confirmacao`, com `If-Match`, nova chave e `{"confirmacao_informacoes":true,"revisao_conflitos":true,"resolucoes":[]}`. Conflitos detectados exigem uma resolução por ID: `manter_original` requer remover os complementos da resposta conflitante; `usar_complemento` requer seu `complemento_id` e o trecho literal substituído. Correções sobrepostas são rejeitadas. O usuário deve conferir também contradições não apontadas automaticamente.
7. Gere pela rota existente de otimização, acrescentando `sessao_complementacao_id` ao consentimento. Apenas a sessão confirmada entra como fonte; perguntas, sugestões e respostas não confirmadas ficam fora. A confirmação congela as fontes. Cada sessão aceita uma única tentativa de geração, mesmo com outra chave; nova geração deliberada usa outra sessão ou o fluxo direto.

`falhou` permite `POST /v1/complementacoes/{id}/retentativas` com `If-Match` e nova chave, ou respostas com `acao:"encerrar"` e lista vazia para revisar os dados já recebidos. A retentativa reutiliza a tentativa da rodada. `POST /v1/complementacoes/{id}/cancelamento` cancela uma sessão não confirmada; repetir é inofensivo. Resultados atrasados são descartados.

As rotas de criação, respostas, confirmação e retentativa guardam a resposta original por usuário/chave/rota/recurso/conteúdo. Repetir devolve esse resultado, inclusive com o ETag original, mesmo que a sessão já tenha avançado; consulte a sessão para obter a revisão atual. Reutilização de chave com outra entrada recebe `409`. Falta de `If-Match` recebe `428`, revisão antiga `412`, contexto original alterado `409`. Se os dados já tiverem sido expurgados, o replay recebe `410`.

Limites padrão configuráveis: três sessões novas por usuário/dia UTC, doze execuções de análise por usuário/dia UTC (incluem retries e recuperação de lease), uma sessão ativa por usuário/original, prazo de 24 horas sem confirmação, 4.000 caracteres por resposta/complemento livre e 12.000 no conjunto confirmado. Os limites de três perguntas e duas rodadas são tetos. Cada claim reserva uma execução sob bloqueio do usuário; a entrevista verifica disponibilidade da cota mensal, mas só a geração final reserva uma das cinco otimizações. Erros de orçamento recebem `429` e `Retry-After`.

Snapshots de sessões não confirmadas, respostas, perguntas e cópias de respostas idempotentes são expurgados ao cancelar/expirar, por consulta ou pelo worker. Sessões confirmadas seguem a retenção do currículo, até exclusão. Excluir o original remove sessões, rodadas e conteúdo privado; ficam somente contadores e identificadores técnicos para impedir reembolso ou evasão dos limites. Mantenha o worker ativo para a limpeza periódica.

Propostas novas registram `versao_schema:2`, `fontes_confirmadas` e o ID da sessão, quando usada. Fatos, alterações e palavras-chave identificam `fonte` (`curriculo_original` ou `complemento:<uuid>`) e evidência literal. Inclusões usam `tipo:"inclusao"` e `antes:null`; correções retiram o trecho substituído do catálogo factual, preservando o original armazenado. Propostas antigas continuam legíveis com a fonte original como padrão. A análise usa contexto estruturado explícito e `store=False`, sem conversa persistida no provedor e sem logs do conteúdo.

## Regras definidas

- **5 otimizações por usuário por mês civil em UTC**, renovando no primeiro dia às 00:00 UTC. Reservas pendentes/em processamento, propostas aguardando revisão e gerações concluídas contam no mês de criação da tentativa. Requisições simultâneas bloqueiam a linha do usuário antes da contagem/reserva no PostgreSQL. Limite retorna `429`, próximo reinício e `Retry-After`.
- Falhas de validação não reservam cota. Falha definitiva interna, do provedor ou da validação da proposta libera a reserva. Falhas transitórias têm backoff e até três execuções da mesma tentativa, sem consumir novas reservas. Excluir uma geração concluída não reembolsa a cota; o registro técnico sem currículo permanece para auditoria.
- A chave de idempotência é única por usuário. Reenvio com a mesma entrada devolve a mesma tentativa, inclusive após falha; entrada diferente com a mesma chave recebe `409`. Para uma nova tentativa, use outra chave. O worker usa bloqueio `SKIP LOCKED`, prazo de execução e token por execução para impedir publicação duplicada ou por um worker antigo.
- As chamadas ao provedor podem ser repetidas após falha de conexão ou interrupção do worker; uma transação local não garante cobrança única no provedor. A cota da aplicação continua usando uma única tentativa.
- Originais, versões, LaTeX, PDF e vagas são mantidos **sem prazo de expurgo**, até exclusão solicitada. Excluir um original remove também suas versões e os arquivos associados. Excluir uma versão remove apenas ela. Uma tentativa em execução é cancelada e não pode republicar arquivos após exclusão.
- Prévias são temporárias: expiram em uma hora, retornam `410` depois disso e são expurgadas pelo worker. Entradas de fila são snapshots temporários apagados ao terminar; entradas ainda aguardando execução são protegidas do expurgo. Códigos de prévia e exportação não consomem cota de IA. Há limites de frequência e de compilações pendentes por conta.
- Upload: até 10 MB, PDF com até 10 páginas, texto até 60000 caracteres, DOCX até 40 MB descompactados, descrição da vaga de 30 a 20000 caracteres, LaTeX até 200000 bytes. A extração usa processo separado com timeout; no contêiner Linux há limites de memória e CPU. DOCX não tem paginação estável sem renderização; aplica-se limite de conteúdo, sem estimar páginas.
- LaTeX livre é compilado com `--untrusted`, contêiner sem rede, root somente leitura, usuário sem privilégios, CPU/memória/processos/arquivos/tempo limitados e sem mounts. Diagnósticos externos incluem somente mensagem e linha de erro permitida, nunca o log bruto.
- O conteúdo estruturado exige evidência literal para cada fato, preserva datas e números e mantém campos de identidade/competências literais. O LaTeX passa por validações técnicas, sem comparação literal com esses campos. Confira o documento final no editor e na prévia: a revisão humana continua necessária para verificar fatos e omissões.

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
