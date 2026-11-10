"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import { interviewPageSchema, usageSchema } from "@/lib/contracts";
import { HttpError, browserRequest, browserGet } from "@/lib/http/errors";
import { intentKey, clearIntent } from "@/lib/http/intents";

const statusLabels: Record<string, string> = {
  analisando: "Analisando contexto",
  aguardando_respostas: "Aguardando respostas",
  aguardando_confirmacao: "Revisar complementos",
  confirmada: "Fontes confirmadas",
  falhou: "Análise falhou",
  cancelada: "Cancelada",
  expirada: "Expirada",
};

export function InterviewHub({
  resumeId,
  userId,
}: {
  resumeId: string;
  userId: string;
}) {
  const router = useRouter();
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const page = useQuery({
    queryKey: [userId, "complementacoes", resumeId, 1, 20],
    queryFn: async () =>
      (
        await browserRequest(
          `/v1/curriculos/${resumeId}/complementacoes?pagina=1&tamanho=20`,
          { method: "GET" },
          interviewPageSchema.parse,
        )
      ).data,
  });
  const usage = useQuery({
    queryKey: [userId, "uso"],
    queryFn: () => browserGet("/api/backend/v1/uso", usageSchema.parse),
  });
  const active =
    page.data?.itens.filter(
      (item) => !["cancelada", "expirada"].includes(item.status),
    ) ?? [];

  async function start() {
    setBusy(true);
    setError(null);
    const scope = `entrevista:${userId}:${resumeId}`;
    try {
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
        (value) => value as { id: string },
      );
      clearIntent(scope);
      router.push(`/complementacoes/${result.data.id}`);
    } catch (cause) {
      if (cause instanceof HttpError && cause.code === "sessao_ativa") {
        await page.refetch();
        const nowActive = page.data?.itens.find(
          (item) => !["cancelada", "expirada"].includes(item.status),
        );
        if (nowActive) router.push(`/complementacoes/${nowActive.id}`);
        else
          setError(
            "Já existe uma sessão ativa. Atualize a lista para retomá-la.",
          );
      } else
        setError(
          cause instanceof HttpError
            ? cause.message
            : "Não foi possível iniciar a entrevista.",
        );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="workflow-stack">
      <section className="panel form-stack">
        <div>
          <h2>Entrevistas deste currículo</h2>
          <p className="section-intro">
            Cada sessão é limitada, fica vinculada ao texto e à vaga atuais e
            expira no prazo informado pela API.
          </p>
        </div>
        {page.error ? (
          <DataError
            error={page.error}
            retry={() => void page.refetch()}
            busy={page.isFetching}
          />
        ) : !page.data ? (
          <div className="loading-block" role="status">
            Carregando sessões…
          </div>
        ) : page.data.itens.length === 0 ? (
          <p>Nenhuma entrevista foi iniciada para este currículo.</p>
        ) : (
          <ul className="recovery-list">
            {page.data.itens.map((item) => (
              <li key={item.id}>
                <div>
                  <strong>{statusLabels[item.status] ?? item.status}</strong>
                  <span>
                    Rodada {item.rodada_atual} · criada em{" "}
                    {new Intl.DateTimeFormat("pt-BR", {
                      dateStyle: "medium",
                      timeZone: "America/Sao_Paulo",
                    }).format(new Date(item.created_at))}
                  </span>
                  {item.expires_at && (
                    <span>
                      Expira em{" "}
                      {new Intl.DateTimeFormat("pt-BR", {
                        dateStyle: "short",
                        timeStyle: "short",
                        timeZone: "America/Sao_Paulo",
                      }).format(new Date(item.expires_at))}
                    </span>
                  )}
                </div>
                <Button asChild variant="outline">
                  <Link href={`/complementacoes/${item.id}`}>
                    {["cancelada", "expirada"].includes(item.status)
                      ? "Ver estado"
                      : "Continuar entrevista"}
                  </Link>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel form-stack">
        <div>
          <h2>Iniciar uma nova entrevista</h2>
          <p className="section-intro">
            A IA pode fazer até duas rodadas de perguntas para buscar detalhes
            que ajudem na proposta.
          </p>
        </div>
        {usage.data && (
          <p className="usage-inline">
            Otimizações neste período:{" "}
            <strong>
              {usage.data.usado} de {usage.data.limite}
            </strong>
            . A entrevista não reserva cota; a geração verificará o saldo
            novamente.
          </p>
        )}
        {usage.error && (
          <p className="field-hint" role="status">
            Não foi possível consultar o uso agora. A API validará a
            disponibilidade ao iniciar.
          </p>
        )}
        {active.length > 0 && (
          <p className="notice">
            Há uma sessão que pode ser retomada. Abra-a antes de iniciar outra.
          </p>
        )}
        <label className="check-row">
          <input
            type="checkbox"
            checked={consent}
            onChange={(event) => setConsent(event.target.checked)}
          />{" "}
          Autorizo enviar o texto confirmado, a vaga e minhas respostas à OpenAI
          para gerar perguntas de complementação.
        </label>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <Button
          disabled={
            !consent || busy || active.length > 0 || usage.data?.restante === 0
          }
          onClick={() => void start()}
        >
          {busy ? "Iniciando entrevista…" : "Consentir e iniciar entrevista"}
        </Button>
        {usage.data?.restante === 0 && (
          <p className="field-hint">
            A cota mensal está esgotada. Você pode revisar sessões existentes; o
            saldo será renovado em{" "}
            {new Intl.DateTimeFormat("pt-BR", {
              dateStyle: "medium",
              timeZone: "America/Sao_Paulo",
            }).format(new Date(usage.data.proximo_reinicio))}
            .
          </p>
        )}
      </section>
    </div>
  );
}
