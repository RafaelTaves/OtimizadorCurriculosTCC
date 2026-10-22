# Orientações para agentes

## Front-end e design

- Antes de criar, redesenhar ou revisar interfaces em `front/`, leia `.agents/skills/design-taste-frontend/SKILL.md` e siga o fluxo aplicável da Taste Skill.
- Para painel, formulários, listas, revisão de currículo, editor e conta, leia também `references/app-screens.md` dentro da skill. Use o modo `--app` nas ferramentas que o suportam. Para a landing page pública, use o fluxo de páginas da skill.
- Consulte `plano-front.md`, `plano.md` e os contratos existentes da API antes de implementar. Os requisitos do produto e as instruções explícitas do usuário prevalecem sobre as preferências estéticas da skill.
- Preserve a stack planejada (Next.js, TypeScript, Tailwind CSS e shadcn/ui), o português do Brasil, a acessibilidade, o consentimento antes do envio à IA e a revisão obrigatória do texto extraído. A cota e as regras de negócio continuam sob responsabilidade da API.
- Use dados fictícios apenas em fixtures e demonstrações identificadas. Não invente métricas de sucesso, depoimentos, experiências profissionais ou resultados de ATS.
- A skill orienta o design da interface web. Ela não altera o template LaTeX ou o conteúdo dos currículos sem solicitação específica.
- Execute as ferramentas a partir da raiz do projeto. Consulte `Documentação/taste-skill.md` para comandos, origem e validação. Registre verificações realmente executadas e limitações; a inspeção visual complementa os testes funcionais.
