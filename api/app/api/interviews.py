from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Response

from app.api.dependencies import ServicesDep, SessionDep, UserDep
from app.presentation.interviews import (
    ConfirmComplements,
    InterviewPage,
    InterviewView,
    ReviseComplements,
    StartInterview,
    SubmitAnswers,
)
from app.service.interviews import InterviewResult

router = APIRouter(prefix="/v1", tags=["Complementação"])
ETag = Annotated[str | None, Header(alias="If-Match")]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)]


def present(result: InterviewResult, response: Response) -> InterviewView:
    response.status_code = result.status
    response.headers["ETag"] = f'"{result.view.revisao}"'
    response.headers["Location"] = result.view.acompanhamento
    return result.view


@router.post("/curriculos/{resume_id}/complementacoes", status_code=202)
def start(
    resume_id: UUID,
    data: StartInterview,
    user: UserDep,
    db: SessionDep,
    container: ServicesDep,
    response: Response,
    idempotency_key: IdempotencyKey = None,
) -> InterviewView:
    return present(
        container.interviews.start(db, user.id, resume_id, data, idempotency_key), response
    )


@router.get("/curriculos/{resume_id}/complementacoes")
def history(
    resume_id: UUID,
    user: UserDep,
    db: SessionDep,
    container: ServicesDep,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 20,
) -> InterviewPage:
    return container.interviews.history(db, user.id, resume_id, pagina, tamanho)


@router.get("/complementacoes/{interview_id}")
def get(
    interview_id: UUID, user: UserDep, db: SessionDep, container: ServicesDep, response: Response
) -> InterviewView:
    result = container.interviews.get(db, user.id, interview_id)
    response.headers["ETag"] = f'"{result.revisao}"'
    return result


@router.post("/complementacoes/{interview_id}/respostas", responses={202: {"model": InterviewView}})
def answers(
    interview_id: UUID,
    data: SubmitAnswers,
    user: UserDep,
    db: SessionDep,
    container: ServicesDep,
    response: Response,
    if_match: ETag = None,
    idempotency_key: IdempotencyKey = None,
) -> InterviewView:
    return present(
        container.interviews.answers(db, user.id, interview_id, data, if_match, idempotency_key),
        response,
    )


@router.put("/complementacoes/{interview_id}/complementos")
def revise(
    interview_id: UUID,
    data: ReviseComplements,
    user: UserDep,
    db: SessionDep,
    container: ServicesDep,
    response: Response,
    if_match: ETag = None,
) -> InterviewView:
    return present(container.interviews.revise(db, user.id, interview_id, data, if_match), response)


@router.post("/complementacoes/{interview_id}/confirmacao")
def confirm(
    interview_id: UUID,
    data: ConfirmComplements,
    user: UserDep,
    db: SessionDep,
    container: ServicesDep,
    response: Response,
    if_match: ETag = None,
    idempotency_key: IdempotencyKey = None,
) -> InterviewView:
    return present(
        container.interviews.confirm(db, user.id, interview_id, data, if_match, idempotency_key),
        response,
    )


@router.post("/complementacoes/{interview_id}/cancelamento")
def cancel(
    interview_id: UUID, user: UserDep, db: SessionDep, container: ServicesDep, response: Response
) -> InterviewView:
    return present(container.interviews.cancel(db, user.id, interview_id), response)


@router.post("/complementacoes/{interview_id}/retentativas", status_code=202)
def retry(
    interview_id: UUID,
    user: UserDep,
    db: SessionDep,
    container: ServicesDep,
    response: Response,
    if_match: ETag = None,
    idempotency_key: IdempotencyKey = None,
) -> InterviewView:
    return present(
        container.interviews.retry(db, user.id, interview_id, if_match, idempotency_key), response
    )
