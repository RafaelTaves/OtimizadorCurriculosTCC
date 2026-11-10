from typing import cast
from uuid import UUID

from app.presentation.interviews import InterviewAnalysis, Question, RecordedAnswer
from app.service.errors import ProcessingError
from app.service.interviews import NEGATIVE
from app.service.proposals import canonical


def validate_analysis(
    analysis: InterviewAnalysis, context: dict[str, object], questions_per_round: int
) -> None:
    def invalid(reason: str) -> None:
        raise ProcessingError(
            "analise_invalida",
            "A análise da IA precisa de correção: " + reason + ".",
            transient=True,
        )

    if len(analysis.perguntas) > questions_per_round:
        invalid("quantidade de perguntas acima do limite")
    history = cast(list[dict[str, object]], context["historico"])
    previous: set[str] = set()
    answers: dict[UUID, str] = {}
    blocked_terms: set[str] = set()
    for round_data in history:
        questions = [
            Question.model_validate(q) for q in cast(list[object], round_data["perguntas"])
        ]
        by_id = {q.id: q for q in questions}
        previous.update(canonical(q.pergunta) for q in questions)
        for raw in cast(list[object], round_data["respostas"]):
            answer = RecordedAnswer.model_validate(raw)
            if answer.pulada or answer.negativa or NEGATIVE.search(answer.texto or ""):
                previous_question = by_id.get(answer.pergunta_id)
                if previous_question and previous_question.termo_da_vaga:
                    blocked_terms.add(canonical(previous_question.termo_da_vaga))
            elif answer.texto:
                answers[answer.id] = answer.texto
        if round_data.get("complemento_livre_id") and round_data.get("complemento_livre"):
            free_text = str(round_data["complemento_livre"])
            if not NEGATIVE.search(free_text):
                answers[UUID(str(round_data["complemento_livre_id"]))] = free_text
    seen: set[str] = set()
    for question in analysis.perguntas:
        key = canonical(question.pergunta)
        if key in previous or key in seen:
            invalid("pergunta repetida; não repita perguntas anteriores nem nesta rodada")
        seen.add(key)
        if question.termo_da_vaga:
            if canonical(question.termo_da_vaga) not in canonical(str(context["descricao_vaga"])):
                invalid("termo_da_vaga deve ser um trecho literal da vaga ou null")
            if canonical(question.termo_da_vaga) in blocked_terms:
                invalid("pergunta sobre requisito já pulado ou negado")
        if int(str(context["rodada"])) > 1 and question.resposta_origem_id not in answers:
            invalid("segunda rodada exige resposta_origem_id de uma resposta afirmativa")
        if question.resposta_origem_id and question.resposta_origem_id not in answers:
            invalid("resposta_origem_id inexistente; na primeira rodada use null")
    for conflict in analysis.conflitos:
        if (
            conflict.trecho_original not in str(context["curriculo_confirmado"])
            or conflict.resposta_origem_id not in answers
            or conflict.trecho_resposta not in answers[conflict.resposta_origem_id]
        ):
            invalid("conflito sem trechos literais do original e da resposta identificada")
