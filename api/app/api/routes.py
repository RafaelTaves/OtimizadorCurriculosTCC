from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select

from app.api.dependencies import ServicesDep, SessionDep, UserDep
from app.infrastructure.models import Attempt, Operation, Resume, utcnow
from app.presentation.schemas import (
    AttemptView,
    ConfirmText,
    LatexInput,
    OptimizeInput,
    Proposal,
    Registration,
    ResumePage,
    ResumeView,
    TokenView,
    UsageView,
    UserView,
)
from app.service.errors import AppError
from app.service.resumes import owned_resume

router = APIRouter(prefix="/v1")


def resume_view(resume: Resume) -> ResumeView:
    view = ResumeView.model_validate(resume)
    view.pdf_disponivel = bool(resume.pdf_objeto_key and resume.pdf_revisao == resume.latex_revisao)
    if view.pdf_disponivel:
        view.download_pdf = f"/v1/curriculos/{resume.id}/download?formato=pdf"
    view.avisos = [
        "Revise o conteúdo antes de usar. O serviço não garante aprovação em ATS ou seleções.",
        "O texto confirmado e a vaga serão enviados à OpenAI somente após seu consentimento.",
    ]
    if resume.tipo == "otimizado" and resume.latex_revisao > 1:
        view.avisos.append("A revisão automática da geração não abrange edições manuais do LaTeX.")
    return view


def attempt_view(attempt: Attempt, db: SessionDep) -> AttemptView:
    base = {
        Operation.OPTIMIZATION: "otimizacoes",
        Operation.PREVIEW: "previews",
        Operation.EXPORT: "renderizacoes",
    }[Operation(attempt.tipo_operacao)]
    view = AttemptView.model_validate(
        {
            **{
                name: getattr(attempt, name)
                for name in AttemptView.model_fields
                if hasattr(attempt, name)
            },
            "acompanhamento": f"/v1/{base}/{attempt.id}",
        }
    )
    if attempt.curriculo_gerado_id:
        generated = db.get(Resume, attempt.curriculo_gerado_id)
        if generated and generated.conteudo_estruturado:
            view.proposta = Proposal.model_validate(generated.conteudo_estruturado)
    if (
        attempt.tipo_operacao == Operation.PREVIEW
        and attempt.resultado_temporario_key
        and attempt.expires_at
        and attempt.expires_at > utcnow()
    ):
        view.download_pdf = f"/v1/previews/{attempt.id}/download"
    if attempt.tipo_operacao == Operation.EXPORT and attempt.curriculo_id:
        resume = db.get(Resume, attempt.curriculo_id)
        if resume and resume.pdf_objeto_key and resume.pdf_revisao == attempt.revisao_solicitada:
            view.download_pdf = f"/v1/curriculos/{resume.id}/download?formato=pdf"
    return view


@router.post("/auth/register", status_code=201, tags=["Autenticação"])
def register(data: Registration, container: ServicesDep, db: SessionDep) -> UserView:
    return UserView.model_validate(container.auth.register(db, data))


@router.post("/auth/token", tags=["Autenticação"])
def token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    container: ServicesDep,
    db: SessionDep,
) -> TokenView:
    if len(form.password) > 128 or len(form.username) > 254:
        raise AppError("credenciais_invalidas", "Credenciais inválidas.", 401)
    return container.auth.login(db, form.username, form.password)


@router.get("/auth/me", tags=["Autenticação"])
def me(user: UserDep) -> UserView:
    return UserView.model_validate(user)


@router.post("/curriculos", status_code=201, tags=["Currículos"])
def upload(
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
    arquivo: Annotated[UploadFile, File()],
    descricao_vaga: Annotated[str, Form(min_length=30, max_length=20_000)],
) -> ResumeView:
    try:
        data = arquivo.file.read(container.settings.max_upload_bytes + 1)
        resume = container.resumes.upload(
            db,
            user.id,
            data,
            arquivo.filename or "",
            descricao_vaga,
        )
        return resume_view(resume)
    finally:
        arquivo.file.close()


@router.patch("/curriculos/{resume_id}/texto-extraido", tags=["Currículos"])
def confirm_text(
    resume_id: UUID,
    data: ConfirmText,
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
) -> ResumeView:
    return resume_view(container.resumes.confirm_text(db, user.id, resume_id, data.texto))


@router.get("/curriculos", tags=["Currículos"])
def history(
    user: UserDep,
    db: SessionDep,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResumePage:
    query = select(Resume).where(Resume.usuario_id == user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    resumes = db.scalars(
        query.order_by(Resume.created_at.desc(), Resume.id)
        .offset((pagina - 1) * tamanho)
        .limit(tamanho)
    )
    return ResumePage(
        itens=[resume_view(item) for item in resumes], total=total, pagina=pagina, tamanho=tamanho
    )


@router.get("/curriculos/{resume_id}", tags=["Currículos"])
def get_resume(resume_id: UUID, user: UserDep, db: SessionDep, response: Response) -> ResumeView:
    resume = owned_resume(db, user.id, resume_id)
    response.headers["ETag"] = f'"{resume.latex_revisao}"'
    return resume_view(resume)


@router.put("/curriculos/{resume_id}/latex", tags=["Editor"])
def save_latex(
    resume_id: UUID,
    data: LatexInput,
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ResumeView:
    resume = container.resumes.save_latex(db, user.id, resume_id, data.latex, if_match)
    response.headers["ETag"] = f'"{resume.latex_revisao}"'
    return resume_view(resume)


@router.post("/curriculos/{resume_id}/otimizacoes", status_code=202, tags=["Otimização"])
def optimize(
    resume_id: UUID,
    data: OptimizeInput,
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
    response: Response,
    idempotency_key: Annotated[str | None, Header(max_length=128)] = None,
) -> AttemptView:
    attempt = container.queue.enqueue(
        db,
        user.id,
        resume_id,
        Operation.OPTIMIZATION,
        idempotency_key=idempotency_key,
        consent=data.consentimento_envio_openai,
    )
    view = attempt_view(attempt, db)
    response.headers["Location"] = view.acompanhamento
    return view


def get_attempt(attempt_id: UUID, operation: Operation, user: UserDep, db: SessionDep) -> Attempt:
    attempt = db.scalar(
        select(Attempt).where(
            Attempt.id == attempt_id,
            Attempt.usuario_id == user.id,
            Attempt.tipo_operacao == operation,
        )
    )
    if attempt is None:
        raise AppError("tentativa_inexistente", "Tentativa inexistente.", 404)
    return attempt


@router.get("/otimizacoes/{attempt_id}", tags=["Otimização"])
def optimization(attempt_id: UUID, user: UserDep, db: SessionDep) -> AttemptView:
    return attempt_view(get_attempt(attempt_id, Operation.OPTIMIZATION, user, db), db)


@router.post("/otimizacoes/{attempt_id}/confirmacao", tags=["Otimização"])
def review(attempt_id: UUID, user: UserDep, container: ServicesDep, db: SessionDep) -> AttemptView:
    return attempt_view(container.queue.confirm_review(db, user.id, attempt_id), db)


@router.post("/curriculos/{resume_id}/preview", status_code=202, tags=["Editor"])
def preview(
    resume_id: UUID,
    data: LatexInput,
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
    response: Response,
) -> AttemptView:
    container.resumes.validate_latex(data.latex)
    attempt = container.queue.enqueue(db, user.id, resume_id, Operation.PREVIEW, latex=data.latex)
    view = attempt_view(attempt, db)
    response.headers["Location"] = view.acompanhamento
    return view


@router.get("/previews/{attempt_id}", tags=["Editor"])
def get_preview(attempt_id: UUID, user: UserDep, db: SessionDep) -> AttemptView:
    attempt = get_attempt(attempt_id, Operation.PREVIEW, user, db)
    if attempt.expires_at and attempt.expires_at <= utcnow():
        raise AppError("preview_expirada", "A prévia expirou.", 410)
    return attempt_view(attempt, db)


@router.get("/previews/{attempt_id}/download", tags=["Editor"])
def preview_pdf(
    attempt_id: UUID, user: UserDep, container: ServicesDep, db: SessionDep
) -> Response:
    attempt = get_attempt(attempt_id, Operation.PREVIEW, user, db)
    if attempt.expires_at and attempt.expires_at <= utcnow():
        raise AppError("preview_expirada", "A prévia expirou.", 410)
    if not attempt.resultado_temporario_key:
        raise AppError("pdf_indisponivel", "A prévia ainda não está disponível.", 409)
    return Response(
        container.storage.read(attempt.resultado_temporario_key),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="preview.pdf"'},
    )


@router.post("/curriculos/{resume_id}/renderizacoes", status_code=202, tags=["Editor"])
def render(
    resume_id: UUID,
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
    response: Response,
) -> AttemptView:
    attempt = container.queue.enqueue(db, user.id, resume_id, Operation.EXPORT)
    view = attempt_view(attempt, db)
    response.headers["Location"] = view.acompanhamento
    return view


@router.get("/renderizacoes/{attempt_id}", tags=["Editor"])
def rendering(attempt_id: UUID, user: UserDep, db: SessionDep) -> AttemptView:
    return attempt_view(get_attempt(attempt_id, Operation.EXPORT, user, db), db)


@router.get("/curriculos/{resume_id}/download", tags=["Currículos"])
def download(
    resume_id: UUID,
    user: UserDep,
    container: ServicesDep,
    db: SessionDep,
    formato: Literal["pdf", "tex"] = "pdf",
) -> Response:
    resume = owned_resume(db, user.id, resume_id)
    if formato == "tex":
        if not resume.latex_gerado:
            raise AppError("latex_indisponivel", "Código LaTeX indisponível.", 404)
        data = resume.latex_gerado.encode("utf-8")
        media_type = "application/x-tex"
    else:
        if not resume.pdf_objeto_key or resume.pdf_revisao != resume.latex_revisao:
            raise AppError("pdf_indisponivel", "Renderize a revisão salva antes de baixar.", 409)
        data = container.storage.read(resume.pdf_objeto_key)
        media_type = "application/pdf"
    return Response(
        data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="curriculo.{formato}"'},
    )


@router.delete("/curriculos/{resume_id}", status_code=204, tags=["Currículos"])
def delete_resume(
    resume_id: UUID, user: UserDep, container: ServicesDep, db: SessionDep
) -> Response:
    container.resumes.delete(db, user.id, resume_id)
    return Response(status_code=204)


@router.get("/uso", tags=["Uso"])
def usage(user: UserDep, container: ServicesDep, db: SessionDep) -> UsageView:
    return container.queue.usage(db, user.id)
