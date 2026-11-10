"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import {
  attemptSchema,
  resumeDetailSchema,
  type ResumeDetail,
} from "@/lib/contracts";
import { browserFile, browserRequest, HttpError } from "@/lib/http/errors";

const CodeMirror = dynamic(() => import("@uiw/react-codemirror"), {
  ssr: false,
  loading: () => (
    <div className="editor-loading" role="status">
      Carregando editor…
    </div>
  ),
});
const PdfViewer = dynamic(
  () => import("./pdf-viewer").then((module) => module.PdfViewer),
  {
    ssr: false,
    loading: () => (
      <div className="editor-loading" role="status">
        Carregando visualizador…
      </div>
    ),
  },
);

const maxLatexBytes = 200_000;
function byteLength(value: string) {
  return new TextEncoder().encode(value).byteLength;
}

export function ResumeEditor({
  resumeId,
  userId,
}: {
  resumeId: string;
  userId: string;
}) {
  const client = useQueryClient();
  const queryKey = useMemo(
    () => [userId, "curriculo", resumeId],
    [userId, resumeId],
  );
  const etag = useRef<string | null>(null);
  const initialized = useRef(false);
  const currentCode = useRef("");
  const pendingDownload = useRef<string | null>(null);
  const [code, setCode] = useState("");
  const [savedCode, setSavedCode] = useState("");
  const [conflict, setConflict] = useState(false);
  const [remote, setRemote] = useState<ResumeDetail | null>(null);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const [previewSnapshot, setPreviewSnapshot] = useState("");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [exportId, setExportId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"code" | "preview">("code");

  const resumeQuery = useQuery({
    queryKey,
    queryFn: async () => {
      const result = await browserRequest(
        "/v1/curriculos/" + resumeId,
        { method: "GET" },
        resumeDetailSchema.parse,
      );
      return { resume: result.data, etag: result.headers.get("etag") };
    },
    retry: false,
  });
  const resume = resumeQuery.data?.resume;
  const refetchResume = resumeQuery.refetch;
  useEffect(() => {
    if (resume && !initialized.current) {
      initialized.current = true;
      etag.current = resumeQuery.data?.etag ?? null;
      currentCode.current = resume.latex_gerado ?? "";
      setCode(currentCode.current);
      setSavedCode(currentCode.current);
    }
  }, [resume, resumeQuery.data?.etag]);
  const dirty = code !== savedCode;
  const bytes = byteLength(code);
  const editorHeight = `${Math.min(640, Math.max(260, code.split("\n").length * 22 + 24))}px`;

  const previewQuery = useQuery({
    queryKey: [userId, "preview", previewId],
    queryFn: async () =>
      (
        await browserRequest(
          "/v1/previews/" + previewId,
          { method: "GET" },
          attemptSchema.parse,
        )
      ).data,
    enabled: Boolean(previewId),
    refetchInterval: (state) =>
      ["pendente", "processando"].includes(state.state.data?.status ?? "")
        ? Math.min(
            10_000,
            2_000 * 2 ** Math.floor(state.state.dataUpdateCount / 3),
          )
        : false,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
  });
  const exportQuery = useQuery({
    queryKey: [userId, "renderizacao", exportId],
    queryFn: async () =>
      (
        await browserRequest(
          "/v1/renderizacoes/" + exportId,
          { method: "GET" },
          attemptSchema.parse,
        )
      ).data,
    enabled: Boolean(exportId),
    refetchOnMount: (query) => query.state.data?.status !== "concluida",
    refetchInterval: (state) =>
      ["pendente", "processando"].includes(state.state.data?.status ?? "")
        ? 1_000
        : false,
    refetchIntervalInBackground: true,
    refetchOnWindowFocus: true,
    retry: false,
  });

  const previewAttempt = previewQuery.data;
  const exportAttempt = exportQuery.data;
  const exporting = Boolean(
    exportId &&
    !exportQuery.error &&
    (!exportAttempt ||
      ["pendente", "processando"].includes(exportAttempt.status)),
  );
  const actionsDisabled =
    busy !== null ||
    exporting ||
    conflict ||
    !code.trim() ||
    bytes > maxLatexBytes;

  useEffect(() => {
    if (previewAttempt?.status !== "concluida" || !previewAttempt.download_pdf)
      return;
    let active = true;
    let url: string | null = null;
    void browserFile("/v1/previews/" + previewAttempt.id + "/download")
      .then((blob) => {
        if (!active) return;
        url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      })
      .catch((cause) => {
        if (active)
          setError(
            cause instanceof HttpError
              ? cause.message
              : "Não foi possível abrir a prévia.",
          );
      });
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
      setPreviewUrl((current) => (current === url ? null : current));
    };
  }, [
    previewAttempt?.id,
    previewAttempt?.status,
    previewAttempt?.download_pdf,
  ]);

  useEffect(() => {
    if (
      exportAttempt?.status !== "concluida" ||
      pendingDownload.current !== exportAttempt.id
    )
      return;
    // Consume the intent once, including when polling or window focus refetches.
    pendingDownload.current = null;
    setBusy("download");
    setMessage("PDF gerado. Iniciando download…");
    void browserFile("/v1/curriculos/" + resumeId + "/download?formato=pdf")
      .then((blob) => {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "curriculo.pdf";
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
        setMessage("PDF final gerado. Download iniciado.");
      })
      .catch((cause) => {
        setMessage(null);
        setError(
          cause instanceof HttpError
            ? cause.message
            : "Não foi possível baixar o PDF. Clique em Gerar PDF Final para tentar novamente.",
        );
      })
      .finally(() => {
        setBusy(null);
        void refetchResume();
      });
  }, [exportAttempt?.id, exportAttempt?.status, resumeId, refetchResume]);

  async function reloadCurrent() {
    const result = await resumeQuery.refetch();
    return result.data;
  }

  async function saveSnapshot(snapshot: string) {
    if (!etag.current)
      throw new HttpError(
        428,
        "revisao_obrigatoria",
        "Atualize o currículo antes de salvar.",
      );
    const result = await browserRequest(
      "/v1/curriculos/" + resumeId + "/latex",
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          "If-Match": etag.current,
        },
        body: JSON.stringify({ latex: snapshot }),
      },
      resumeDetailSchema.parse,
    );
    etag.current = result.headers.get("etag") ?? etag.current;
    client.setQueryData(queryKey, { resume: result.data, etag: etag.current });
    setSavedCode(result.data.latex_gerado ?? snapshot);
    if (currentCode.current === snapshot) {
      currentCode.current = result.data.latex_gerado ?? snapshot;
      setCode(currentCode.current);
    }
    return result.data;
  }

  async function handleActionError(cause: unknown, fallback: string) {
    if (cause instanceof HttpError && [412, 428].includes(cause.status)) {
      setConflict(true);
      const latest = await reloadCurrent();
      setRemote(latest?.resume ?? null);
      setError(
        "O currículo mudou em outra janela. Seu rascunho foi preservado; compare as versões antes de escolher como continuar.",
      );
    } else setError(cause instanceof HttpError ? cause.message : fallback);
  }

  function adoptRemoteRevision() {
    if (!resumeQuery.data) return;
    etag.current = resumeQuery.data.etag;
    setSavedCode(resumeQuery.data.resume.latex_gerado ?? "");
    setConflict(false);
    setRemote(null);
    setMessage(
      "Revisão atualizada. Seu rascunho foi mantido; atualize a prévia ou gere o PDF após conferir a comparação.",
    );
  }

  async function updatePreview() {
    if (!resume || actionsDisabled) return;
    setBusy("preview");
    setError(null);
    setMessage(null);
    const snapshot = code;
    try {
      const updated = await saveSnapshot(snapshot);
      const savedSnapshot = updated.latex_gerado ?? snapshot;
      const result = await browserRequest(
        "/v1/curriculos/" + resumeId + "/preview",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ latex: savedSnapshot }),
        },
        attemptSchema.parse,
      );
      setPreviewSnapshot(savedSnapshot);
      setPreviewUrl(null);
      setPreviewId(result.data.id);
      setActiveTab("preview");
      setMessage("Alterações salvas. Prévia solicitada.");
    } catch (cause) {
      await handleActionError(
        cause,
        "Não foi possível salvar e atualizar a prévia.",
      );
    } finally {
      setBusy(null);
    }
  }

  async function renderFinal() {
    if (!resume || actionsDisabled) return;
    pendingDownload.current = null;
    setExportId(null);
    setBusy("render");
    setError(null);
    setMessage(null);
    const snapshot = code;
    try {
      await saveSnapshot(snapshot);
      const result = await browserRequest(
        "/v1/curriculos/" + resumeId + "/renderizacoes",
        { method: "POST" },
        attemptSchema.parse,
      );
      pendingDownload.current = result.data.id;
      client.setQueryData(
        [userId, "renderizacao", result.data.id],
        result.data,
      );
      setExportId(result.data.id);
    } catch (cause) {
      await handleActionError(
        cause,
        "Não foi possível salvar e gerar o PDF final.",
      );
    } finally {
      setBusy(null);
    }
  }

  if ((!resume && resumeQuery.error) || (!resume && !resumeQuery.isPending))
    return (
      <DataError
        error={resumeQuery.error}
        retry={() => void resumeQuery.refetch()}
        busy={resumeQuery.isFetching}
      />
    );
  if (!resume)
    return (
      <div className="panel loading-block" role="status">
        Carregando editor…
      </div>
    );
  if (resume.tipo !== "otimizado")
    return (
      <section className="panel form-stack">
        <h2>Este documento não tem um editor</h2>
        <p>
          O editor fica disponível para uma versão otimizada depois da revisão
          da proposta.
        </p>
        {resume.tentativa_origem_id && (
          <Button asChild>
            <Link href={"/otimizacoes/" + resume.tentativa_origem_id}>
              Revisar proposta
            </Link>
          </Button>
        )}
      </section>
    );
  if (!resume.revisao_humana_confirmada)
    return (
      <section className="panel form-stack">
        <h2>Revise a proposta antes de editar</h2>
        <p>
          O conteúdo só pode ser editado ou exportado depois da confirmação
          humana.
        </p>
        {resume.tentativa_origem_id ? (
          <Button asChild>
            <Link href={"/otimizacoes/" + resume.tentativa_origem_id}>
              Abrir proposta para revisão
            </Link>
          </Button>
        ) : (
          <p className="field-hint">
            A API ainda não associou uma tentativa de origem a esta versão.
          </p>
        )}
      </section>
    );

  return (
    <div className="workflow-stack">
      <section className="panel editor-summary">
        <div>
          <span className="context-label">
            Versão otimizada · revisão {resume.latex_revisao}
          </span>
          <h2>{resume.nome_arquivo}</h2>
          <p className="section-intro">
            Atualizar a prévia salva suas alterações. Gerar PDF Final salva e
            baixa o currículo automaticamente.
          </p>
        </div>
        <div className="editor-actions">
          <Button
            variant="outline"
            disabled={actionsDisabled}
            onClick={() => void updatePreview()}
          >
            {busy === "preview"
              ? "Salvando e atualizando…"
              : "Atualizar prévia"}
          </Button>
          <Button disabled={actionsDisabled} onClick={() => void renderFinal()}>
            {busy === "download"
              ? "Baixando PDF…"
              : busy === "render" || exporting
                ? "Gerando PDF…"
                : "Gerar PDF Final"}
          </Button>
        </div>
      </section>

      {exportQuery.error && (
        <DataError
          error={exportQuery.error}
          retry={() => void exportQuery.refetch()}
          busy={exportQuery.isFetching}
        />
      )}
      {exporting && (
        <p role="status" className="status-message">
          Alterações salvas. Gerando o PDF final; o download iniciará
          automaticamente.
        </p>
      )}
      {exportAttempt?.status === "falhou" && (
        <div className="notice warning-notice" role="alert">
          <strong>{exportAttempt.codigo_erro ?? "PDF não gerado"}</strong>
          <p>
            {exportAttempt.mensagem_erro ??
              "A revisão foi preservada. Corrija o LaTeX e gere o PDF novamente."}
          </p>
        </div>
      )}
      {conflict && (
        <section className="panel conflict-item" role="alert">
          <h2>O currículo mudou em outra revisão</h2>
          <p>
            Seu rascunho continua no editor. Compare o texto salvo mais recente
            antes de usar a revisão atual como base para um novo salvamento.
          </p>
          {remote && (
            <details>
              <summary>Comparar revisão salva e rascunho</summary>
              <div className="before-after">
                <div>
                  <span>Versão mais recente na API</span>
                  <pre>{remote.latex_gerado}</pre>
                </div>
                <div>
                  <span>Seu rascunho</span>
                  <pre>{code}</pre>
                </div>
              </div>
            </details>
          )}
          <Button
            variant="outline"
            disabled={!resumeQuery.data?.etag}
            onClick={adoptRemoteRevision}
          >
            Usar ETag atual e manter meu rascunho
          </Button>
        </section>
      )}
      {resumeQuery.error && (
        <p className="field-error" role="alert">
          {resumeQuery.error instanceof Error
            ? resumeQuery.error.message
            : "Não foi possível atualizar o currículo."}
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
          {error.includes("sessão expirou") && (
            <>
              {" "}
              <Link
                href={
                  "/login?retorno=%2Fcurriculos%2F" + resumeId + "%2Feditor"
                }
              >
                Entre novamente
              </Link>
            </>
          )}
        </p>
      )}
      {message && (
        <p className="status-message" role="status">
          {message}
        </p>
      )}
      {bytes > maxLatexBytes && (
        <p className="field-error" role="alert">
          O código excede 200.000 bytes UTF-8.
        </p>
      )}
      {dirty && (
        <p className="field-hint">
          Rascunho não salvo · {bytes.toLocaleString("pt-BR")} /{" "}
          {maxLatexBytes.toLocaleString("pt-BR")} bytes
        </p>
      )}
      <div className="editor-tabs" role="tablist" aria-label="Área do editor">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "code"}
          onClick={() => setActiveTab("code")}
        >
          Código
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "preview"}
          onClick={() => setActiveTab("preview")}
        >
          Prévia
        </button>
      </div>
      <div className="editor-panes">
        <section
          className={
            "panel editor-pane" + (activeTab === "code" ? " is-active" : "")
          }
          aria-label="Código LaTeX"
        >
          <div className="panel-heading">
            <h2>LaTeX</h2>
            <span className="character-count">
              {code.split("\n").length} linhas
            </span>
          </div>
          <CodeMirror
            value={code}
            height={editorHeight}
            theme="light"
            basicSetup={{ lineNumbers: true, foldGutter: true }}
            onChange={(value) => {
              currentCode.current = value;
              setCode(value);
              setMessage(null);
            }}
          />
          <noscript>
            <p>O editor interativo requer JavaScript.</p>
          </noscript>
          <p className="field-hint">
            A revisão factual automática não abrange alterações manuais.
          </p>
          <details className="latex-fallback-details">
            <summary>Alternativa de edição em texto</summary>
            <textarea
              id="latex-fallback"
              className="latex-fallback"
              value={code}
              onChange={(event) => {
                currentCode.current = event.target.value;
                setCode(event.target.value);
              }}
              spellCheck={false}
            />
          </details>
        </section>
        <section
          className={
            "panel editor-pane preview-pane" +
            (activeTab === "preview" ? " is-active" : "")
          }
          aria-label="Prévia em PDF"
        >
          <div className="panel-heading">
            <h2>Prévia</h2>
            {previewAttempt?.status && (
              <span className="status-label">{previewAttempt.status}</span>
            )}
          </div>
          {previewQuery.error && (
            <DataError
              error={previewQuery.error}
              retry={() => void previewQuery.refetch()}
              busy={previewQuery.isFetching}
            />
          )}
          {previewAttempt &&
            ["pendente", "processando"].includes(previewAttempt.status) && (
              <p role="status" className="status-message">
                Compilando a prévia da captura solicitada…
              </p>
            )}
          {previewAttempt?.status === "falhou" && (
            <div className="notice warning-notice">
              <strong>
                {previewAttempt.codigo_erro ?? "Prévia indisponível"}
              </strong>
              <p>
                {previewAttempt.mensagem_erro ??
                  "Confira o LaTeX e solicite uma nova prévia."}
              </p>
            </div>
          )}
          {previewUrl && (
            <>
              <p className="field-hint">
                {code === previewSnapshot
                  ? "Prévia do rascunho enviado."
                  : "Esta prévia representa uma versão anterior do rascunho."}
              </p>
              <PdfViewer url={previewUrl} />
            </>
          )}
          {!previewAttempt && (
            <p className="empty-inline">
              Atualize a prévia para salvar as alterações e conferir o currículo
              aqui.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}
