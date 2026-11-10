"use client";

import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import { attemptSchema } from "@/lib/contracts";
import { HttpError, browserRequest } from "@/lib/http/errors";

function sourceName(source: string, records: { id: string }[]) {
  if (
    source.startsWith("complemento:") &&
    records.some((item) => item.id === source.slice("complemento:".length))
  ) {
    return "Informação confirmada na entrevista";
  }
  return "Currículo original";
}

export function ProposalReview({
  attemptId,
  userId,
}: {
  attemptId: string;
  userId: string;
}) {
  const router = useRouter();
  const client = useQueryClient();
  const queryKey = useMemo(
    () => [userId, "otimizacao", attemptId],
    [userId, attemptId],
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const query = useQuery({
    queryKey,
    queryFn: async () =>
      (
        await browserRequest(
          "/v1/otimizacoes/" + attemptId,
          { method: "GET" },
          attemptSchema.parse,
        )
      ).data,
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
  const attempt = query.data;

  async function confirmReview() {
    if (!attempt || attempt.status !== "aguardando_revisao") return;
    setBusy(true);
    setError(null);
    try {
      const result = await browserRequest(
        "/v1/otimizacoes/" + attemptId + "/confirmacao",
        { method: "POST" },
        attemptSchema.parse,
      );
      client.setQueryData(queryKey, result.data);
      if (result.data.curriculo_gerado_id)
        router.push(
          "/curriculos/" + result.data.curriculo_gerado_id + "/editor",
        );
      else await query.refetch();
    } catch (cause) {
      const current = await query.refetch();
      if (
        current.data?.status === "concluida" &&
        current.data.curriculo_gerado_id
      )
        router.push(
          "/curriculos/" + current.data.curriculo_gerado_id + "/editor",
        );
      else
        setError(
          cause instanceof HttpError
            ? cause.message
            : "Não foi possível confirmar a revisão.",
        );
    } finally {
      setBusy(false);
    }
  }

  if (query.error || (!attempt && !query.isPending))
    return (
      <DataError
        error={query.error}
        retry={() => void query.refetch()}
        busy={query.isFetching}
      />
    );
  if (!attempt)
    return (
      <div className="panel loading-block" role="status">
        Carregando proposta…
      </div>
    );
  const proposal = attempt.proposta;
  const confirmed = attempt.status === "concluida";

  return (
    <div className="workflow-stack">
      <section className="panel form-stack">
        <div>
          <span className="context-label">
            Tentativa {attempt.id.slice(0, 8)}
          </span>
          <h2>
            {attempt.status === "pendente" || attempt.status === "processando"
              ? "Preparando proposta"
              : attempt.status === "aguardando_revisao"
                ? "Revise a proposta"
                : confirmed
                  ? "Revisão confirmada"
                  : attempt.status === "falhou"
                    ? "Geração não concluída"
                    : "Estado da geração"}
          </h2>
          <p className="section-intro">
            Etapa: {attempt.etapa}. Criada em{" "}
            {new Intl.DateTimeFormat("pt-BR", {
              dateStyle: "medium",
              timeStyle: "short",
              timeZone: "America/Sao_Paulo",
            }).format(new Date(attempt.created_at))}
          </p>
        </div>
        {["pendente", "processando"].includes(attempt.status) && (
          <p role="status" className="status-message">
            A geração está em andamento. A tela acompanha a tentativa sem
            reiniciar a IA.
          </p>
        )}
        {attempt.status === "falhou" && (
          <div className="notice warning-notice">
            <strong>{attempt.codigo_erro ?? "A geração falhou"}</strong>
            <p>
              {attempt.mensagem_erro ?? "A API não concluiu esta tentativa."}
            </p>
          </div>
        )}
        {confirmed && attempt.curriculo_gerado_id && (
          <Button asChild>
            <Link
              href={"/curriculos/" + attempt.curriculo_gerado_id + "/editor"}
            >
              Abrir editor
            </Link>
          </Button>
        )}
        {attempt.status === "falhou" && attempt.curriculo_id && (
          <div className="form-actions wrap-actions">
            <Button asChild variant="outline">
              <Link href={"/curriculos/" + attempt.curriculo_id + "/revisao"}>
                Voltar ao currículo original
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link
                href={
                  "/curriculos/" + attempt.curriculo_id + "/complementacoes"
                }
              >
                Iniciar novo fluxo com entrevista
              </Link>
            </Button>
          </div>
        )}
      </section>

      {attempt.status === "aguardando_revisao" && proposal && (
        <>
          <section className="panel form-stack">
            <div>
              <h2>O que mudou</h2>
              <p className="section-intro">
                Confira o texto proposto e a evidência que sustenta cada
                alteração.
              </p>
            </div>
            {proposal.alteracoes.length === 0 ? (
              <p>
                Nenhuma alteração foi listada. Revise o conteúdo estruturado
                antes de confirmar.
              </p>
            ) : (
              <ol className="change-list">
                {proposal.alteracoes.map((change, index) => (
                  <li key={index}>
                    <div className="change-heading">
                      <strong>{change.secao}</strong>
                      <span className="status-label">
                        {change.tipo === "inclusao" ? "Inclusão" : "Reescrita"}
                      </span>
                    </div>
                    {change.tipo === "inclusao" ? (
                      <p className="change-before">
                        Informação adicionada após sua confirmação
                      </p>
                    ) : (
                      <div className="before-after">
                        <div>
                          <span>Antes</span>
                          <p>{change.antes}</p>
                        </div>
                        <div>
                          <span>Depois</span>
                          <p>{change.depois}</p>
                        </div>
                      </div>
                    )}
                    <p>{change.justificativa}</p>
                    <blockquote>{change.trecho_fonte}</blockquote>
                    <span className="source-label">
                      {sourceName(
                        change.fonte,
                        proposal.fontes_confirmadas ?? [],
                      )}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </section>

          <div className="dashboard-grid proposal-grid">
            <section className="panel form-stack">
              <div>
                <h2>Palavras da vaga consideradas</h2>
                <p className="section-intro">
                  Cada termo vem acompanhado de uma evidência literal.
                </p>
              </div>
              {proposal.palavras_chave_usadas.length === 0 ? (
                <p>Nenhuma palavra-chave foi indicada.</p>
              ) : (
                <ul className="evidence-list">
                  {proposal.palavras_chave_usadas.map((keyword, index) => (
                    <li key={index}>
                      <strong>{keyword.termo}</strong>
                      <blockquote>
                        {keyword.trecho_fonte ?? keyword.evidencia_no_original}
                      </blockquote>
                      <span className="source-label">
                        {sourceName(
                          keyword.fonte,
                          proposal.fontes_confirmadas ?? [],
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="panel form-stack">
              <div>
                <h2>Requisitos sem evidência</h2>
                <p className="section-intro">
                  A proposta não inventa experiências para cobrir lacunas.
                </p>
              </div>
              {proposal.lacunas.length === 0 ? (
                <p>Nenhuma lacuna foi indicada.</p>
              ) : (
                <ul className="evidence-list">
                  {proposal.lacunas.map((gap, index) => (
                    <li key={index}>
                      <strong>{gap.termo_da_vaga}</strong>
                      <p>{gap.motivo_para_nao_incluir}</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>

          <section className="panel form-stack">
            <h2>Currículo estruturado</h2>
            {proposal.curriculo.resumo && (
              <div>
                <h3>Resumo</h3>
                <p>{proposal.curriculo.resumo.texto}</p>
              </div>
            )}
            {proposal.curriculo.experiencias.length > 0 && (
              <div>
                <h3>Experiências</h3>
                {proposal.curriculo.experiencias.map((entry, index) => (
                  <article className="structured-entry" key={index}>
                    <strong>{entry.titulo.texto}</strong>
                    {entry.instituicao && (
                      <span>{entry.instituicao.texto}</span>
                    )}
                    {entry.periodo && <span>{entry.periodo.texto}</span>}
                    <ul>
                      {entry.itens.map((item, itemIndex) => (
                        <li key={itemIndex}>{item.texto}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            )}
            {proposal.curriculo.formacao.length > 0 && (
              <div>
                <h3>Formação</h3>
                {proposal.curriculo.formacao.map((entry, index) => (
                  <article className="structured-entry" key={index}>
                    <strong>{entry.titulo.texto}</strong>
                    {entry.instituicao && (
                      <span>{entry.instituicao.texto}</span>
                    )}
                    {entry.periodo && <span>{entry.periodo.texto}</span>}
                  </article>
                ))}
              </div>
            )}
            {proposal.curriculo.projetos.length > 0 && (
              <div>
                <h3>Projetos</h3>
                {proposal.curriculo.projetos.map((entry, index) => (
                  <article className="structured-entry" key={index}>
                    <strong>{entry.titulo.texto}</strong>
                    {entry.instituicao && (
                      <span>{entry.instituicao.texto}</span>
                    )}
                    <ul>
                      {entry.itens.map((item, itemIndex) => (
                        <li key={itemIndex}>{item.texto}</li>
                      ))}
                    </ul>
                  </article>
                ))}
              </div>
            )}
            {proposal.curriculo.competencias.length > 0 && (
              <div>
                <h3>Competências</h3>
                <ul className="inline-list">
                  {proposal.curriculo.competencias.map((item, index) => (
                    <li key={index}>{item.texto}</li>
                  ))}
                </ul>
              </div>
            )}
          </section>
          {error && (
            <p className="field-error" role="alert">
              {error}
            </p>
          )}
          <div className="notice">
            <p>
              A proposta ainda não foi revisada por você. Confira os fatos e as
              fontes; a geração não substitui sua confirmação.
            </p>
          </div>
          <Button
            disabled={busy || query.isFetching}
            onClick={() => void confirmReview()}
          >
            {busy ? "Confirmando revisão…" : "Confirmar revisão e abrir editor"}
          </Button>
        </>
      )}
      {attempt.status === "aguardando_revisao" && !proposal && (
        <div className="panel notice warning-notice">
          A tentativa não incluiu uma proposta válida. Atualize para consultar a
          resposta atual.
        </div>
      )}
      <p className="page-footnote">
        A proposta não garante aprovação em processos seletivos ou sistemas ATS.
        Confirme os fatos antes de editar ou exportar.
      </p>
    </div>
  );
}
