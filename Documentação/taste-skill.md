# Taste Skill no projeto

A Taste Skill orienta decisões de composição, tipografia, cores, conteúdo e interação. Sua versão atual inclui uma biblioteca de direções visuais, scripts sem dependências npm e inspeção em navegador com capturas de tela. Há fluxos distintos para páginas públicas e telas de aplicação.

## Instalação e origem

- Nome da skill: `design-taste-frontend`.
- Local: `.agents/skills/design-taste-frontend/`, no escopo deste projeto.
- Site: https://www.tasteskill.dev/
- Repositório: https://github.com/Leonxlnx/taste-skill
- Diretório de origem: `skills/taste-skill`.
- Revisão instalada: `6010f91a9935f1c167dfc500fb1a475681892e6b`.
- Data da instalação: 22/10/2026.
- Licença: MIT, preservada no arquivo `LICENSE` junto à skill.

Foi copiado o diretório completo da revisão acima, incluindo `SKILL.md`, referências, biblioteca, assets e scripts. O código de origem da skill foi mantido sem adaptações; as orientações específicas do projeto ficam em `AGENTS.md`. A instalação não cria dependências npm para a aplicação.

O site ainda descreve uma organização anterior com várias skills. A revisão instalada do repositório oficial concentra o fluxo principal em `design-taste-frontend`, incluindo o tratamento de telas de aplicação. Esta cópia fica fixada na revisão indicada e não recebe atualizações automaticamente.

## Aplicação no otimizador de currículos

Antes de trabalhar na interface, ler a skill e o `plano-front.md`:

- Landing page: fluxo de páginas, com conteúdo real do produto e chamadas para ações disponíveis.
- Painel, currículos, revisão, editor e conta: fluxo de `references/app-screens.md`, com hierarquia funcional, estados claros e dados da API.
- Compartilhar identidade visual entre a página pública e a aplicação, respeitando as diferenças de densidade e interação.
- Manter os requisitos funcionais e de acessibilidade do plano. Preferências estéticas não justificam mudar rotas, consentimento, cota, contratos ou inventar conteúdo de currículo.

## Comandos

Executar na raiz `Tcc`. Os scripts de inspeção requerem Node.js 22 ou superior e Chrome, Edge ou Chromium. A busca opcional de imagens requer rede. O ambiente desta instalação possui Node.js `v24.19.0`.

Para listar categorias e consultar até três propostas de estilo sem gerar uma direção definitiva:

```powershell
node .agents/skills/design-taste-frontend/scripts/draw.mjs --app --list kinds
node .agents/skills/design-taste-frontend/scripts/draw.mjs --app --kind workspace --brief "Otimizador de currículos em português com revisão, editor LaTeX e prévia PDF" --screens overview,list,detail,builder,settings --options 3
```

Escolher o estilo com base no fluxo de uso, conforme a skill, e depois executar o comando de geração com `--style` no lugar de `--options 3`. Para manter também o histórico do sorteio dentro do projeto, definir antes de gerar:

```powershell
$env:TASTE_SKILL_HISTORY = Join-Path (Get-Location).Path '.taste-skill/history.json'
```

Quando existir código e o servidor do front estiver ativo, validar uma tela da aplicação, ajustando a URL para uma rota acessível na sessão de teste:

```powershell
node .agents/skills/design-taste-frontend/scripts/lint.mjs front/src --app
node .agents/skills/design-taste-frontend/scripts/inspect.mjs http://localhost:3000/painel --app
```

Para a página pública, executar lint e inspeção no modo de páginas, sem `--app`, sobre os arquivos e a URL correspondentes. Atenção: os scripts também detectam o modo pelo arquivo `.taste-skill/direction.json`; usar diretórios de trabalho separados para a landing page e a aplicação quando houver direções salvas, evitando que uma direção de app ative esse modo na validação da landing page. Ler as capturas e corrigir problemas após a inspeção. Não considerar uma tela de login como validação do painel protegido.

Os arquivos temporários e capturas em `.taste-skill/` estão ignorados pelo Git. Decisões visuais aprovadas devem ser registradas na documentação do front. A matriz responsiva e os testes funcionais de `plano-front.md` continuam necessários.

## Limite da validação inicial

A instalação foi conferida com carregamento da biblioteca de estilos e verificação de sintaxe dos scripts. A pasta `front/` estava vazia: não havia interface para executar lint de aplicação ou inspeção visual. A validação de páginas deve ocorrer durante a implementação.
