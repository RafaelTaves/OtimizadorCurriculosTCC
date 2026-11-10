"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import {
  attemptSchema,
  interviewSchema,
  type Complement,
  type InterviewData,
} from "@/lib/contracts";
import { HttpError, browserRequest, browserGet } from "@/lib/http/errors";
import { intentKey, clearIntent } from "@/lib/http/intents";
import { interviewPresentationLimits as limits } from "./limits";

type Resolution = {
  conflito_id: string;
  acao: "manter_original" | "usar_complemento";
  complemento_id?: string;
};
type AnswerDraft = { texto: string; pulada: boolean; negativa: boolean };
const stateNames: Record<string, string> = {
  analisando: "Analisando o currículo e a vaga",
  aguardando_respostas: "Aguardando suas respostas",
  aguardando_confirmacao: "Revise os complementos antes de confirmar",
  confirmada: "Fontes confirmadas",
  falhou: "A análise não foi concluída",
  cancelada: "Entrevista cancelada",
  expirada: "Entrevista expirada",
};

function sameList(a: Complement[], b: Complement[]) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function InterviewPanel({
  interviewId,
  userId,
}: {
  interviewId: string;
  userId: string;
}) {
  const queryKey = useMemo(
    () => [userId, "complementacao", interviewId],
    [userId, interviewId],
  );
  const query = useQuery({
    queryKey,
    queryFn: async () => {
      const result = await browserRequest(
        "/v1/complementacoes/" + interviewId,
        { method: "GET" },
        interviewSchema.parse,
      );
      return { interview: result.data, etag: result.headers.get("etag") };
    },
    staleTime: 0,
    refetchInterval: (state) => {
      if (state.state.data?.interview.status !== "analisando") return false;
      return Math.min(
        10_000,
        2_000 * 2 ** Math.floor(state.state.dataUpdateCount / 3),
      );
    },
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    retry: false,
  });
  const refresh = async () => {
    const current = await query.refetch();
    return { data: current.data?.interview, etag: current.data?.etag ?? null };
  };
  if (query.error || (!query.data && !query.isPending))
    return (
      <DataError
        error={query.error}
        retry={() => void query.refetch()}
        busy={query.isFetching}
      />
    );
  if (!query.data)
    return (
      <div className="panel loading-block" role="status">
        Carregando entrevista…
      </div>
    );
  return (
    <InterviewSession
      key={interviewId + ":" + query.data.interview.status}
      interviewId={interviewId}
      userId={userId}
      queryKey={queryKey}
      initialEtag={query.data.etag}
      interview={query.data.interview}
      refresh={refresh}
    />
  );
}

function InterviewSession({
  interviewId,
  userId,
  queryKey,
  initialEtag,
  interview,
  refresh,
}: {
  interviewId: string;
  userId: string;
  queryKey: string[];
  initialEtag: string | null;
  interview: InterviewData;
  refresh: () => Promise<{
    data: InterviewData | undefined;
    etag: string | null;
  }>;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const etag = useRef<string | null>(initialEtag);
  const [answers, setAnswers] = useState<Record<string, AnswerDraft>>({});
  const [freeText, setFreeText] = useState("");
  const [complements, setComplements] = useState<Complement[]>(() =>
    interview.complementos.map((item) => ({ ...item })),
  );
  const [resolutions, setResolutions] = useState<Record<string, Resolution>>(
    () => {
      const initial: Record<string, Resolution> = {};
      interview.resolucoes.forEach((item) => {
        initial[item.conflito_id] = {
          conflito_id: item.conflito_id,
          acao: item.acao,
          ...(item.complemento_id
            ? { complemento_id: item.complemento_id }
            : {}),
        };
      });
      return initial;
    },
  );
  const [savedConfirmations, setSavedConfirmations] = useState({
    information: false,
    conflicts: false,
  });
  const [generationConsent, setGenerationConsent] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const roundQuestions =
    interview.rodadas.find((round) => round.numero === interview.rodada_atual)
      ?.perguntas ?? [];
  const dirtyComplements = !sameList(complements, interview.complementos);
  const totalCharacters = complements.reduce(
    (sum, item) => sum + item.texto.length,
    0,
  );
  const missingQuestions = roundQuestions.filter((item) => {
    const answer = answers[item.id];
    return !answer?.pulada && !answer?.negativa && !answer?.texto.trim();
  }).length;
  const conflictsComplete = interview.conflitos.every(
    (item) => resolutions[item.id],
  );

  useEffect(() => {
    if (interview?.status === "cancelada" || interview?.status === "expirada") {
      clearIntent("respostas:" + userId + ":" + interviewId + ":1:encerrar");
    }
  }, [interview?.status, interviewId, userId]);

  async function refreshAfterMutation(result: {
    data: InterviewData;
    headers: Headers;
  }) {
    etag.current = result.headers.get("etag") ?? etag.current;
    const latest = client.getQueryData<{
      interview: InterviewData;
      etag: string | null;
    }>(queryKey);
    if (!latest || result.data.revisao >= latest.interview.revisao)
      client.setQueryData(queryKey, {
        interview: result.data,
        etag: etag.current,
      });
    // An idempotent replay can return its original snapshot; always read the current session afterward.
    const refreshed = await refresh();
    etag.current = refreshed.etag ?? etag.current;
  }

  function showError(cause: unknown) {
    if (cause instanceof HttpError && cause.status === 412) {
      setError(
        "A entrevista mudou em outra janela. Atualizamos o estado; confira os dados antes de continuar.",
      );
      void refresh();
    } else if (
      cause instanceof HttpError &&
      cause.code === "sessao_ja_utilizada"
    ) {
      setError(
        "Esta entrevista já possui uma geração. Atualize a sessão para abrir a tentativa vinculada.",
      );
      void refresh();
    } else
      setError(
        cause instanceof HttpError
          ? cause.message
          : "Não foi possível salvar esta etapa.",
      );
  }

  async function sendRound(
    action: "aprofundar" | "encerrar",
    failedSession = false,
  ) {
    if (!interview) return;
    setBusy(action);
    setError(null);
    setNotice(null);
    const responses = failedSession
      ? []
      : roundQuestions.map((question) => {
          const draft = answers[question.id] ?? {
            texto: "",
            pulada: false,
            negativa: false,
          };
          if (draft.pulada)
            return {
              pergunta_id: question.id,
              texto: null,
              pulada: true,
              negativa: false,
            };
          const text =
            draft.texto.trim() ||
            (draft.negativa ? "Não tenho essa experiência." : "");
          if (!text && action === "encerrar")
            return {
              pergunta_id: question.id,
              texto: null,
              pulada: true,
              negativa: false,
            };
          return {
            pergunta_id: question.id,
            texto: text || null,
            pulada: false,
            negativa: draft.negativa,
          };
        });
    if (responses.some((item) => !item.pulada && !item.texto)) {
      setBusy(null);
      setError(
        action === "encerrar"
          ? "Informe uma resposta, marque a opção negativa ou pule a pergunta."
          : "Responda cada pergunta ou marque-a como pulada antes de aprofundar.",
      );
      return;
    }
    const scope =
      "respostas:" +
      userId +
      ":" +
      interviewId +
      ":" +
      interview.rodada_atual +
      ":" +
      action;
    try {
      const result = await browserRequest(
        "/v1/complementacoes/" + interviewId + "/respostas",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(etag.current ? { "If-Match": etag.current } : {}),
            "Idempotency-Key": intentKey(scope),
          },
          body: JSON.stringify({
            rodada: interview.rodada_atual,
            respostas: responses,
            complemento_livre: freeText.trim() || null,
            acao: action,
          }),
        },
        interviewSchema.parse,
      );
      await refreshAfterMutation(result);
      setAnswers({});
      setFreeText("");
      setNotice("Respostas salvas. Confira o estado atualizado da entrevista.");
    } catch (cause) {
      showError(cause);
    } finally {
      setBusy(null);
    }
  }

  async function saveComplements() {
    if (!interview) return;
    if (
      complements.length > limits.complementItems ||
      totalCharacters > limits.totalConfirmedCharacters
    ) {
      setError(
        "A lista pode ter até " +
          limits.complementItems +
          " itens e " +
          limits.totalConfirmedCharacters.toLocaleString("pt-BR") +
          " caracteres no total.",
      );
      return;
    }
    setBusy("save-complements");
    setError(null);
    setNotice(null);
    const snapshot = complements.map((item) => ({ ...item }));
    try {
      const result = await browserRequest(
        "/v1/complementacoes/" + interviewId + "/complementos",
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            ...(etag.current ? { "If-Match": etag.current } : {}),
          },
          body: JSON.stringify({ complementos: snapshot }),
        },
        interviewSchema.parse,
      );
      await refreshAfterMutation(result);
      setNotice(
        "Complementos salvos. Revise as confirmações e as divergências.",
      );
    } catch (cause) {
      showError(cause);
    } finally {
      setBusy(null);
    }
  }

  async function confirmComplements() {
    if (
      !interview ||
      dirtyComplements ||
      !conflictsComplete ||
      !savedConfirmations.information ||
      !savedConfirmations.conflicts
    )
      return;
    setBusy("confirm");
    setError(null);
    setNotice(null);
    const scope = "confirmacao:" + userId + ":" + interviewId;
    const resolutionsPayload = interview.conflitos
      .map((item) => resolutions[item.id])
      .filter((item): item is Resolution => Boolean(item));
    try {
      const result = await browserRequest(
        "/v1/complementacoes/" + interviewId + "/confirmacao",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(etag.current ? { "If-Match": etag.current } : {}),
            "Idempotency-Key": intentKey(scope),
          },
          body: JSON.stringify({
            confirmacao_informacoes: true,
            revisao_conflitos: true,
            resolucoes: resolutionsPayload,
          }),
        },
        interviewSchema.parse,
      );
      await refreshAfterMutation(result);
      clearIntent(scope);
      setNotice(
        "Fontes confirmadas. Agora você pode pedir uma geração com novo consentimento.",
      );
    } catch (cause) {
      showError(cause);
    } finally {
      setBusy(null);
    }
  }

  async function retryAnalysis() {
    if (!interview) return;
    setBusy("retry");
    setError(null);
    const scope =
      "retentativa:" +
      userId +
      ":" +
      interviewId +
      ":" +
      interview.rodada_atual;
    try {
      const result = await browserRequest(
        "/v1/complementacoes/" + interviewId + "/retentativas",
        {
          method: "POST",
          headers: {
            ...(etag.current ? { "If-Match": etag.current } : {}),
            "Idempotency-Key": intentKey(scope),
          },
        },
        interviewSchema.parse,
      );
      await refreshAfterMutation(result);
    } catch (cause) {
      showError(cause);
    } finally {
      setBusy(null);
    }
  }

  async function cancelInterview() {
    setBusy("cancel");
    setError(null);
    try {
      const result = await browserRequest(
        "/v1/complementacoes/" + interviewId + "/cancelamento",
        {
          method: "POST",
          headers: etag.current ? { "If-Match": etag.current } : {},
        },
        interviewSchema.parse,
      );
      await refreshAfterMutation(result);
      setAnswers({});
      setFreeText("");
      setComplements([]);
      setResolutions({});
      setNotice("Entrevista cancelada. O conteúdo temporário foi removido.");
    } catch (cause) {
      showError(cause);
    } finally {
      setBusy(null);
    }
  }

  async function generate() {
    if (
      !interview ||
      !generationConsent ||
      interview.status !== "confirmada" ||
      !interview.curriculo_id
    )
      return;
    if (interview.geracao_id) {
      router.push("/otimizacoes/" + interview.geracao_id);
      return;
    }
    setBusy("generate");
    setError(null);
    const scope = "geracao-entrevista:" + userId + ":" + interviewId;
    try {
      const result = await browserRequest(
        "/v1/curriculos/" + interview.curriculo_id + "/otimizacoes",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": intentKey(scope),
          },
          body: JSON.stringify({
            consentimento_envio_openai: true,
            sessao_complementacao_id: interviewId,
          }),
        },
        attemptSchema.parse,
      );
      clearIntent(scope);
      router.push("/otimizacoes/" + result.data.id);
    } catch (cause) {
      if (cause instanceof HttpError && cause.code === "sessao_ja_utilizada") {
        const current = await refresh();
        const generationId = current.data?.geracao_id;
        if (generationId) router.push("/otimizacoes/" + generationId);
        else showError(cause);
      } else showError(cause);
    } finally {
      setBusy(null);
    }
  }

  function setAnswer(questionId: string, patch: Partial<AnswerDraft>) {
    setAnswers((current) => ({
      ...current,
      [questionId]: {
        ...(current[questionId] ?? {
          texto: "",
          pulada: false,
          negativa: false,
        }),
        ...patch,
      },
    }));
  }

  function resolveConflict(
    conflictId: string,
    action: "manter_original" | "usar_complemento",
    complementId?: string,
  ) {
    const conflict = interview?.conflitos.find(
      (item) => item.id === conflictId,
    );
    if (!conflict) return;
    if (action === "manter_original") {
      setComplements((items) =>
        items.filter(
          (item) => item.resposta_origem_id !== conflict.resposta_origem_id,
        ),
      );
      setResolutions((items) => ({
        ...items,
        [conflictId]: { conflito_id: conflictId, acao: action },
      }));
    } else if (complementId) {
      setComplements((items) =>
        items.map((item) =>
          item.id === complementId
            ? { ...item, substitui_trecho_original: conflict.trecho_original }
            : item,
        ),
      );
      setResolutions((items) => ({
        ...items,
        [conflictId]: {
          conflito_id: conflictId,
          acao: action,
          complemento_id: complementId,
        },
      }));
    }
  }

  function sourceLabel(origin: string | null | undefined) {
    if (!origin) return "Informação acrescentada por você";
    for (const round of interview?.rodadas ?? []) {
      if (round.complemento_livre_id === origin)
        return "Complemento livre da rodada " + round.numero;
      const answer = round.respostas.find((item) => item.id === origin);
      if (answer) {
        const question = round.perguntas.find(
          (item) => item.id === answer.pergunta_id,
        );
        return (
          "Resposta da rodada " +
          round.numero +
          (question ? " · " + question.pergunta : "")
        );
      }
    }
    return "Origem registrada pela entrevista";
  }

  const usage = useQuery({
    queryKey: [userId, "uso"],
    queryFn: () =>
      browserGet(
        "/api/backend/v1/uso",
        (value) => value as { restante: number; proximo_reinicio: string },
      ),
    enabled: interview?.status === "confirmada",
  });

  const cancelable = !["confirmada", "cancelada", "expirada"].includes(
    interview.status,
  );

  return (
    <div className="workflow-stack">
      <section className="panel interview-status-panel">
        <div>
          <span className="context-label">
            Sessão {interview.id.slice(0, 8)}
          </span>
          <h2>{stateNames[interview.status] ?? interview.status}</h2>
          <p className="section-intro">
            Rodada {interview.rodada_atual} de até {limits.maximumRounds}
            {interview.expires_at
              ? " · Expira em " +
                new Intl.DateTimeFormat("pt-BR", {
                  dateStyle: "medium",
                  timeStyle: "short",
                  timeZone: "America/Sao_Paulo",
                }).format(new Date(interview.expires_at))
              : ""}
          </p>
        </div>
        {interview.status === "analisando" && (
          <p role="status" className="status-message">
            A análise está em andamento. O estado é consultado automaticamente
            enquanto a sessão estiver ativa.
          </p>
        )}
        {interview.status === "falhou" && (
          <div className="notice warning-notice">
            <strong>{interview.codigo_erro ?? "A análise falhou"}</strong>
            <p>
              {interview.mensagem_erro ??
                "Você pode repetir a análise manualmente ou revisar as informações já salvas."}
            </p>
          </div>
        )}
        {interview.status === "expirada" && (
          <div className="notice">
            O prazo terminou e os dados temporários foram removidos. Inicie uma
            nova sessão para continuar.
          </div>
        )}
        {interview.status === "cancelada" && (
          <div className="notice">
            A entrevista foi encerrada e seu conteúdo temporário foi removido.
          </div>
        )}
      </section>

      {interview.status === "aguardando_respostas" && (
        <section
          className="panel form-stack"
          aria-labelledby="perguntas-titulo"
        >
          <div>
            <h2 id="perguntas-titulo">Rodada {interview.rodada_atual}</h2>
            <p className="section-intro">
              Responda o que for verdadeiro. Você pode pular uma pergunta sem
              resposta.
            </p>
          </div>
          {roundQuestions.length === 0 && (
            <p>
              Não há perguntas nesta rodada. Você pode revisar as informações
              disponíveis.
            </p>
          )}
          <div className="question-list">
            {roundQuestions.map((question, index) => {
              const draft = answers[question.id] ?? {
                texto: "",
                pulada: false,
                negativa: false,
              };
              return (
                <fieldset className="question-item" key={question.id}>
                  <legend>
                    <span className="question-number">{index + 1}</span>
                    {question.pergunta}
                  </legend>
                  <p>
                    {question.justificativa}
                    {question.termo_da_vaga
                      ? " · Relacionada a “" + question.termo_da_vaga + "”"
                      : ""}
                  </p>
                  <label htmlFor={"resposta-" + question.id}>
                    Sua resposta
                  </label>
                  <textarea
                    id={"resposta-" + question.id}
                    rows={4}
                    maxLength={limits.answerCharacters}
                    value={draft.texto}
                    disabled={draft.pulada}
                    onChange={(event) =>
                      setAnswer(question.id, {
                        texto: event.target.value,
                        negativa: false,
                      })
                    }
                  />
                  <div className="answer-options">
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={draft.pulada}
                        onChange={(event) =>
                          setAnswer(question.id, {
                            pulada: event.target.checked,
                            negativa: false,
                          })
                        }
                      />{" "}
                      Pular esta pergunta
                    </label>
                    <label className="check-row">
                      <input
                        type="checkbox"
                        checked={draft.negativa}
                        disabled={draft.pulada}
                        onChange={(event) =>
                          setAnswer(question.id, {
                            negativa: event.target.checked,
                            pulada: false,
                            texto:
                              event.target.checked && !draft.texto.trim()
                                ? "Não tenho essa experiência."
                                : draft.texto,
                          })
                        }
                      />{" "}
                      Não tenho essa experiência
                    </label>
                  </div>
                  <span className="character-count">
                    {draft.texto.length.toLocaleString("pt-BR")} /{" "}
                    {limits.answerCharacters.toLocaleString("pt-BR")}
                  </span>
                </fieldset>
              );
            })}
          </div>
          <div className="form-field">
            <label htmlFor="complemento-livre">
              Algo mais que deseja incluir?
            </label>
            <p className="field-hint">
              Opcional. Escreva apenas informações verdadeiras que queira
              acrescentar.
            </p>
            <textarea
              id="complemento-livre"
              rows={4}
              maxLength={limits.answerCharacters}
              value={freeText}
              onChange={(event) => setFreeText(event.target.value)}
            />
            <span className="character-count">
              {freeText.length.toLocaleString("pt-BR")} /{" "}
              {limits.answerCharacters.toLocaleString("pt-BR")}
            </span>
          </div>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions wrap-actions">
            {interview.rodada_atual < limits.maximumRounds && (
              <Button
                variant="outline"
                disabled={busy !== null || roundQuestions.length === 0}
                onClick={() => void sendRound("aprofundar")}
              >
                {busy === "aprofundar"
                  ? "Enviando respostas…"
                  : "Aprofundar respostas"}
              </Button>
            )}
            <Button
              disabled={busy !== null}
              onClick={() => void sendRound("encerrar")}
            >
              {busy === "encerrar"
                ? "Salvando respostas…"
                : missingQuestions > 0
                  ? "Pular sem resposta e revisar complementos"
                  : "Revisar complementos"}
            </Button>
          </div>
        </section>
      )}

      {interview.status === "aguardando_confirmacao" && (
        <section
          className="panel form-stack"
          aria-labelledby="complementos-titulo"
        >
          <div>
            <h2 id="complementos-titulo">
              Informações que podem entrar na proposta
            </h2>
            <p className="section-intro">
              Edite ou remova itens. A origem ajuda a conferir cada informação.
            </p>
          </div>
          {complements.map((item, index) => (
            <div className="complement-editor" key={item.id}>
              <div className="panel-heading">
                <span className="source-label">
                  {sourceLabel(item.resposta_origem_id)}
                </span>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() =>
                    setComplements((current) =>
                      current.filter((entry) => entry.id !== item.id),
                    )
                  }
                >
                  Remover informação
                </Button>
              </div>
              <label htmlFor={"complemento-" + item.id}>
                Complemento {index + 1}
              </label>
              <textarea
                id={"complemento-" + item.id}
                rows={3}
                maxLength={limits.complementCharacters}
                value={item.texto}
                onChange={(event) =>
                  setComplements((current) =>
                    current.map((entry) =>
                      entry.id === item.id
                        ? { ...entry, texto: event.target.value }
                        : entry,
                    ),
                  )
                }
              />
              <span className="character-count">
                {item.texto.length.toLocaleString("pt-BR")} /{" "}
                {limits.complementCharacters.toLocaleString("pt-BR")}
              </span>
            </div>
          ))}
          <div className="form-actions wrap-actions">
            <Button
              type="button"
              variant="outline"
              disabled={complements.length >= limits.complementItems}
              onClick={() =>
                setComplements((items) => [
                  ...items,
                  {
                    id: crypto.randomUUID(),
                    texto: "",
                    resposta_origem_id: null,
                    substitui_trecho_original: null,
                  },
                ])
              }
            >
              Adicionar informação
            </Button>
            <span className="character-count">
              {complements.length} / {limits.complementItems} itens ·{" "}
              {totalCharacters.toLocaleString("pt-BR")} /{" "}
              {limits.totalConfirmedCharacters.toLocaleString("pt-BR")}{" "}
              caracteres
            </span>
          </div>
          {interview.conflitos.length > 0 ? (
            <div className="conflict-list">
              <h3>Confira possíveis divergências com o original</h3>
              <p className="section-intro">
                Cada divergência precisa de uma escolha. Salve também os
                complementos compatíveis.
              </p>
              {interview.conflitos.map((conflict) => {
                const candidates = complements.filter(
                  (item) =>
                    item.resposta_origem_id === conflict.resposta_origem_id,
                );
                const resolution = resolutions[conflict.id];
                return (
                  <article className="conflict-item" key={conflict.id}>
                    <h4>{conflict.descricao}</h4>
                    <dl>
                      <div>
                        <dt>Currículo original</dt>
                        <dd>{conflict.trecho_original}</dd>
                      </div>
                      <div>
                        <dt>Resposta da entrevista</dt>
                        <dd>{conflict.trecho_resposta}</dd>
                      </div>
                    </dl>
                    <div className="resolution-options">
                      <label className="check-row">
                        <input
                          type="radio"
                          name={"resolucao-" + conflict.id}
                          checked={resolution?.acao === "manter_original"}
                          onChange={() =>
                            resolveConflict(conflict.id, "manter_original")
                          }
                        />{" "}
                        Manter o original e remover os complementos desta
                        resposta
                      </label>
                      <label className="check-row">
                        <input
                          type="radio"
                          name={"resolucao-" + conflict.id}
                          checked={resolution?.acao === "usar_complemento"}
                          disabled={candidates.length === 0}
                          onChange={() =>
                            candidates[0] &&
                            resolveConflict(
                              conflict.id,
                              "usar_complemento",
                              candidates[0].id,
                            )
                          }
                        />{" "}
                        Usar um complemento desta resposta
                      </label>
                      {resolution?.acao === "usar_complemento" &&
                        candidates.length > 0 && (
                          <div className="form-field">
                            <label htmlFor={"resolver-" + conflict.id}>
                              Complemento que substitui o trecho original
                            </label>
                            <select
                              id={"resolver-" + conflict.id}
                              value={resolution.complemento_id ?? ""}
                              onChange={(event) =>
                                resolveConflict(
                                  conflict.id,
                                  "usar_complemento",
                                  event.target.value,
                                )
                              }
                            >
                              {candidates.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.texto.slice(0, 100)}
                                  {item.texto.length > 100 ? "…" : ""}
                                </option>
                              ))}
                            </select>
                            <p className="field-hint">
                              O trecho substituído será salvo exatamente como
                              aparece no original.
                            </p>
                          </div>
                        )}
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className="notice">
              Nenhuma divergência foi indicada. Confira mesmo assim se as
              informações combinam com o original.
            </p>
          )}
          <Button
            type="button"
            variant="outline"
            disabled={
              busy !== null ||
              !dirtyComplements ||
              complements.some((item) => !item.texto.trim())
            }
            onClick={() => void saveComplements()}
          >
            {busy === "save-complements"
              ? "Salvando lista…"
              : "Salvar complementos"}
          </Button>
          {interview.conflitos.length === 0 || conflictsComplete ? (
            <div className="confirmation-checks">
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={savedConfirmations.information}
                  disabled={dirtyComplements}
                  onChange={(event) =>
                    setSavedConfirmations((current) => ({
                      ...current,
                      information: event.target.checked,
                    }))
                  }
                />{" "}
                Confirmo que revisei as informações e que são verdadeiras.
              </label>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={savedConfirmations.conflicts}
                  disabled={dirtyComplements}
                  onChange={(event) =>
                    setSavedConfirmations((current) => ({
                      ...current,
                      conflicts: event.target.checked,
                    }))
                  }
                />{" "}
                Confirmo que revisei possíveis contradições com o currículo
                original.
              </label>
            </div>
          ) : (
            <p className="field-hint">
              Resolva todas as divergências antes de confirmar.
            </p>
          )}
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          {notice && (
            <p className="status-message" role="status">
              {notice}
            </p>
          )}
          <Button
            disabled={
              busy !== null ||
              dirtyComplements ||
              !conflictsComplete ||
              !savedConfirmations.information ||
              !savedConfirmations.conflicts
            }
            onClick={() => void confirmComplements()}
          >
            {busy === "confirm"
              ? "Confirmando fontes…"
              : "Confirmar informações e fontes"}
          </Button>
          {dirtyComplements && (
            <p className="field-hint">
              Salve as alterações antes de confirmar. A lista completa,
              inclusive vazia, é enviada à API.
            </p>
          )}
        </section>
      )}

      {interview.status === "falhou" && (
        <section className="panel form-stack">
          <h2>O que fazer agora</h2>
          <p>
            A entrevista não desconta uma otimização. Você pode repetir
            manualmente a análise desta rodada ou encerrar e revisar as
            informações já salvas.
          </p>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <div className="form-actions wrap-actions">
            <Button
              variant="outline"
              disabled={busy !== null}
              onClick={() => void retryAnalysis()}
            >
              {busy === "retry"
                ? "Solicitando análise…"
                : "Tentar análise novamente"}
            </Button>
            <Button
              disabled={busy !== null}
              onClick={() => void sendRound("encerrar", true)}
            >
              {busy === "encerrar"
                ? "Encerrando…"
                : "Encerrar e revisar complementos"}
            </Button>
          </div>
        </section>
      )}

      {interview.status === "confirmada" && (
        <section className="panel form-stack">
          <div>
            <h2>Fontes confirmadas</h2>
            <p className="section-intro">
              A geração final usa o currículo original e apenas estas
              informações confirmadas.
            </p>
          </div>
          {interview.complementos.length ? (
            <ul className="confirmed-list">
              {interview.complementos.map((item) => (
                <li key={item.id}>
                  <p>{item.texto}</p>
                  <span>{sourceLabel(item.resposta_origem_id)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="notice">
              Nenhum complemento foi confirmado. A geração usará somente o
              original.
            </p>
          )}
          {interview.geracao_id ? (
            <Button asChild>
              <Link href={"/otimizacoes/" + interview.geracao_id}>
                Acompanhar geração vinculada
              </Link>
            </Button>
          ) : (
            <>
              <label className="check-row">
                <input
                  type="checkbox"
                  checked={generationConsent}
                  onChange={(event) =>
                    setGenerationConsent(event.target.checked)
                  }
                />{" "}
                Autorizo enviar o currículo original, a vaga e os complementos
                confirmados à OpenAI para gerar uma proposta.
              </label>
              {usage.data?.restante === 0 && (
                <p className="notice warning-notice">
                  A cota mensal está esgotada. Ela será renovada em{" "}
                  {new Intl.DateTimeFormat("pt-BR", {
                    dateStyle: "medium",
                    timeZone: "America/Sao_Paulo",
                  }).format(new Date(usage.data.proximo_reinicio))}
                  .
                </p>
              )}
              {usage.error && (
                <p className="field-hint" role="status">
                  Não foi possível consultar a cota agora. A API validará o
                  saldo ao gerar.
                </p>
              )}
              {error && (
                <p className="field-error" role="alert">
                  {error}
                </p>
              )}
              <Button
                disabled={
                  !generationConsent ||
                  busy !== null ||
                  usage.data?.restante === 0
                }
                onClick={() => void generate()}
              >
                {busy === "generate"
                  ? "Enviando para otimização…"
                  : "Gerar proposta com estas fontes"}
              </Button>
            </>
          )}
        </section>
      )}

      {cancelable && (
        <details className="panel cancel-interview">
          <summary>Cancelar esta entrevista</summary>
          <p>
            O cancelamento remove snapshots, perguntas, respostas, complementos
            e conflitos temporários. Uma chamada já enviada à IA pode terminar,
            mas seu resultado será descartado.
          </p>
          <Button
            type="button"
            variant="outline"
            disabled={busy !== null}
            onClick={() => void cancelInterview()}
          >
            {busy === "cancel"
              ? "Cancelando…"
              : "Confirmar cancelamento e apagar conteúdo temporário"}
          </Button>
        </details>
      )}
      {error &&
        ![
          "aguardando_respostas",
          "aguardando_confirmacao",
          "falhou",
          "confirmada",
        ].includes(interview.status) && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
      {notice &&
        !["aguardando_confirmacao", "confirmada"].includes(
          interview.status,
        ) && (
          <p className="status-message" role="status">
            {notice}
          </p>
        )}
      {interview.status !== "confirmada" && (
        <div className="panel round-history">
          <h2>Rodadas enviadas</h2>
          {interview.rodadas.length === 0 ? (
            <p>Nenhuma rodada foi registrada.</p>
          ) : (
            interview.rodadas.map((round) => (
              <details key={round.id}>
                <summary>
                  Rodada {round.numero}
                  {round.acao_apos_respostas
                    ? " · " +
                      (round.acao_apos_respostas === "encerrar"
                        ? "revisão"
                        : "aprofundamento")
                    : " · em análise"}
                </summary>
                <ul>
                  {round.perguntas.map((question) => {
                    const answer = round.respostas.find(
                      (item) => item.pergunta_id === question.id,
                    );
                    return (
                      <li key={question.id}>
                        <strong>{question.pergunta}</strong>
                        <p>
                          {answer?.pulada
                            ? "Pergunta pulada"
                            : answer?.negativa
                              ? "Resposta negativa: " + answer.texto
                              : (answer?.texto ?? "Sem resposta salva")}
                        </p>
                      </li>
                    );
                  })}
                  {round.complemento_livre && (
                    <li>
                      <strong>Complemento livre</strong>
                      <p>{round.complemento_livre}</p>
                    </li>
                  )}
                </ul>
              </details>
            ))
          )}
        </div>
      )}
      <p className="page-footnote">
        As respostas não são salvas a cada tecla. Rascunhos ficam nesta página
        até o envio e não sobrevivem garantidamente a uma atualização.
      </p>
    </div>
  );
}
