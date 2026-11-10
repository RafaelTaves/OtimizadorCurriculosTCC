# Validação da geração da proposta — 05/11/2026

Registro histórico. A estratégia de montagem local descrita aqui foi substituída
pela geração de LaTeX pela IA, conforme solicitação posterior do usuário. Consulte
[a validação atual](model-contract-validation.md).

## Problema e limite do diagnóstico

O adaptador exigia que a OpenAI produzisse tanto o conteúdo estruturado quanto
uma reprodução exata do LaTeX montado por `render_content`. O validador rejeitava
diferenças de formatação com o mesmo código usado para fatos sem evidência:
`proposta_sem_evidencia`. Isso permite rejeitar conteúdo válido por divergência
na montagem do documento.

A resposta rejeitada da tentativa informada pelo usuário não foi persistida.
Não é possível atribuir retrospectivamente essa tentativa a uma regra específica.

## Alteração

- `GeneratedContent` define a saída interna da OpenAI, sem `latex_gerado`.
- O servidor monta o LaTeX pelo renderizador existente. O arquivo de template
  não foi alterado. A resposta pública continua incluindo `latex_gerado`, as
  evidências e os demais campos da proposta.
- O worker continua validando fatos, fontes, datas, alterações, palavras-chave,
  lacunas e correspondência do documento antes de salvar a proposta.
- Mensagens identificam a regra e o campo rejeitados, sem reproduzir conteúdo
  privado. Divergência de template tem código distinto de ausência de evidência.

## Verificações executadas

Na raiz do projeto, com o Python existente em `api/.venv314`:

```powershell
./api/.venv314/Scripts/python.exe -m pytest -q -c api/pyproject.toml api/tests/test_model_proposals.py api/tests/test_adapters.py api/tests/test_proposals.py api/tests/test_flow.py api/tests/test_interviews.py --basetemp=.test-tmp/proposal-render-flow --tb=short
./api/.venv314/Scripts/python.exe -m ruff check api/app/infrastructure/openai_optimizer.py api/app/presentation/schemas.py api/app/service/proposals.py api/tests/test_adapters.py api/tests/test_proposals.py api/tests/test_model_proposals.py
./api/.venv314/Scripts/python.exe -m ruff format --check api/app/infrastructure/openai_optimizer.py api/app/presentation/schemas.py api/app/service/proposals.py api/tests/test_adapters.py api/tests/test_proposals.py api/tests/test_model_proposals.py
./api/.venv314/Scripts/python.exe -m mypy --config-file api/pyproject.toml api/app/infrastructure/openai_optimizer.py api/app/presentation/schemas.py api/app/service/proposals.py
```

Resultado: **64 testes passaram**, lint, formatação e tipagem sem erros. O
transporte simulado do SDK confirma que o schema enviado não exige LaTeX. Os
testes integrados confirmam publicação para revisão de conteúdo válido e rejeição
de competência inventada com liberação da cota. Também foram verificados escape
de caracteres, preservação do preâmbulo, diagnósticos sem dados privados e os
fluxos de entrevista.

Testes usam conteúdo fictício, SQLite temporário e OpenAI simulada. Os fluxos
rodaram fora do sandbox devido ao socketpair do TestClient no Windows. Nenhum
currículo real foi reenviado, nenhuma nova chamada paga foi feita e não houve
compilação real de PDF ou alteração visual.

Reinicie API e worker para carregar a correção. Tentativas já falhadas preservam
seu estado histórico: solicite uma nova otimização do original confirmado.
