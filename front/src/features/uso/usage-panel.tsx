"use client";
import { useQuery } from "@tanstack/react-query";
import { usageSchema, type Usage } from "@/lib/contracts";
import { browserGet, type LoadResult } from "@/lib/http/errors";
import { DataError } from "@/components/ui/data-error";
import Link from "next/link";

export function UsagePanel({
  initial,
  userId,
  detailsLink = true,
}: {
  initial: LoadResult<Usage>;
  userId: string;
  detailsLink?: boolean;
}) {
  const query = useQuery({
    queryKey: [userId, "uso"],
    queryFn: () => browserGet("/api/backend/v1/uso", usageSchema.parse),
    initialData: initial.data,
  });
  const data = query.data;
  return (
    <section className="panel usage-panel" aria-labelledby="uso-titulo">
      <h2 id="uso-titulo">Otimizações do período</h2>
      {query.error || (!data && initial.error) ? (
        <DataError
          error={query.error}
          retry={() => void query.refetch()}
          busy={query.isFetching}
        />
      ) : !data ? (
        <div role="status" className="loading-block">
          Consultando seu uso…
        </div>
      ) : (
        <>
          <p className="usage-number">
            <span>{data.restante}</span>{" "}
            {data.restante === 1 ? "disponível" : "disponíveis"}
          </p>
          <div className="usage-meter-label">
            <span>{data.usado} utilizadas ou reservadas</span>
            <span>Limite: {data.limite}</span>
          </div>
          <progress
            aria-label={`${data.usado} de ${data.limite} otimizações utilizadas ou reservadas`}
            value={data.usado}
            max={Math.max(data.limite, 1)}
          />
          {data.restante === 0 && (
            <p className="mt-3 font-medium">Limite atingido neste período.</p>
          )}
          <div className="renewal">
            <span>Próxima renovação</span>
            <time dateTime={data.proximo_reinicio}>
              {new Intl.DateTimeFormat("pt-BR", {
                day: "2-digit",
                month: "short",
                year: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                timeZone: "America/Sao_Paulo",
                timeZoneName: "short",
              }).format(new Date(data.proximo_reinicio))}
            </time>
            <small>Horário de Brasília. Contagem mensal em UTC.</small>
          </div>
          <p className="usage-note">
            Prévias e exportações não consomem otimizações.
          </p>
          {detailsLink && (
            <Link href="/conta" className="text-link usage-details">
              Consultar uso na conta
            </Link>
          )}
        </>
      )}
    </section>
  );
}
