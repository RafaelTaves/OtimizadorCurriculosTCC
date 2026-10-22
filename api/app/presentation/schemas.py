from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints

Text = Annotated[str, StringConstraints(min_length=1, max_length=4000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Registration(StrictModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: Annotated[str, StringConstraints(strip_whitespace=False)] = Field(
        min_length=10, max_length=128
    )


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    username: str
    email: str


class TokenView(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ConfirmText(StrictModel):
    texto: str = Field(min_length=50, max_length=60_000)


class OptimizeInput(StrictModel):
    consentimento_envio_openai: bool


class LatexInput(StrictModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    latex: str = Field(min_length=1, max_length=200_000)


class Fact(StrictModel):
    texto: Text
    trecho_fonte: Text


class Entry(StrictModel):
    titulo: Fact
    instituicao: Fact | None
    periodo: Fact | None
    itens: list[Fact] = Field(max_length=20)


class ResumeContent(StrictModel):
    contato: list[Fact] = Field(min_length=1, max_length=10)
    resumo: Fact | None
    formacao: list[Entry] = Field(max_length=15)
    experiencias: list[Entry] = Field(max_length=20)
    projetos: list[Entry] = Field(max_length=20)
    competencias: list[Fact] = Field(max_length=50)


class Change(StrictModel):
    secao: Text
    antes: Text
    depois: Text
    justificativa: Text
    trecho_fonte: Text


class Keyword(StrictModel):
    termo: Text
    evidencia_no_original: Text


class Gap(StrictModel):
    termo_da_vaga: Text
    motivo_para_nao_incluir: Text


class Proposal(StrictModel):
    curriculo: ResumeContent
    latex_gerado: str = Field(min_length=50, max_length=200_000)
    alteracoes: list[Change] = Field(max_length=80)
    palavras_chave_usadas: list[Keyword] = Field(max_length=80)
    lacunas: list[Gap] = Field(max_length=80)


class ResumeView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tipo: str
    curriculo_origem_id: UUID | None
    nome_arquivo: str
    descricao_vaga: str | None
    texto_extraido: str | None
    texto_confirmado: bool
    latex_gerado: str | None
    latex_revisao: int
    pdf_revisao: int | None
    template_versao: str | None
    conteudo_estruturado: dict[str, object] | None
    created_at: datetime
    updated_at: datetime
    pdf_disponivel: bool = False
    download_pdf: str | None = None
    avisos: list[str] = Field(default_factory=list)


class ResumePage(BaseModel):
    itens: list[ResumeView]
    total: int
    pagina: int
    tamanho: int


class AttemptView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    curriculo_id: UUID | None
    curriculo_gerado_id: UUID | None
    tipo_operacao: str
    status: str
    etapa: str
    codigo_erro: str | None
    mensagem_erro: str | None
    modelo: str | None
    tokens_entrada: int | None
    tokens_saida: int | None
    created_at: datetime
    completed_at: datetime | None
    expires_at: datetime | None
    acompanhamento: str
    proposta: Proposal | None = None
    download_pdf: str | None = None


class UsageView(BaseModel):
    limite: int
    usado: int
    restante: int
    inicio_periodo: datetime
    proximo_reinicio: datetime
