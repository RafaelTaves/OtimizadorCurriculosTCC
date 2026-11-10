# Validação da entrevista — 23/10/2026

Implementação da API descrita em `MDs/featureChat.md`. A interface web não faz parte desta entrega.

Verificações executadas:

- `pytest -q --tb=short`: 71 aprovados; oito ignorados nessa execução (seis PostgreSQL e dois Docker).
- Suíte `pytest -q -m postgres --tb=line`, com a URL configurada e schemas temporários isolados: seis aprovados. Inclui concorrência de criação/geração, orçamento diário de análise, integridade de proprietário, bloqueios e migration com registros anteriores.
- Migration `0002` aplicada ao banco configurado. Contagens de usuários, currículos e tentativas anteriores preservadas; `alembic check` sem novas operações. Os testes da migration verificaram RLS e ausência de permissão de leitura dos papéis de navegador quando existentes.
- Ruff lint e formato: aprovados em `app`, `tests`, `migrations`, `docker` e `evaluation`.
- mypy: aprovado nos 30 arquivos da aplicação.
- OpenAPI exportado sem carregar `.env`; tipos TypeScript regenerados com `openapi-typescript`.
- Front: TypeScript sem erros, Vitest com 17 testes aprovados e formato do arquivo de contratos aprovado pelo Prettier.

As fixtures de currículo, vaga, entrevista e proposta são fictícias. O SDK OpenAI foi exercitado com transporte simulado, incluindo Structured Outputs, `store=False`, contexto explícito e separação de instruções. A geração com complemento confirmado foi testada até a proposta revisável, com evidência identificada e sem alteração do original. Também foram testados ETag, replay idempotente, negativas/pulos, conflitos, limites, falhas, retentativas, recuperação de lease e expurgo de resultados tardios.

Não foram feitas chamadas pagas ao provedor, medições de qualidade/custo/latência real ou compilação com Docker nesta validação; Docker não estava disponível no ambiente. A simulação do compilador não comprova a aparência do PDF. A avaliação humana e com o provedor continua descrita em `evaluation/README.md`.
