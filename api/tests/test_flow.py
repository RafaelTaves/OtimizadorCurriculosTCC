from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.infrastructure.models import Attempt, Resume, Status, utcnow
from app.service.errors import ProcessingError
from tests.conftest import SOURCE, enqueue, register, upload_confirm


def test_complete_flow(client, auth, worker, database):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    assert queued.status_code == 202, queued.text
    attempt_id = queued.json()["id"]
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
    assert worker.run_once()
    status = client.get(queued.headers["location"], headers=auth)
    assert status.json()["status"] == "aguardando_revisao", status.text
    generated = status.json()["curriculo_gerado_id"]
    assert status.json()["proposta"]["curriculo"]["contato"][0]["texto"] == "Ana Silva"
    review = client.post(f"/v1/otimizacoes/{attempt_id}/confirmacao", headers=auth)
    assert review.json()["status"] == "concluida", review.text
    current = client.get(f"/v1/curriculos/{generated}", headers=auth)
    assert current.headers["etag"] == '"1"'
    latex = current.json()["latex_gerado"]
    preview = client.post(
        f"/v1/curriculos/{generated}/preview", headers=auth, json={"latex": latex + "\n% temporary"}
    )
    assert preview.status_code == 202, preview.text
    assert worker.run_once()
    state = client.get(preview.headers["location"], headers=auth)
    assert state.json()["status"] == "concluida", state.text
    pdf = client.get(state.json()["download_pdf"], headers=auth)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert client.get(f"/v1/curriculos/{generated}", headers=auth).json()["latex_revisao"] == 1
    saved = client.put(
        f"/v1/curriculos/{generated}/latex",
        headers={**auth, "If-Match": '"1"'},
        json={"latex": latex + "\n% final"},
    )
    assert saved.status_code == 200 and saved.headers["etag"] == '"2"', saved.text
    rendered = client.post(f"/v1/curriculos/{generated}/renderizacoes", headers=auth)
    assert rendered.status_code == 202, rendered.text
    assert worker.run_once()
    state = client.get(rendered.headers["location"], headers=auth)
    assert state.json()["status"] == "concluida", state.text
    assert client.get(f"/v1/curriculos/{generated}/download", headers=auth).status_code == 200
    tex = client.get(f"/v1/curriculos/{generated}/download?formato=tex", headers=auth)
    assert tex.content.endswith(b"% final")
    assert tex.headers["cache-control"] == "no-store"
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
    deleted = client.delete(f"/v1/curriculos/{original}", headers=auth)
    assert deleted.status_code == 204, deleted.text
    assert client.get(f"/v1/curriculos/{generated}", headers=auth).status_code == 404
    assert client.get("/v1/curriculos", headers=auth).json()["total"] == 0
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
    assert not list(worker.storage.root.glob("objects/*"))
    assert not list(worker.storage.root.glob("temporary/*"))


def test_idempotency_quota_and_month_reset(client, auth, worker, database):
    original = upload_confirm(client, auth)
    first = enqueue(client, auth, original, "same")
    second = enqueue(client, auth, original, "same")
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    for i in range(4):
        assert enqueue(client, auth, original, f"different-{i}").status_code == 202
    blocked = enqueue(client, auth, original, "sixth")
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert enqueue(client, auth, original, "same").status_code == 202
    with database.sessions.begin() as session:
        for attempt in session.scalars(select(Attempt)):
            attempt.created_at = utcnow().replace(day=1) - timedelta(days=1)
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
    assert enqueue(client, auth, original, "new-month").status_code == 202


def test_failure_releases_quota_and_retry_same_attempt(client, auth, worker, database):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)

    class BrokenOptimizer:
        def optimize(self, text, job):
            raise ProcessingError("openai_indisponivel", "Indisponível", transient=True)

    worker.optimizer = BrokenOptimizer()
    for i in range(3):
        assert worker.run_once()
        if i < 2:
            assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
        with database.sessions.begin() as session:
            attempt = session.get(Attempt, UUID(queued.json()["id"]))
            attempt.available_at = utcnow() - timedelta(seconds=1)
    state = client.get(queued.headers["location"], headers=auth).json()
    assert state["status"] == "falhou"
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0
    assert client.get(f"/v1/curriculos/{original}", headers=auth).status_code == 200
    with database.sessions() as session:
        attempts = list(session.scalars(select(Attempt)))
        assert len(attempts) == 1 and attempts[0].executions == 3


def test_cross_account_access(client, auth, worker):
    original = upload_confirm(client, auth)
    attempt = enqueue(client, auth, original)
    assert worker.run_once()
    state = client.get(attempt.headers["location"], headers=auth).json()
    generated = state["curriculo_gerado_id"]
    other = register(client, "other")
    for url in (
        f"/v1/curriculos/{original}",
        f"/v1/curriculos/{generated}/download?formato=tex",
        attempt.headers["location"],
    ):
        assert client.get(url, headers=other).status_code == 404
    assert client.delete(f"/v1/curriculos/{original}", headers=other).status_code == 404
    assert (
        client.put(
            f"/v1/curriculos/{generated}/latex",
            headers={**other, "If-Match": '"1"'},
            json={"latex": "hello"},
        ).status_code
        == 404
    )
    assert client.get("/v1/curriculos", headers=other).json()["total"] == 0


def test_etag_and_stale_export(client, auth, worker):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    worker.run_once()
    generated = client.get(queued.headers["location"], headers=auth).json()["curriculo_gerado_id"]
    url = f"/v1/curriculos/{generated}/latex"
    assert client.put(url, headers=auth, json={"latex": "test"}).status_code == 428
    assert (
        client.put(url, headers={**auth, "If-Match": '"0"'}, json={"latex": "test"}).status_code
        == 412
    )
    rendering = client.post(f"/v1/curriculos/{generated}/renderizacoes", headers=auth)
    assert (
        client.put(url, headers={**auth, "If-Match": '"1"'}, json={"latex": "new"}).status_code
        == 200
    )
    worker.run_once()
    state = client.get(rendering.headers["location"], headers=auth).json()
    assert state["codigo_erro"] == "revisao_alterada"
    assert client.get(f"/v1/curriculos/{generated}/download", headers=auth).status_code == 409


def test_requires_auth_consent_confirmation_and_key(client, auth):
    assert client.get("/v1/curriculos").status_code == 401
    original = upload_confirm(client, auth)
    assert (
        client.post(
            f"/v1/curriculos/{original}/otimizacoes",
            headers=auth,
            json={"consentimento_envio_openai": False},
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/v1/curriculos/{original}/otimizacoes",
            headers=auth,
            json={"consentimento_envio_openai": True},
        ).status_code
        == 400
    )
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 0


def test_expired_preview_purged_without_deleting_saved_resume(client, auth, worker, database):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    worker.run_once()
    generated = client.get(queued.headers["location"], headers=auth).json()["curriculo_gerado_id"]
    preview = client.post(
        f"/v1/curriculos/{generated}/preview", headers=auth, json={"latex": "any test latex"}
    )
    worker.run_once()
    with database.sessions.begin() as session:
        attempt = session.get(Attempt, UUID(preview.json()["id"]))
        key = attempt.resultado_temporario_key
        attempt.expires_at = utcnow() - timedelta(seconds=1)
    assert client.get(preview.headers["location"], headers=auth).status_code == 410
    worker.cleanup()
    assert not worker.storage._path(key).exists()
    assert client.get(f"/v1/curriculos/{generated}", headers=auth).status_code == 200


def test_snapshot_and_idempotency_conflict(client, auth, worker, database):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    client.patch(
        f"/v1/curriculos/{original}/texto-extraido",
        headers=auth,
        json={"texto": SOURCE + "\nNovo projeto."},
    )
    assert enqueue(client, auth, original).status_code == 409
    assert worker.run_once()
    assert (
        client.get(queued.headers["location"], headers=auth).json()["status"]
        == "aguardando_revisao"
    )


def test_worker_reclaims_expired_lease_and_rejects_old_claim(client, auth, worker, database):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    old_claim = worker.claim()
    assert worker.claim() is None
    with database.sessions.begin() as session:
        attempt = session.get(Attempt, old_claim.id)
        attempt.lease_until = utcnow() - timedelta(seconds=1)
    assert worker.claim() is None  # recovered with backoff
    with database.sessions.begin() as session:
        attempt = session.get(Attempt, old_claim.id)
        attempt.available_at = utcnow() - timedelta(seconds=1)
    new_claim = worker.claim()
    assert new_claim.lease_token != old_claim.lease_token
    result = worker.optimizer.optimize(SOURCE, "test")
    worker._complete(old_claim, result, None)
    with database.sessions() as session:
        assert not list(session.scalars(select(Resume).where(Resume.tipo == "otimizado")))
    worker._complete(new_claim, result, None)
    assert client.get(queued.headers["location"], headers=auth).json()["status"] == Status.REVIEW


def test_delete_running_attempt_does_not_publish_output(client, auth, worker):
    original = upload_confirm(client, auth)
    enqueue(client, auth, original)
    claim = worker.claim()
    assert client.delete(f"/v1/curriculos/{original}", headers=auth).status_code == 204
    worker._complete(claim, worker.optimizer.optimize(SOURCE, "job"), None)
    assert client.get("/v1/curriculos", headers=auth).json()["total"] == 0
    assert not list(worker.storage.root.glob("objects/*"))


def test_preview_failure_is_safe_and_does_not_consume_ai(client, auth, worker):
    original = upload_confirm(client, auth)
    queued = enqueue(client, auth, original)
    worker.run_once()
    generated = client.get(queued.headers["location"], headers=auth).json()["curriculo_gerado_id"]

    class BrokenCompiler:
        def compile(self, latex):
            raise ProcessingError("latex_invalido", "Verifique a linha 9.")

    worker.compiler = BrokenCompiler()
    preview = client.post(
        f"/v1/curriculos/{generated}/preview", headers=auth, json={"latex": r"\input{/etc/passwd}"}
    )
    worker.run_once()
    result = client.get(preview.headers["location"], headers=auth)
    assert result.json()["codigo_erro"] == "latex_invalido"
    assert client.get("/v1/uso", headers=auth).json()["usado"] == 1
