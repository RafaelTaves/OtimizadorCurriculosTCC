# Validação da estrutura inicial — 22/10/2026

Os resultados desta primeira seção são históricos. A execução da tarefa 12 em
23/10/2026 está registrada ao final, incluindo o teste posterior de zoom nativo.

## Executado

- TypeScript strict e ESLint: sem erros.
- Vitest: 12 testes passando (retorno interno, confirmação de senha, contratos,
  minimização dos metadados, encaminhamento de originais/versões e cota zero).
- Build de produção Next.js 16.4.2, webpack: aprovado.
- Playwright, Edge/Chromium: 5 testes passando. Cobrem cookie ausente/inválido,
  BFF JSON/401, origem ausente/externa, login, conta, destino do original, logout,
  vazio/erro, navegação e menu por teclado com retorno de foco.
- Painel em 320, 375, 390, 768, 1024, 1440 e 1920 px: sem overflow horizontal;
  axe-core, regras WCAG 2 A/AA e 2.1 AA: nenhuma violação automatizada.
- Smoke com **FastAPI real e SQLite descartável**: cadastro pelo formulário,
  login, painel vazio, consumo 0/5 vindo da API, conta e logout. Sem worker ou IA.
- Smoke visual/axe em login, cadastro, painel, histórico, preparação de novo
  currículo e conta, em 390 e 1440 px: sem violações automatizadas; capturas abertas.
- Taste lint no código: 0 FAIL, 0 WARN.
- Taste inspect no painel autenticado com dados sintéticos, em 1440, 768 e 390 px:
  primeira rodada 0 FAIL/2 WARN; rodada final **0 FAIL/0 WARN**, sem `--allow`.
  Todas as seis capturas finais (dobras e folhas completas) foram abertas.

Artefatos locais ignorados pelo Git: `.taste-skill/inspect-initial/`,
`.taste-skill/inspect-final/` e `.taste-skill/real-smoke/`, a partir da raiz.

## Crítica visual do app

1. **Pergunta/hierarquia:** os documentos ocupam o maior bloco; o saldo é o único
   número em 30 px. A ação Novo currículo é identificável na primeira tela.
2. **Grade:** margens e fundos alinhados, dois blocos no desktop e uma coluna no
   tablet/celular. Na primeira rodada o uso tinha 59 px sobrando; a ação de
   consultar a conta e a tipografia legível ocupam esse espaço. Conta nova tem
   menos conteúdo no bloco de documentos, sem preenchimento com dados inventados.
3. **Cor/identidade:** marca de folha, nome explícito, Geist carregada localmente;
   azul só na barra proporcional, chrome neutro. Superfícies sem sombras.
4. **Consistência:** fixture 2 utilizados/reservados + 3 disponíveis = limite 5;
   a barra mostra 40%. A tela real vazia mostra 0 utilizados e 5 disponíveis,
   barra sem preenchimento. Datas usam Brasília; 01/11 00h UTC aparece em 31/10 21h.
5. **Zeros/ausências:** falha não vira zero; lista vazia tem orientação própria.
   Sem badges de contagem decorativos ou status de proposta inferido.
6. **Marcas/rótulos:** só uma barra de uso, com os dois extremos em texto, sem
   legenda redundante. Datas continuam visíveis no celular (ajuste da revisão).
7. **Celular:** navegação recolhida em diálogo, ação principal larga, nomes podem
   quebrar linha, rótulos e ações permanecem legíveis. Sem navegação fixa inferior.

Correções da rodada final: metadados importantes de 12 para 13 px; preenchimento
útil do painel de uso; datas preservadas nos itens móveis. A nota de confirmação
desconhecida foi removida da versão otimizada: exibir seu tipo basta, sem inventar
um estado de revisão. Não há fotografia nem animação de entrada, adequadas a este app.

## Limites reais

- Validação em Edge/Chromium no Windows. Firefox, WebKit, Android físico,
  iOS físico, leitor de tela manual e zoom nativo de 200% ainda não executados.
  Reflow a 320 px foi executado; não equivale a testar todas essas plataformas.
- O smoke real usa SQLite e não prova concorrência ou isolamento entre dois
  usuários com documentos no PostgreSQL. As regras de autorização continuam na API.
- Upload, geração, revisão, editor, preview, exportação e exclusão não foram
  implementados nem testados nesta entrega. As rotas preparatórias informam isso.
- Dados sintéticos existem só nos testes. A inspeção não mede eficácia de ATS.
- `npm audit` reportou cinco entradas altas na cadeia de ferramentas de lint
  (`eslint-config-next → fast-glob → micromatch → braces`), pelo advisory
  GHSA-vfj7-8cjw-p6xm. Não foi aplicado downgrade automático do Next/eslint para
  uma versão principal antiga. A auditoria completa está pendente de correção
  compatível upstream; não declarar o conjunto livre de vulnerabilidades.
- O npm não estava no PATH do executor: foi obtido em `.tools/npm` para instalar
  e validar. Os comandos documentados supõem uma instalação normal Node 24/npm.

## Tarefa 12 — logo, azul e mascote — 23/10/2026

### Verificações executadas

- `npm run lint --prefix front`, `npm run typecheck --prefix front` e
  `npm run build --prefix front` (webpack): aprovados.
- Vitest: **17 testes passando**. Os cinco novos casos cobrem o mascote na
  primeira página com total zero e sua ausência no erro, em páginas posteriores
  e quando a resposta não tem itens mas ainda informa documentos existentes.
- Playwright/Edge: **6 testes passando**, reaproveitando sessão, navegação,
  Escape/retorno de foco e estados anteriores. Novo cenário confere destinos da
  marca, logo carregada, mascote proporcional, dimensões reservadas e a navegação
  por teclado com as requisições das imagens bloqueadas.
- Reflow da marca em login/cadastro e do estado vazio em painel/histórico em
  **320, 390, 768 e 1440 px**, sem overflow horizontal. Mascote medido em 112/144 px,
  com proporção 1:1. As sete larguras do teste anterior do painel também passaram.
- Axe nas telas internas e estados testados: sem violações das regras WCAG A/AA
  selecionadas. Contrastes do azul verificados por cálculo, conforme `design.md`.
- **Zoom nativo de 200% no Edge**, em perfil descartável, configurado pela API de
  zoom da página `edge://settings/appearance`: `setDefaultZoom(2)`. Confirmado
  por `devicePixelRatio === 2`, largura externa de 1440 px e `innerWidth === 708`,
  sem alterar CSS para simular zoom. Painel, histórico vazio, login e cadastro
  carregados, capturados e abertos; sem overflow horizontal ou controles cortados.
  Isso não altera o perfil de navegação pessoal do usuário.
- Cópias das imagens verificadas por SHA-256: idênticas aos originais. Sem alfa,
  sem alterações nos traços, no texto, no corpo branco ou nas cores da ilustração.
- Taste lint: **0 FAIL, 0 WARN**. Inspeção autenticada em modo app no painel com
  documentos e no painel sem documentos, em 1440/768/390: **0 FAIL, 0 WARN** em
  ambos os estados finais, sem exceções por `--allow`.

### Capturas e comparação visual

Em `.taste-skill/task12/`, ignorado pelo Git:

- `before-filled/` e `before-empty/`: antes, com a marca SVG anterior.
- `after-filled/` e `after-empty/`: depois, com logo oficial e mascote condicional.
- Cada diretório contém relatório e capturas da dobra e página inteira nas três
  larguras do inspetor. As doze capturas finais foram abertas para conferência.
- `zoom-painel.png`, `zoom-curriculos.png`, `zoom-login.png` e `zoom-cadastro.png`:
  capturas reais em zoom nativo de 200%, com arquivos `-action.png` após rolar até
  a ação principal. Usado `Page.captureScreenshot` para capturar o viewport físico
  completo; a captura fullPage padrão do Playwright recortava metade da janela
  nesse perfil com zoom. As oito capturas finais de zoom foram abertas.

Para repetir a inspeção vazia, defina `TASTE_TEST_ACCOUNT=empty` no processo do
adaptador `front/tests/fixtures/inspect-auth.mjs`, com os mesmos servidores
sintéticos descritos no README. Sem essa variável ele usa a conta com documentos.

Crítica app: hierarquia e margens preservadas; logo legível sem repetir o nome;
mascote acompanha a primeira ação e não aparece sobre documentos ou cota. Texto
azul restrito à orientação e links sublinhados; dados e reservas mantêm os valores
da fixture. O estado vazio anterior tinha 93 px sobrando no bloco de documentos;
na primeira versão com mascote o aviso mudou para 42 px no bloco de uso. Um ajuste
de 4 px no espaçamento da orientação eliminou o aviso sem ocultar conteúdo ou
alterar o inspetor. Mobile preserva a ação e o menu; o mascote não é interativo.

### Limites desta execução

Navegador testado: Edge/Chromium no Windows. Firefox, WebKit, aparelhos físicos e
leitor de tela manual não foram executados. Dados de inspeção são sintéticos e
identificados pela fixture; não foram adicionados registros reais ou chamadas de
IA. Esta tarefa não reexecutou o smoke com FastAPI real da entrega anterior,
pois não alterou os contratos ou a autenticação. O aviso de dependências de lint
da auditoria anterior permanece registrado; esta tarefa não atualizou pacotes.

## Feature de upload, entrevista e editor — 23/10/2026

### Verificações executadas

- `npm --prefix front run lint`, `typecheck`, `format:check` e `build` (webpack):
  aprovados.
- Vitest: **21 testes passando** em quatro arquivos. Os casos novos verificam
  validação de extensão, multipart, rota de revisão, confirmação explícita após
  resultado incerto do upload e preservação de edições enquanto a confirmação
  do texto extraído está pendente.
- Playwright/Edge: **9 testes passando**. A fixture sintética cobre upload,
  revisão obrigatória do texto, consentimento antes da IA, retomada de sessão e
  reflow da tela de upload em 320/390/768/1440 px. Os cenários de shell também
  cobrem CSRF, sessão, estados de erro, teclado e reflow em sete larguras.
- API: **71 testes passando e 8 ignorados**. Os cinco cenários PostgreSQL (inclui
  migração e concorrência) foram ignorados sem `TEST_DATABASE_URL`; os dois testes
  com compilador real foram ignorados sem `RUN_COMPILER_TESTS=1` e imagem Tectonic.
  A suíte executada usou SQLite, parsers reais de extração e doubles para worker,
  OpenAI e compilador.
- Smoke com FastAPI real e SQLite temporário: cadastro, login, painel vazio, cota,
  conta e logout aprovados. Axe/reflow em seis telas e 390/1440 px sem violações.
  Não enviou arquivo, não iniciou worker, não compilou LaTeX e não chamou IA.
- Taste lint da aplicação: **0 FAIL e 0 WARN**.
- Taste inspect autenticado com dados explicitamente sintéticos: upload, revisão,
  hub/retomada, sessão de entrevista e proposta fecharam com **0 FAIL/0 WARN**.
  Editor final: **0 FAIL, 2 WARN** — diferença de 177 px entre os painéis de código
  e prévia vazia e faixa vazia de 77 px no canvas da prévia. O código curto mantém
  260 px de área editável e cresce até 640 px; a prévia vazia reserva o painel onde
  o PDF aparecerá. As capturas finais em 1440/768/390 px foram abertas. A tela de
  envio também passou por Playwright em 320 px.

Capturas de inspeção e relatórios ficam em `.taste-skill/feature-*`, ignorados pelo
Git. A API foi executada fora do sandbox para permitir o processo isolado de
extração e os servidores HTTP locais descartáveis usados no Edge.

### Limites desta execução

Não foi executada a matriz PostgreSQL de concorrência/RLS nem o compilador real
Tectonic. O smoke real usa SQLite temporário e não executa a jornada de upload
contra a API por HTTP; a validação de extração e dos fluxos de serviço veio da
suíte da API. Nenhuma chamada ao provedor OpenAI foi feita. Navegador: Edge/
Chromium no Windows; Firefox, WebKit, dispositivos físicos, leitor de tela manual
e zoom nativo de 200% nas novas telas não foram executados. O teste de Axe do smoke
real cobriu login, cadastro, painel, upload e conta; nas demais novas rotas houve
inspeção visual, tipagem e testes de fluxo, sem auditoria Axe dedicada.

## Ações finais do editor — 10/11/2026

A pergunta desta tela é: como conferir e baixar a versão editada do currículo?
Mantida a direção existente `achromatic-ledger`, com a identidade do Otimizador,
sem novo sorteio nem alteração do shell. O objeto é um currículo otimizado e
confirmado; código, revisão salva, ETag, captura da prévia e tentativa de exportação
continuam separados. A API fornece as revisões e o estado da compilação. O uso é
individual, em desktop ou celular. O código e a prévia continuam sendo o conteúdo
principal. As duas ações ficam juntas no topo: atualizar a prévia salva primeiro;
gerar o PDF salva, acompanha a compilação e inicia o download uma única vez.
Removidos salvar, baixar TEX e a seção redundante de exportação ao fim da tela.
O aviso sobre revisão factual permanece junto ao código.

Verificações executadas:

- Build de produção, TypeScript e ESLint aprovados; 21 testes unitários aprovados.
- 7 testes Playwright/Edge novos aprovados: salvamento antes de cada prévia,
  sequência salvar/gerar/baixar, rascunho preservado durante compilação, conflito
  nas duas ações, falha de compilação, falha de download e reflow em três larguras.
- Taste lint do componente: 0 FAIL / 0 WARN.
- Taste inspect autenticado em 1440, 768 e 390 px: 0 FAIL / 2 WARN. Capturas
  abertas e conferidas: ações legíveis e acessíveis, bordas alinhadas, navegação
  recolhida e abas no celular. A área de código conserva altura mínima editável;
  a prévia vazia reserva seu canvas, justificando os avisos de diferença de altura
  entre painéis (201 px) e faixa vazia no painel de prévia (77 px). Não há métricas,
  gráficos ou totais adicionados. Capturas em `.taste-skill/editor-actions/`.

Os testes usam currículo, respostas de compilação e arquivo PDF sintéticos,
identificados nas fixtures. Não houve chamada à IA nem compilação Tectonic real.
Build e navegador precisaram executar fora do sandbox após bloqueios locais de
criação de artefatos/inicialização do navegador. A primeira versão do teste de
falha de download capturava o alerta vazio do Next.js; o seletor foi corrigido
para aguardar a mensagem de erro do editor, e os sete testes foram repetidos.
