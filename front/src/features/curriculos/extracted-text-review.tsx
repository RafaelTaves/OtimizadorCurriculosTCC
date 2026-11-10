"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import {
  attemptSchema,
  interviewPageSchema,
  interviewSchema,
  resumeDetailSchema,
  type ResumeDetail,
} from "@/lib/contracts";
import { HttpError, browserRequest } from "@/lib/http/errors";
import { intentKey, clearIntent } from "@/lib/http/intents";

export function ExtractedTextReview({
  resumeId,
  userId,
}: {
  resumeId: string;
  userId: string;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const key = useMemo(
    () => [userId, "curriculo", resumeId],
    [userId, resumeId],
  );
  const query = useQuery({
    queryKey: key,
    queryFn: async () =>
      (
        await browserRequest(
          `/v1/curriculos/${resumeId}`,
          { method: "GET" },
          resumeDetailSchema.parse,
        )
      ).data,
  });
  const resume = query.data;
  const [textDraft, setTextDraft] = useState<string | null>(null);
  const textDraftRef = useRef<string | null>(null);
  const text = textDraft ?? resume?.texto_extraido ?? "";
  const [directConsent, setDirectConsent] = useState(false);
  const [interviewConsent, setInterviewConsent] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"save" | "direct" | "interview" | null>(
    null,
  );
  const dirty = Boolean(resume && text !== (resume.texto_extraido ?? ""));
  const canContinue = Boolean(resume?.texto_confirmado && !dirty);

  async function confirmText() {
    if (!resume) return;
    setBusy("save");
    setError(null);
    setMessage(null);
    const snapshot = text;
    try {
      const result = await browserRequest(
        `/v1/curriculos/${resumeId}/texto-extraido`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto: snapshot }),
        },
        resumeDetailSchema.parse,
      );
      client.setQueryData<ResumeDetail>(key, result.data);
      setDirectConsent(false);
      setInterviewConsent(false);
      if (textDraftRef.current === null || textDraftRef.current === snapshot) {
        textDraftRef.current = null;
        setTextDraft(null);
        setMessage("Texto confirmado. Escolha como deseja continuar.");
      } else {
        setMessage(
          "A versão enviada foi confirmada. Há novas alterações no campo; confirme-as antes de continuar.",
        );
      }
    } catch (cause) {
      if (cause instanceof HttpError && cause.status === 401)
        setError(
          `${cause.message} Seu rascunho permanece nesta página enquanto ela estiver aberta.`,
        );
      else
        setError(
          cause instanceof HttpError
            ? cause.message
            : "Não foi possível confirmar o texto.",
        );
    } finally {
      setBusy(null);
    }
  }

  async function generate(interviewId?: string) {
    if (!resume || !canContinue) return;
    setBusy(interviewId ? "interview" : "direct");
    setError(null);
    try {
      const scope = interviewId
        ? `geracao-entrevista:${userId}:${interviewId}`
        : `geracao-direta:${userId}:${resumeId}`;
      const result = await browserRequest(
        `/v1/curriculos/${resumeId}/otimizacoes`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": intentKey(scope),
          },
          body: JSON.stringify({
            consentimento_envio_openai: true,
            ...(interviewId ? { sessao_complementacao_id: interviewId } : {}),
          }),
        },
        attemptSchema.parse,
      );
      clearIntent(scope);
      router.push(`/otimizacoes/${result.data.id}`);
    } catch (cause) {
      if (
        cause instanceof HttpError &&
        cause.code === "sessao_ja_utilizada" &&
        interviewId
      ) {
        try {
          const current = await browserRequest(
            `/v1/complementacoes/${interviewId}`,
            { method: "GET" },
            interviewSchema.parse,
          );
          if (current.data.geracao_id)
            router.push(`/otimizacoes/${current.data.geracao_id}`);
          else
            setError(
              "A sessão já foi usada. Atualize a entrevista para consultar a tentativa vinculada.",
            );
        } catch {
          setError(
            "A sessão já foi usada. Atualize a entrevista para consultar a tentativa vinculada.",
          );
        }
      } else {
        setError(
          cause instanceof HttpError
            ? cause.message
            : "Não foi possível iniciar a otimização.",
        );
      }
    } finally {
      setBusy(null);
    }
  }

  async function startInterview() {
    if (!resume || !canContinue) return;
    setBusy("interview");
    setError(null);
    try {
      const scope = `entrevista:${userId}:${resumeId}`;
      const result = await browserRequest(
        `/v1/curriculos/${resumeId}/complementacoes`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": intentKey(scope),
          },
          body: JSON.stringify({ consentimento_envio_openai: true }),
        },
        interviewSchema.parse,
      );
      clearIntent(scope);
      router.push(`/complementacoes/${result.data.id}`);
    } catch (cause) {
      if (cause instanceof HttpError && cause.code === "sessao_ativa") {
        try {
          const page = await browserRequest(
            `/v1/curriculos/${resumeId}/complementacoes?pagina=1&tamanho=20`,
            { method: "GET" },
            interviewPageSchema.parse,
          );
          const active = page.data.itens.find((item) =>
            [
              "analisando",
              "aguardando_respostas",
              "aguardando_confirmacao",
              "confirmada",
              "falhou",
            ].includes(item.status),
          );
          if (active) router.push(`/complementacoes/${active.id}`);
          else router.push(`/curriculos/${resumeId}/complementacoes`);
        } catch {
          router.push(`/curriculos/${resumeId}/complementacoes`);
        }
      } else {
        setError(
          cause instanceof HttpError
            ? cause.message
            : "Não foi possível iniciar a entrevista.",
        );
      }
    } finally {
      setBusy(null);
    }
  }

  if (query.error || (!resume && !query.isPending))
    return (
      <DataError
        error={query.error}
        retry={() => void query.refetch()}
        busy={query.isFetching}
      />
    );
  if (!resume)
    return (
      <div className="panel loading-block" role="status">
        Carregando currículo…
      </div>
    );
  if (resume.tipo !== "original") {
    return (
      <section className="panel form-stack">
        <h2>Este documento não é um original</h2>
        <p>
          Abra a tentativa de origem para revisar a proposta antes de editar.
        </p>
        {resume.tentativa_origem_id && (
          <Button asChild>
            <Link href={`/otimizacoes/${resume.tentativa_origem_id}`}>
              Revisar proposta
            </Link>
          </Button>
        )}
      </section>
    );
  }

  return (
    <div className="workflow-stack">
      <section className="panel form-stack">
        <div>
          <h2>{resume.nome_arquivo}</h2>
          <p className="section-intro">
            Confira nomes, datas e conteúdo extraído. Você pode corrigir o texto
            antes de confirmá-lo.
          </p>
        </div>
        {resume.avisos.length > 0 && (
          <div className="notice">
            <ul>
              {resume.avisos.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="form-field">
          <label htmlFor="texto-extraido">Texto extraído</label>
          <p className="field-hint">
            De 50 a 60.000 caracteres. Alterações exigem nova confirmação.
          </p>
          <textarea
            id="texto-extraido"
            className="resume-text"
            value={text}
            maxLength={60_000}
            onChange={(event) => {
              textDraftRef.current = event.target.value;
              setTextDraft(event.target.value);
              setDirectConsent(false);
              setInterviewConsent(false);
              setMessage(null);
            }}
            aria-describedby="texto-contador"
          />
          <div className="form-hint-row">
            <span>
              {resume.texto_confirmado && !dirty
                ? "Texto confirmado"
                : dirty
                  ? "Há alterações não confirmadas"
                  : "Ainda não confirmado"}
            </span>
            <span id="texto-contador" className="character-count">
              {text.length.toLocaleString("pt-BR")} / 60.000
            </span>
          </div>
        </div>
        {resume.descricao_vaga && (
          <details className="read-only-details">
            <summary>Descrição da vaga usada nesta revisão</summary>
            <p>{resume.descricao_vaga}</p>
          </details>
        )}
        {error && (
          <div className="notice warning-notice" role="alert">
            {error}
            {error.includes("sessão expirou") && (
              <>
                {" "}
                <Link
                  href={`/login?retorno=${encodeURIComponent(`/curriculos/${resumeId}/revisao`)}`}
                >
                  Entrar novamente
                </Link>
              </>
            )}
          </div>
        )}
        {message && (
          <p className="status-message" role="status">
            {message}
          </p>
        )}
        <div className="form-actions">
          <Button
            type="button"
            variant="outline"
            disabled={
              busy !== null || text.trim().length < 50 || text.length > 60_000
            }
            onClick={() => void confirmText()}
          >
            {busy === "save"
              ? "Confirmando texto…"
              : resume.texto_confirmado && !dirty
                ? "Confirmar texto novamente"
                : "Confirmar texto"}
          </Button>
          <span className="field-hint">
            A confirmação é necessária até quando você não alterar o texto.
          </span>
        </div>
      </section>

      {canContinue && (
        <section
          className="panel form-stack"
          aria-labelledby="continuar-titulo"
        >
          <div>
            <h2 id="continuar-titulo">Como deseja continuar?</h2>
            <p className="section-intro">
              Cada etapa pede seu consentimento antes de enviar o conteúdo à
              OpenAI.
            </p>
          </div>
          <div className="consent-choice">
            <label className="check-row">
              <input
                type="checkbox"
                checked={directConsent}
                onChange={(event) => setDirectConsent(event.target.checked)}
              />{" "}
              Autorizo enviar o texto confirmado e a descrição da vaga à OpenAI
              para gerar uma proposta.
            </label>
            <Button
              disabled={!directConsent || busy !== null}
              onClick={() => void generate()}
            >
              {busy === "direct"
                ? "Enviando para otimização…"
                : "Gerar com o texto confirmado"}
            </Button>
          </div>
          <div className="consent-choice">
            <label className="check-row">
              <input
                type="checkbox"
                checked={interviewConsent}
                onChange={(event) => setInterviewConsent(event.target.checked)}
              />{" "}
              Autorizo enviar o texto, a vaga e minhas respostas à OpenAI para
              uma entrevista limitada.
            </label>
            <Button
              variant="outline"
              disabled={!interviewConsent || busy !== null}
              onClick={() => void startInterview()}
            >
              {busy === "interview"
                ? "Iniciando entrevista…"
                : "Complementar com perguntas"}
            </Button>
          </div>
        </section>
      )}
      <p className="page-footnote">
        A descrição da vaga foi salva com o original e não pode ser alterada
        nesta etapa. Para usar outra vaga, envie um novo arquivo.
      </p>
    </div>
  );
}
