"""Provider schemas without redundant fields or cross-field Python validators.

Public API schemas remain unchanged. Derived metadata is calculated locally.
"""

from pydantic import Field

from app.presentation.interviews import AnalysisConflict, AnalysisQuestion, InterviewAnalysis
from app.presentation.schemas import (
    Change,
    Gap,
    Keyword,
    Proposal,
    ResumeContent,
    StrictModel,
    Text,
)


class ModelChange(StrictModel):
    secao: Text
    antes: Text | None
    depois: Text
    justificativa: Text
    trecho_fonte: Text
    fonte: str


class ModelKeyword(StrictModel):
    termo: Text
    trecho_fonte: Text
    fonte: str


class ModelProposal(StrictModel):
    curriculo: ResumeContent
    latex_gerado: str = Field(min_length=50, max_length=200_000)
    alteracoes: list[ModelChange] = Field(max_length=80)
    palavras_chave_usadas: list[ModelKeyword] = Field(max_length=80)
    lacunas: list[Gap] = Field(max_length=80)

    def to_proposal(self) -> Proposal:
        changes = []
        for change in self.alteracoes:
            # A newly written summary is a rewrite of its quoted original evidence,
            # not a factual addition from an interview that never happened.
            before = change.antes
            if before is None and change.fonte == "curriculo_original":
                before = change.trecho_fonte
            changes.append(
                Change(
                    **change.model_dump(exclude={"antes"}),
                    antes=before,
                    tipo="inclusao" if before is None else "reescrita",
                )
            )
        return Proposal(
            curriculo=self.curriculo,
            latex_gerado=self.latex_gerado,
            alteracoes=changes,
            palavras_chave_usadas=[
                Keyword(
                    **keyword.model_dump(),
                    evidencia_no_original=keyword.trecho_fonte
                    if keyword.fonte == "curriculo_original"
                    else None,
                )
                for keyword in self.palavras_chave_usadas
            ],
            lacunas=self.lacunas,
            versao_schema=2,
        )


class ModelAnalysis(StrictModel):
    perguntas: list[AnalysisQuestion] = Field(max_length=3)
    conflitos: list[AnalysisConflict] = Field(max_length=6)

    def to_analysis(self) -> InterviewAnalysis:
        return InterviewAnalysis(
            perguntas=self.perguntas,
            conflitos=self.conflitos,
            pronta_para_confirmacao=not self.perguntas,
        )


class FirstRoundQuestion(AnalysisQuestion):
    # There cannot be an answer reference before the person has answered anything.
    resposta_origem_id: None = None


class FirstRoundAnalysis(StrictModel):
    perguntas: list[FirstRoundQuestion] = Field(max_length=3)
    conflitos: list[AnalysisConflict] = Field(max_length=0)

    def to_analysis(self) -> InterviewAnalysis:
        return InterviewAnalysis(
            perguntas=list(self.perguntas),
            conflitos=self.conflitos,
            pronta_para_confirmacao=not self.perguntas,
        )
