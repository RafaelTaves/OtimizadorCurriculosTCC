# Validação da inicialização da fila — 05/11/2026

## Diagnóstico

Iniciar apenas a API e o front deixa pedidos na fila, pois as chamadas de
otimização e análise de entrevista são executadas pelo processo `app.worker`.
A consulta operacional ao banco configurado confirmou migration `0002`, uma
otimização pendente em `fila` com zero execuções e uma análise de entrevista
cancelada com zero execuções. Não foram consultados conteúdos de currículos.

## Correção

`python -m app.dev`, executado na pasta `api`, inicia API e worker com o mesmo
interpretador, ambiente e diretório de trabalho. O supervisor encerra ambos ao
receber Ctrl+C ou quando um filho termina. Não usa reload automático; reinicie
após alterar o backend. O front continua em seu próprio terminal.

## Verificações executadas

A partir da raiz do projeto, usando o ambiente existente `.venv314`:

```powershell
./api/.venv314/Scripts/python.exe -m pytest -q -c api/pyproject.toml api/tests/test_dev.py api/tests/test_adapters.py api/tests/test_flow.py api/tests/test_interviews.py --basetemp=.test-tmp/queue-validation --tb=short
./api/.venv314/Scripts/python.exe -m ruff check api/app/dev.py api/tests/test_dev.py
./api/.venv314/Scripts/python.exe -m ruff format --check api/app/dev.py api/tests/test_dev.py
./api/.venv314/Scripts/python.exe -m mypy --strict api/app/dev.py --follow-imports=skip
./api/.venv314/Scripts/python.exe -m compileall -q api/app/dev.py
```

Resultado: **51 testes passaram**, lint, formatação, tipagem e compilação sem
erros. Os testes cobrem o supervisor, contratos do SDK com transporte simulado,
fluxo completo de otimização, entrevista, revisão, idempotência, cota e leases.

## Limitações

Os testes de fluxo usaram SQLite temporário, dados fictícios e provedores
simulados. Precisaram rodar fora do sandbox: o TestClient bloqueava na criação
do socketpair do event loop do Windows dentro dele. As execuções bloqueadas
foram interrompidas.

A execução do worker contra a tarefa real foi bloqueada pela revisão automática
de aprovação, por envolver envio de currículo/vaga à OpenAI e alteração de
artefatos reais. A proposta real não foi gerada nesta validação. Nenhuma mudança
visual foi feita, e não houve inspeção visual do front.
