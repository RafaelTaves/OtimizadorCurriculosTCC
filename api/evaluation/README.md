# Avaliação do TCC

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
