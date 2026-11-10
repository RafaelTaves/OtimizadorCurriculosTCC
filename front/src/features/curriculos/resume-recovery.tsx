"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import {
  attemptPageSchema,
  interviewPageSchema,
  type ResumeSummary,
} from "@/lib/contracts";
import { browserRequest } from "@/lib/http/errors";

const interviewLabels: Record<string, string> = {
  analisando: "Análise em andamento",
  aguardando_respostas: "Responder entrevista",
  aguardando_confirmacao: "Revisar complementos",
  confirmada: "Fontes confirmadas",
  falhou: "Análise falhou",
  cancelada: "Entrevista cancelada",
  expirada: "Entrevista expirada",
};

export function ResumeRecovery({
  resume,
  userId,
}: {
  resume: ResumeSummary;
  userId: string;
}) {
  const [open, setOpen] = useState(false);
  const sessionQuery = useQuery({
    queryKey: [userId, "complementacoes", resume.id, 1, 20],
    queryFn: async () =>
      (
        await browserRequest(
          "/v1/curriculos/" +
            resume.id +
            "/complementacoes?pagina=1&tamanho=20",
          { method: "GET" },
          interviewPageSchema.parse,
        )
      ).data,
    enabled: open && resume.tipo === "original",
  });
  const attemptsQuery = useQuery({
    queryKey: [userId, "otimizacoes", resume.id, 1, 20],
    queryFn: async () =>
      (
        await browserRequest(
          "/v1/otimizacoes?curriculo_id=" + resume.id + "&pagina=1&tamanho=20",
          { method: "GET" },
          attemptPageSchema.parse,
        )
      ).data,
    enabled: open && resume.tipo === "original",
  });
  const sessions = sessionQuery.data?.itens ?? [];
  const attempts = attemptsQuery.data?.itens ?? [];

  return (
    <details
      className="resume-recovery"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Retomar trabalho e ver tentativas</summary>
      {resume.tipo === "otimizado" ? (
        <p className="recovery-action">
          {resume.revisao_humana_confirmada
            ? "Revisão humana confirmada"
            : "A revisão da proposta ainda está pendente"}
          {resume.tentativa_origem_id && (
            <>
              {" "}
              ·{" "}
              <Link href={"/otimizacoes/" + resume.tentativa_origem_id}>
                {resume.revisao_humana_confirmada
                  ? "Abrir tentativa"
                  : "Revisar proposta"}
              </Link>
            </>
          )}
          {resume.revisao_humana_confirmada && (
            <>
              {" "}
              ·{" "}
              <Link href={"/curriculos/" + resume.id + "/editor"}>
                Abrir editor
              </Link>
            </>
          )}
        </p>
      ) : (
        <>
          {(sessionQuery.error || attemptsQuery.error) && (
            <DataError
              error={sessionQuery.error ?? attemptsQuery.error}
              retry={() => {
                void sessionQuery.refetch();
                void attemptsQuery.refetch();
              }}
              busy={sessionQuery.isFetching || attemptsQuery.isFetching}
            />
          )}
          {sessionQuery.isPending || attemptsQuery.isPending ? (
            <p role="status" className="field-hint">
              Carregando estados persistidos…
            </p>
          ) : (
            <div className="recovery-results">
              <section>
                <h3>Entrevistas</h3>
                {sessions.length === 0 ? (
                  <p>Nenhuma entrevista registrada.</p>
                ) : (
                  <ul>
                    {sessions.map((item) => (
                      <li key={item.id}>
                        <span>
                          {interviewLabels[item.status] ?? item.status} · rodada{" "}
                          {item.rodada_atual}
                        </span>
                        <Link href={"/complementacoes/" + item.id}>
                          {["cancelada", "expirada"].includes(item.status)
                            ? "Ver estado"
                            : "Continuar"}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
                <Link href={"/curriculos/" + resume.id + "/complementacoes"}>
                  Abrir entrevistas
                </Link>
              </section>
              <section>
                <h3>Gerações diretas e vinculadas</h3>
                {attempts.length === 0 ? (
                  <p>Nenhuma tentativa de otimização registrada.</p>
                ) : (
                  <ul>
                    {attempts.map((item) => (
                      <li key={item.id}>
                        <span>
                          {item.status} ·{" "}
                          {new Intl.DateTimeFormat("pt-BR", {
                            dateStyle: "medium",
                            timeZone: "America/Sao_Paulo",
                          }).format(new Date(item.created_at))}
                        </span>
                        <Link href={"/otimizacoes/" + item.id}>
                          {item.status === "aguardando_revisao"
                            ? "Revisar proposta"
                            : ["pendente", "processando"].includes(item.status)
                              ? "Acompanhar geração"
                              : item.curriculo_gerado_id
                                ? "Abrir tentativa"
                                : "Ver tentativa"}
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          )}
        </>
      )}
    </details>
  );
}

export function DeleteResumeButton({
  resume,
  userId,
}: {
  resume: ResumeSummary;
  userId: string;
}) {
  const client = useQueryClient();
  const mutation = useMutation({
    mutationFn: async () =>
      (
        await browserRequest(
          "/v1/curriculos/" + resume.id,
          { method: "DELETE" },
          (value) => value,
        )
      ).status,
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: [userId, "curriculos"] });
      client.removeQueries({ queryKey: [userId, "curriculo", resume.id] });
      client.removeQueries({ queryKey: [userId, "complementacoes"] });
      client.removeQueries({ queryKey: [userId, "otimizacoes"] });
    },
  });
  function remove() {
    const consequence =
      resume.tipo === "original"
        ? "Excluir o original também remove suas versões, entrevistas, respostas e fontes associadas."
        : "Excluir remove esta versão otimizada.";
    if (
      window.confirm(
        "Excluir “" +
          resume.nome_arquivo +
          "”? " +
          consequence +
          " A exclusão não pode ser desfeita.",
      )
    )
      mutation.mutate();
  }
  return (
    <div className="delete-control">
      <Button
        type="button"
        variant="ghost"
        disabled={mutation.isPending}
        onClick={remove}
      >
        {mutation.isPending ? "Excluindo…" : "Excluir"}
      </Button>
      {mutation.error && (
        <p className="field-error" role="alert">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Não foi possível excluir."}
        </p>
      )}
    </div>
  );
}
