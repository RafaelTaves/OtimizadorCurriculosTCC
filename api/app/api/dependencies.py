from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.database import Database
from app.infrastructure.models import User
from app.service.auth import AuthService
from app.service.ports import Storage
from app.service.resumes import QueueService, ResumeService


@dataclass
class Services:
    settings: Settings
    database: Database
    storage: Storage
    auth: AuthService
    resumes: ResumeService
    queue: QueueService


def services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


def session(container: Annotated[Services, Depends(services)]) -> Iterator[Session]:
    yield from container.database.session()


SessionDep = Annotated[Session, Depends(session)]
ServicesDep = Annotated[Services, Depends(services)]
bearer = OAuth2PasswordBearer(tokenUrl="/v1/auth/token", auto_error=False)


def current_user(
    container: ServicesDep,
    db: SessionDep,
    token: Annotated[str | None, Depends(bearer)],
) -> User:
    return container.auth.authenticate(db, token or "")


UserDep = Annotated[User, Depends(current_user)]
