from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.dependencies import Services
from app.api.routes import router
from app.config import Settings, get_settings
from app.infrastructure.database import Database
from app.infrastructure.extraction import ProcessExtractor
from app.infrastructure.storage import LocalStorage
from app.service.auth import AuthService
from app.service.errors import AppError
from app.service.ports import Extractor, Storage
from app.service.resumes import QueueService, ResumeService


class RequestLimitMiddleware:
    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = dict(scope["headers"]).get(b"content-length", b"0")
        try:
            too_large = int(length) > self.limit
        except ValueError:
            too_large = True
        if too_large:
            await JSONResponse(
                {
                    "erro": {
                        "codigo": "requisicao_grande",
                        "mensagem": "Requisição excede o limite.",
                    }
                },
                413,
            )(scope, receive, send)
            return
        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.limit:
                # FastAPI preserves HTTPException while decoding JSON/multipart bodies.
                raise HTTPException(status_code=413, detail="Requisição excede o limite.")
            return message

        async def private_send(message: Message) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + [
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        await self.app(scope, bounded_receive, private_send)


def create_app(
    settings: Settings | None = None,
    *,
    database: Database | None = None,
    storage: Storage | None = None,
    extractor: Extractor | None = None,
) -> FastAPI:
    config = settings or get_settings()
    db = database or Database(config.database_url)
    objects = storage or LocalStorage(config.storage_root)
    app = FastAPI(
        title="Otimização de Currículos",
        version="0.1.0",
        description="API do TCC. Revise o texto extraído e confirme o envio à OpenAI antes de "
        "otimizar. A geração requer revisão humana e não garante aprovação em ATS. "
        "Dados salvos são mantidos até exclusão; prévias expiram em uma hora.",
    )
    app.state.services = Services(
        config,
        db,
        objects,
        AuthService(config),
        ResumeService(config, objects, extractor or ProcessExtractor(config)),
        QueueService(config, objects),
    )
    app.add_middleware(RequestLimitMiddleware, limit=config.max_upload_bytes + 100_000)

    @app.exception_handler(AppError)
    async def application_error(request: Request, exc: AppError) -> JSONResponse:
        headers = dict(exc.headers)
        if exc.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            {"erro": {"codigo": exc.code, "mensagem": exc.message}},
            status_code=exc.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic errors include raw input by default; never echo credentials or CVs.
        details: list[dict[str, Any]] = [
            {"campo": list(error["loc"]), "tipo": error["type"]} for error in exc.errors()
        ]
        return JSONResponse(
            {"erro": {"codigo": "validacao", "mensagem": "Entrada inválida.", "campos": details}},
            422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            {"erro": {"codigo": "http", "mensagem": str(exc.detail)}},
            exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            {
                "erro": {
                    "codigo": "banco_indisponivel",
                    "mensagem": "Persistência temporariamente indisponível.",
                }
            },
            503,
        )

    @app.get("/health", tags=["Operação"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(router)
    return app
