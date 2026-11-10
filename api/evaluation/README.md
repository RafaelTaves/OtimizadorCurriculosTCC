# Avaliação do TCC

## Contratos reais de geração e entrevista

`uv run python -m evaluation.check_model_contracts --live`, na pasta `api`, valida
os três casos fictícios contra o modelo configurado, incluindo LaTeX e duas
rodadas de entrevista quando há perguntas. Não consulta o banco da aplicação.
Cada etapa tem até três execuções com diagnóstico de correção; `--case <id>`
restringe os casos. O comando falha sem `--live`. Resultados e artefatos ficam em
`evaluation/results/model-contracts`, ignorado pelo Git. Os dados são somente as
fixtures de `cases.json`; a rotina não aceita arquivos de currículos reais.

Veja [a validação de 05/11/2026](model-contract-validation.md) para resultados,
reprodução, limites e diferenças em relação à montagem determinística anterior.

## Avaliação de qualidade

Os três casos em `cases.json` são inteiramente sintéticos. Incluem estágio, primeiro emprego, competências sem evidência e injeção de instruções pela vaga. Amplie a amostra antes de tirar conclusões.

Execute na pasta `api` com o ambiente instalado:

```powershell
uv run python -m evaluation.run
```

Esse comando apenas prepara o relatório e a rubrica vazios. Não inventa medições. Para medir chamadas reais, configure `.env` e use `--live`; para incluir compilação, acrescente `--compile`. Informe os preços efetivos do modelo com `--input-price` e `--output-price`, em moeda por milhão de tokens, para calcular estimativas de custo. O modelo não tem preço presumido no código. A execução direta de avaliação não passa pela cota de contas da API.

```powershell
uv run python -m evaluation.run --live --compile
```

Guarde modelo, data da execução e versões do lockfile junto ao relatório. `results.json` contém duração, tokens, custo quando informado, cobertura de termos sustentados, termos não sustentados detectados e proposta. Erros são registrados por código. Meça a extração com os casos PDF/DOCX dos testes e adicione documentos consentidos se necessário. Os testes do compilador medem sucesso e texto selecionável; eles não substituem inspeção visual da legibilidade.

Entregue os arquivos `*-A.txt` e `*-B.txt`, a vaga e `rubrica.csv` a avaliadores que não recebam `chave-cega.json`. Avalie relevância, clareza e legibilidade de 1 a 5 e conte fatos introduzidos indevidamente. A chave permite comparar as notas depois da avaliação. A atribuição aleatória usa uma semente fixa para ser reproduzível.

No relatório, apresente taxas de extração e compilação, média e dispersão de tempo/custo, cobertura de termos sustentados e contagem humana de alterações factuais indevidas. Explique o tamanho e a natureza da amostra, vieses dos avaliadores e limites da detecção automática. Não use uma “nota ATS” como evidência de contratação.

## Entrevista opcional

As fixtures identificadas em `tests/test_interviews.py` cobrem projeto acadêmico, ausência de experiência, respostas puladas, informação espontânea, contribuição em API, conflito de datas, referências inválidas, confirmação e geração com evidências. Os testes simulam o provedor: seus tempos e tokens fictícios não medem a qualidade ou o custo de um modelo real. O script `evaluation.run` continua avaliando a geração direta.

Para avaliar a entrevista real, use uma conta de teste e esses cenários fictícios pelas rotas documentadas em `api/README.md`. Registre modelo, data, quantidade de rodadas, perguntas realizadas, informações confirmadas aproveitadas na proposta e fatos indevidos. Os registros técnicos em `tentativas_geracao` guardam tokens cumulativos por análise e execuções; os logs do worker registram duração e tokens sem texto de currículo ou respostas. Estime o custo com os preços efetivos na data, incluindo análises e geração. Uma falha antes do retorno do provedor pode não disponibilizar tokens/cobrança; confira também o consumo no provedor. Separe tempo de espera na fila e de resposta humana do tempo de processamento.

A rubrica humana deve registrar pertinência (1–5), clareza (1–5), perguntas repetidas, insistência após negativa, sugestões de fatos não informados, conflitos não resolvidos e aproveitamento dos complementos. Compare o mesmo cenário com geração direta. Mantenha campos sem medição em branco; não atribua notas ou vantagens presumidas. Chamadas reais não foram executadas na validação automatizada da feature.
