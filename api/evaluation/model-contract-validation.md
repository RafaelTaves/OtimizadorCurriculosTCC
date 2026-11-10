# Contratos da OpenAI e LaTeX — validação de 05/11/2026

## Correção entregue

O provedor recebe o template original e devolve `latex_gerado` completo junto
dos campos estruturados otimizados. O código recebido é preservado; não é
substituído pelo renderizador auxiliar. O arquivo de template não foi alterado.

O schema interno deixa de pedir campos redundantes sujeitos a contradições:
tipo de alteração, duas versões da mesma evidência e um booleano de entrevista
que duplicava a informação contida na lista de perguntas. Esses valores são
derivados para o contrato público, que permanece compatível com o front. Fontes
e trechos de evidência continuam obrigatórios e são validados antes de salvar.

Na primeira rodada da entrevista, o schema permite apenas referências nulas a
respostas e zero conflitos. A segunda rodada continua exigindo IDs de respostas
afirmativas existentes. O prompt explica que o termo da vaga deve ser literal
ou nulo. O validador identifica a regra que falhou sem expor currículo/respostas.

O LaTeX é verificado por comandos e conteúdo, não por igualdade de bytes com o
renderizador. O preâmbulo deve preservar os comandos/argumentos do template;
comentários e espaços podem variar. O corpo usa um conjunto limitado dos comandos
do template, com ambientes/grupos balanceados. Seu texto precisa ser composto
pelos campos validados, preservando cada sequência; repetições de fatos existentes
são aceitas. Texto extra, comandos desconhecidos, links sem fonte, preâmbulo
alterado e conteúdo após o documento são rejeitados. Isso complementa, mas não
substitui, a revisão humana e a compilação isolada.

Respostas inválidas são corrigidas automaticamente dentro da mesma tentativa,
com o diagnóstico anterior e o limite de execuções existente (padrão: três).
Não há duplicação de reserva de cota. O orçamento de execução das entrevistas
continua sendo aplicado a cada chamada. Tokens retornados de propostas rejeitadas
também são acumulados no registro da tentativa; erros de parsing do SDK podem
não disponibilizar contagem, portanto o consumo do provedor continua sendo a
referência para faturamento.

## Verificação real

Modelo configurado: `gpt-6-luna`. Somente fixtures declaradamente fictícias de
`evaluation/cases.json`; nenhum currículo real foi lido ou reenviado e nenhum
registro da aplicação foi modificado.

| Cenário | Otimização com LaTeX | Entrevista |
| --- | --- | --- |
| Estágio Python | Válida na primeira execução | Primeira rodada válida, três perguntas |
| Primeiro emprego em dados | Válida após uma correção automática | Primeira e segunda rodadas válidas |
| Vaga com injeção de instruções | Válida na primeira execução | Primeira e segunda rodadas válidas |

O primeiro retorno de dados repetia o título de curso/projeto em dois argumentos
de `cventry`. A comparação por quantidade de palavras o rejeitou; a segunda chamada
corrigiu a repetição e foi aceita. A regra final foi ajustada para permitir a
repetição de fatos inteiros comprovados. As **quatro respostas reais de proposta**
capturadas foram revalidadas com o código final e passaram, inclusive a primeira.
O relatório original mantém a rejeição observada, sem reescrever o histórico.

Artefatos sintéticos locais (ignorados pelo Git):

- `evaluation/results/model-contract-debug/`: estágio e primeira entrevista.
- `evaluation/results/model-contracts/report.json`: execução dos outros dois casos.
- Subpastas por caso: respostas JSON e `.tex` realmente devolvidos pelo modelo.

Para reproduzir, na pasta `api`:

```powershell
.\.venv314\Scripts\python.exe -m evaluation.check_model_contracts --live
```

O comando recusa executar sem `--live`. Aceita `--case <id>` para limitar cenários.
Executa chamadas pagas com as fixtures, sem acesso ao banco da aplicação.

## Testes automatizados e verificações

Na raiz do projeto:

```powershell
./api/.venv314/Scripts/python.exe -m pytest -q -c api/pyproject.toml api/tests --basetemp=.test-tmp/final-provider-suite --tb=short
./api/.venv314/Scripts/python.exe -m mypy --config-file api/pyproject.toml api/app
```

Resultado final: **115 testes passaram; 8 foram pulados**, pois dependem de
PostgreSQL de teste ou Docker/Tectonic habilitados. Inclui schema real do SDK com
transporte simulado, normalização de metadados, primeira rodada sem IDs inventados,
correção com feedback, cota/orçamento, persistência, migrações SQLite e rejeição
de LaTeX/conteúdo não permitido. O caminho de `alembic.ini` nos testes foi corrigido
para funcionar também a partir da raiz do projeto.

Mypy passou nos 35 arquivos da aplicação. Ruff passou nos módulos da correção e
nos novos testes; o lint global também apontou formatação preexistente em
`app/api/routes.py` e linhas de `tests/test_flow.py`, fora da alteração funcional.
Os testes HTTP rodaram fora do sandbox devido aos sockets locais do TestClient
no Windows. Não houve alteração visual, inspeção do front ou compilação real de
PDF; a validação real abrange resposta estruturada e código LaTeX.

## Aplicar no ambiente local

Reinicie API e worker para carregar os novos schemas e prompts. O comando
`python -m app.dev` inicia ambos. Solicite nova otimização do currículo salvo;
tentativas antigas preservam seu estado de falha. Uma entrevista falhada ainda
válida pode usar “Tentar análise novamente”, respeitando os limites da API.
