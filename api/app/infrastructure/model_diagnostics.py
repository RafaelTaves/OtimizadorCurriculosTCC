import logging

from pydantic import ValidationError

from app.service.errors import ProcessingError

logger = logging.getLogger(__name__)
FIELDS = {
    "curriculo",
    "contato",
    "resumo",
    "formacao",
    "experiencias",
    "projetos",
    "competencias",
    "texto",
    "trecho_fonte",
    "fonte",
    "titulo",
    "instituicao",
    "periodo",
    "itens",
    "latex_gerado",
    "alteracoes",
    "secao",
    "antes",
    "depois",
    "justificativa",
    "palavras_chave_usadas",
    "termo",
    "lacunas",
    "termo_da_vaga",
    "motivo_para_nao_incluir",
    "perguntas",
    "pergunta",
    "categoria",
    "resposta_origem_id",
    "conflitos",
    "trecho_original",
    "trecho_resposta",
    "descricao",
}


def invalid_model_output(exc: ValidationError, code: str) -> ProcessingError:
    # Never log error strings or inputs: Pydantic includes full private values there.
    fields = [
        ".".join(str(p) if isinstance(p, int) or p in FIELDS else "campo" for p in e["loc"])
        or "resposta"
        for e in exc.errors(include_input=False, include_context=False)[:3]
    ]
    logger.warning("model_output_invalid code=%s fields=%s", code, ",".join(fields))
    return ProcessingError(
        code,
        "A resposta da IA não seguiu o formato esperado em " + ", ".join(fields) + ".",
        transient=True,
    )
