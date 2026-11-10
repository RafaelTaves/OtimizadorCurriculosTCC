from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.presentation.schemas import StrictModel


class InterviewStatus(StrEnum):
    ANALYZING = "analisando"
    ANSWERING = "aguardando_respostas"
    REVIEW = "aguardando_confirmacao"
    CONFIRMED = "confirmada"
    FAILED = "falhou"
    CANCELLED = "cancelada"
    EXPIRED = "expirada"


class StartInterview(StrictModel):
    consentimento_envio_openai: bool


class AnalysisQuestion(StrictModel):
    pergunta: str = Field(min_length=1, max_length=1500)
    justificativa: str = Field(min_length=1, max_length=1500)
    categoria: Literal["projeto", "experiencia", "formacao", "competencia", "outro"]
    termo_da_vaga: str | None = Field(default=None, min_length=1, max_length=200)
    resposta_origem_id: UUID | None = None


class Question(AnalysisQuestion):
    id: UUID


class AnalysisConflict(StrictModel):
    resposta_origem_id: UUID
    trecho_original: str = Field(min_length=1, max_length=4000)
    trecho_resposta: str = Field(min_length=1, max_length=4000)
    descricao: str = Field(min_length=1, max_length=1500)


class Conflict(AnalysisConflict):
    id: UUID


class InterviewAnalysis(StrictModel):
    perguntas: list[AnalysisQuestion] = Field(max_length=3)
    pronta_para_confirmacao: bool
    conflitos: list[AnalysisConflict] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.pronta_para_confirmacao != (len(self.perguntas) == 0):
            raise ValueError(
                "Análise pronta deve ter zero perguntas; caso contrário, de uma a três"
            )
        return self


class Answer(StrictModel):
    pergunta_id: UUID
    texto: str | None = Field(default=None, min_length=1, max_length=4000)
    pulada: bool = False
    negativa: bool = False

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.pulada == (self.texto is not None) or (self.pulada and self.negativa):
            raise ValueError("Informe texto ou pulo explícito, nunca ambos")
        return self


class RecordedAnswer(Answer):
    id: UUID


class SubmitAnswers(StrictModel):
    rodada: int = Field(ge=1, le=2)
    respostas: list[Answer] = Field(default_factory=list, max_length=3)
    complemento_livre: str | None = Field(default=None, min_length=1, max_length=4000)
    acao: Literal["aprofundar", "encerrar"]


class Complement(StrictModel):
    id: UUID
    texto: str = Field(min_length=1, max_length=12000)
    resposta_origem_id: UUID | None = None
    substitui_trecho_original: str | None = Field(default=None, min_length=1, max_length=4000)


class ReviseComplements(StrictModel):
    complementos: list[Complement] = Field(max_length=24)


class ConflictResolution(StrictModel):
    conflito_id: UUID
    acao: Literal["manter_original", "usar_complemento"]
    complemento_id: UUID | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (self.acao == "usar_complemento") != (self.complemento_id is not None):
            raise ValueError("Usar complemento exige seu ID; manter original não aceita esse ID")
        return self


class ConfirmComplements(StrictModel):
    confirmacao_informacoes: bool
    revisao_conflitos: bool
    resolucoes: list[ConflictResolution] = Field(default_factory=list, max_length=12)


class RoundView(StrictModel):
    id: UUID
    numero: int
    perguntas: list[Question]
    respostas: list[RecordedAnswer]
    complemento_livre: str | None
    complemento_livre_id: UUID | None
    acao_apos_respostas: str | None
    created_at: datetime


class InterviewSummary(StrictModel):
    id: UUID
    curriculo_id: UUID | None
    status: InterviewStatus
    revisao: int
    rodada_atual: int
    created_at: datetime
    expires_at: datetime | None


class InterviewView(InterviewSummary):
    rodadas: list[RoundView]
    complementos: list[Complement]
    conflitos: list[Conflict]
    resolucoes: list[ConflictResolution]
    consentimento_em: datetime
    consentimento_versao: str
    confirmado_em: datetime | None
    tentativa_id: UUID | None
    geracao_id: UUID | None
    codigo_erro: str | None
    mensagem_erro: str | None
    acompanhamento: str


class InterviewPage(StrictModel):
    itens: list[InterviewSummary]
    total: int
    pagina: int
    tamanho: int
