from datetime import timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.infrastructure.models import User, utcnow
from app.presentation.schemas import Registration, TokenView
from app.service.errors import AppError


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.passwords = PasswordHash.recommended()
        self.dummy_hash = self.passwords.hash("unused-constant-time-login-password")

    def register(self, session: Session, data: Registration) -> User:
        user = User(
            username=data.username.casefold(),
            email=str(data.email).casefold(),
            hashed_password=self.passwords.hash(data.password),
        )
        session.add(user)
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise AppError("conta_existente", "E-mail ou username já cadastrado.", 409) from exc
        return user

    def login(self, session: Session, identifier: str, password: str) -> TokenView:
        user = session.scalar(
            select(User).where(
                or_(User.username == identifier.casefold(), User.email == identifier.casefold())
            )
        )
        valid = self.passwords.verify(password, user.hashed_password if user else self.dummy_hash)
        if not user or not valid:
            raise AppError("credenciais_invalidas", "Credenciais inválidas.", 401)
        now = utcnow()
        seconds = self.settings.token_minutes * 60
        token = jwt.encode(
            {
                "sub": str(user.id),
                "iat": now,
                "exp": now + timedelta(seconds=seconds),
                "iss": self.settings.jwt_issuer,
            },
            self.settings.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )
        return TokenView(access_token=token, expires_in=seconds)

    def authenticate(self, session: Session, token: str) -> User:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                issuer=self.settings.jwt_issuer,
                options={"require": ["sub", "exp", "iat", "iss"]},
            )
            user = session.get(User, UUID(payload["sub"]))
        except (jwt.InvalidTokenError, ValueError, KeyError) as exc:
            raise AppError("token_invalido", "Token inválido ou expirado.", 401) from exc
        if not user:
            raise AppError("token_invalido", "Token inválido ou expirado.", 401)
        return user
