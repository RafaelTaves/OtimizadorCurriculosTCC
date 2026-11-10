# Direção da estrutura inicial

Taste Skill, modo app. Estilo **Achromatic ledger**, seed **1146489771**.
Escolhido para leitura de documentos, uso mensal e sessões de revisão individuais.
Sorteio inicial: icon rail. Um redesenho de shell resultou em no sidebar. Ambos
contradizem o menu lateral rotulado e o menu superior móvel exigidos no plano;
aplica-se a precedência do produto, usando o open plane com sidebar de 256 px.
Nenhum redesenho de cores ou tipografia.

## Inventário anterior à implementação

- Produto: Otimizador de currículos; escopo: conta autenticada.
- Pessoas: estudantes e profissionais em início de carreira, no celular ou desktop.
- Original: nome do arquivo, tipo, datas, texto e confirmação, conforme API.
- Versão otimizada: tipo e origem; não inferir confirmação da proposta.
- Histórico: página de até 20 registros; painel com até quatro recentes.
- Uso: limite, usado, restante, período e reinício informados pelo servidor.
- A conta nova pode não ter nenhum currículo; não preencher com amostras.
- Falha de uso não significa cota zero; falha de histórico não significa lista vazia.
- Trabalho frequente: preparar novo currículo e encontrar documentos anteriores.
- Revisar texto e consentir são pré-condições futuras para solicitar IA.

Pergunta do painel: **Quais currículos tenho e quanto posso otimizar neste período?**
Pergunta do histórico: **Quais documentos estão salvos na minha conta?**
Pergunta da conta: **Com qual identidade estou conectado e qual é meu uso?**

Face: fundo de papel neutro e Geist local. A marca oficial e o azul em destaques
curtos foram incorporados na tarefa 12, conforme as decisões abaixo. Assinatura:
sequência textual Enviar → Revisar → Otimizar → Editar, com a revisão humana como
parte explícita do trabalho.

Grade desktop: viewport − 256 px de sidebar − 2 × 32 px de margem;
conteúdo limitado a 1200 px. Duas colunas: (largura − 12 px) × 2/3 e × 1/3.
No celular: uma coluna, margens de 16 px e controles de pelo menos 44 px.

As imagens se limitam à marca e à orientação da conta sem currículos. Os objetos
da tela continuam sendo documentos, ações e a cota, sem gráficos estatísticos.
Dados sintéticos existem somente nos testes identificados.

## Identidade fornecida — tarefa 12, 23/10/2026

Mantidos o estilo Achromatic ledger, seed 1146489771, a tipografia e a estrutura.
Sem novo sorteio. A instrução explícita da tarefa permite palavras coloridas nos
títulos e substitui a restrição anterior do azul somente no indicador de uso.

- Originais preservados em `Documentação/LogoOtimizador.png` (2172 × 724) e
  `Documentação/MascoteCvOtimzador.png` (1254 × 1254).
- Cópias idênticas em `front/public/brand/logo-otimizador.png` e `mascote-cv.png`.
  Ambas são opacas (sem canal alfa). Sem recorte, remoção de fundo, filtros ou
  geração de arte. A logo fica sobre superfície branca compatível, com margens
  originais; o corpo branco do personagem foi preservado.
- `Brand` usa Next Image, dimensões intrínsecas e `sizes`, largura de 168 px no
  mobile e 204 px no desktop. Nome somente na imagem, seguido de “de currículos”.
  O link mantém seu destino configurável e um único nome acessível. `alt=""`
  evita a duplicação do anúncio; foco visível e dimensão reservada permanecem.
- Mascote estático: 112 px no mobile/tablet, 144 px no desktop. Só aparece em
  `HistoryPanel` após sucesso, sem itens, `total === 0` e `page === 1`.
  Texto: “Seu primeiro currículo começa aqui”; ação: “Preparar novo currículo”.
  Paginação vazia, erro, carregamento e lista preenchida não recebem a ilustração.

### Azul e contraste

Amostragem direta dos pixels RGB do mascote: região interior do bloco azul,
x=470–499 e y=670–699, em coordenadas do original. O valor mais frequente nessa
região foi **#2588FE** (198 pixels), sem usar bordas suavizadas ou sombra.

| Token               | Valor                    | Aplicação                                                                                                  |
| ------------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `--brand-blue`      | `#2588FE`                | Azul original, disponível no utilitário `text-brand-blue`; reservado a contextos com contraste suficiente. |
| `--brand-blue-text` | `#1462C7`                | Variante escura da mesma família, utilitário `text-brand-blue-text`, trechos curtos e links.               |
| `--data`            | `var(--brand-blue-text)` | Indicador de uso e foco, alinhados à marca.                                                                |

Contraste calculado pela luminância relativa sRGB:

| Cor de texto     | Branco #FFF | Fundo #F8F8F8 | Superfície #EEE |
| ---------------- | ----------- | ------------- | --------------- |
| Original #2588FE | 3,48:1      | 3,28:1        | 3,00:1          |
| Texto #1462C7    | 5,83:1      | 5,49:1        | 5,03:1          |

Todo texto azul desta entrega usa a variante escura, incluindo “primeiro currículo”,
“seus currículos” no login e “revisar seus currículos” no cadastro. `Ver todos` e
as ações do estado vazio usam `.brand-action`, com sublinhado permanente, foco e
reforço no hover. Descrições longas, campos, documentos e estados semânticos mantêm
as cores existentes. A futura landing poderá reutilizar os tokens; não foi criada
nesta tarefa. As cores ilustradas da marca não são estendidas aos painéis.

## Fluxo de upload e edição — featureChatUpload — 23/10/2026

Mantido o Achromatic ledger, a sidebar rotulada e os tokens da marca. As novas
telas seguem a sequência factual do produto: enviar arquivo e vaga, revisar o texto
extraído, consentir antes da IA, revisar a proposta e editar a versão confirmada.
O upload não exibe métricas, depoimentos ou dados fictícios; fixtures identificadas
existem somente nos testes e na inspeção autenticada.

- O formulário ocupa uma coluna; o seletor nativo permanece disponível além do
  arrastar/soltar. Nome e tamanho do arquivo ficam visíveis antes do envio.
- A revisão mantém o texto extraído em campo editável e diferencia texto pendente
  de texto confirmado. As caixas de consentimento aparecem separadas por jornada.
- A entrevista dá prioridade à pergunta e às opções de responder, pular ou marcar
  ausência de experiência; informações e conflitos mantêm a origem visível.
- A proposta compara antes/depois e aproxima cada alteração da evidência literal.
  Lacunas permanecem explícitas e não se convertem em competências inventadas.
- No editor, CodeMirror e prévia autenticada são carregados sob demanda. A altura
  do editor cresce com as linhas até 640 px e mantém 260 px para documentos curtos.
  O estado inicial da prévia explica que é preciso solicitá-la; a exportação fica
  separada da prévia.
- Desktop usa painéis Código/Prévia lado a lado; mobile troca entre abas e conserva
  o mesmo rascunho. O editor de três linhas da fixture ainda produz uma diferença
  natural entre a altura do painel de código e a prévia vazia (177 px no inspetor).
  O espaço da prévia vazia (77 px) é o canvas de leitura reservado para o PDF. Esses
  dois avisos da Taste Skill descrevem a diferença entre áreas de trabalho distintas;
  foram mantidos para preservar a comparação lado a lado pedida pelo fluxo. O editor
  permite rolagem interna do código longo sem ampliar a largura da página.

Inspeção com fixture sintética autenticada em `.taste-skill/feature-*`, ignorada pelo
Git: upload, revisão do texto, hub/retomada, sessão de entrevista, proposta e editor.
Upload, revisão, hub, entrevista e proposta fecharam com 0 FAIL/0 WARN. O editor
final fechou com 0 FAIL e os dois avisos de painéis descritos acima. As capturas de
1440, 768 e 390 px foram abertas para conferência. Um teste Playwright adicional
verifica o upload em 320, 390, 768 e 1440 px.
