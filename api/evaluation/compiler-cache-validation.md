# Compilação offline: links e fontes

Validação local em 2026-11-10, com Docker Desktop e Python 3.14.

## Causa reproduzida

O documento enviado para investigação falhava na linha 73 (`\url`), com:

```text
Font T1/cmr/m/n/10=ecrm1000 at 10.0pt not loadable:
Metric (TFM) file or installed font not found
```

O script de aquecimento substituía marcadores `@@...@@` ausentes no template
atual. Assim, a amostra de aquecimento nunca entrava no documento compilado.
O template exercitava `\href` com rótulos, mas não `\url` e suas fontes.
Na reconstrução, a amostra nova baixou `t1lmtt.fd`, `ec-lmtt10.tfm` e os recursos
necessários para os links. O nome `ecrm1000` era o diagnóstico da execução
offline sem esses recursos; não indicava um erro de sintaxe na URL.

## Alteração

- Compilar o template e uma amostra fictícia separada, usando seu preâmbulo.
- Exercitar URLs, contatos, tamanhos de título, acentos, caracteres escapados,
  listas e entradas `\cventry`, inclusive com campos opcionais vazios.
- Verificar as duas amostras com `--only-cached` durante a construção.
- Acrescentar teste real de regressão para links e entradas.
- Normalizar a ligatura tipográfica `ﬁ` na asserção de texto do teste de
  isolamento; a verificação de ausência do segredo continua intacta.

O template e o conteúdo do currículo não foram alterados. O isolamento em
tempo de execução permanece: sem rede ou volumes do host, sistema de arquivos
somente leitura e limites de recursos.

## Verificações executadas

Comandos a partir da raiz do projeto, usando diretórios temporários exclusivos
em `tmp` para pytest:

```powershell
docker build -f api/docker/compiler.Dockerfile -t curriculo-tectonic:0.1 api
$env:RUN_COMPILER_TESTS='1'
./api/.venv314/Scripts/python.exe -m pytest -c api/pyproject.toml api/tests/test_compiler_integration.py api/tests/test_adapters.py api/tests/test_flow.py -q
./api/.venv314/Scripts/python.exe -m ruff check api/docker/warm_cache.py api/tests/test_compiler_integration.py
./api/.venv314/Scripts/python.exe -m ruff format --check api/docker/warm_cache.py api/tests/test_compiler_integration.py
```

- Regressão antes da reconstrução: falhou com `latex_invalido`.
- Depois da reconstrução: **26 testes passaram**, incluindo os três testes
  reais de compilação. Os testes HTTP usam SQLite e os adaptadores simulados
  das fixtures; os testes do compilador usam Docker real.
- Documento enviado: compilado pelo `DockerCompiler` e entrypoint de produção,
  offline, em PDF válido com duas páginas e 28.794 bytes; nome presente no texto
  extraído. Não houve chamada à IA nem alteração de dados persistidos.
- Ruff e verificação de formatação: passaram.
- A execução dos testes HTTP no sandbox ficou parada e foi interrompida; a
  execução fora dele concluiu normalmente em 15,17 segundos.

## Limitações observadas

Não foi feita navegação no front nem nova solicitação na conta do usuário.
A tentativa já encerrada exige nova prévia/exportação para usar a imagem nova.
Pacotes ou fontes de outros comandos não exercitados ainda podem exigir novo
aquecimento.

O Tectonic também avisa que o caractere Unicode `–` não existe na fonte itálica
T1 usada nas datas. Ele não impede a compilação, mas é omitido do PDF. O texto
extraído confirmou a ausência dos separadores nas datas do documento enviado.
Usar a notação LaTeX `--` nesses pontos resolve esse detalhe tipográfico; essa
substituição não foi aplicada automaticamente ao currículo nem ao template.
