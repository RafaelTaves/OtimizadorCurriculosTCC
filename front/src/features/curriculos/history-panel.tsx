"use client";
import Link from "next/link";
import Image from "next/image";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  FileText,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { resumePageSchema, type History } from "@/lib/contracts";
import { browserGet, type LoadResult } from "@/lib/http/errors";
import { resumeDestination } from "@/lib/navigation";
import { Button } from "@/components/ui/button";
import { DataError } from "@/components/ui/data-error";
import {
  DeleteResumeButton,
  ResumeRecovery,
} from "@/features/curriculos/resume-recovery";

export function HistoryPanel({
  initial,
  userId,
  full = false,
  page = 1,
}: {
  initial: LoadResult<History>;
  userId: string;
  full?: boolean;
  page?: number;
}) {
  const size = full ? 20 : 4;
  const query = useQuery({
    queryKey: [userId, "curriculos", page, size],
    queryFn: () =>
      browserGet(
        `/api/backend/v1/curriculos?pagina=${page}&tamanho=${size}`,
        resumePageSchema.parse,
      ),
    initialData: initial.data,
  });
  const history = query.data;
  const firstCurriculum = history?.total === 0 && page === 1;
  return (
    <section
      className="panel history-panel"
      aria-labelledby="curriculos-titulo"
    >
      <div className="panel-heading">
        <h2 id="curriculos-titulo">
          {full ? "Documentos salvos" : "Currículos recentes"}
        </h2>
        {!full && (
          <Link href="/curriculos" className="text-link brand-action">
            Ver todos <ArrowUpRight size={15} aria-hidden="true" />
          </Link>
        )}
      </div>
      {query.error || (!history && initial.error) ? (
        <DataError
          error={query.error}
          retry={() => void query.refetch()}
          busy={query.isFetching}
        />
      ) : !history ? (
        <div role="status" className="loading-block">
          Carregando seus currículos…
        </div>
      ) : history.itens.length === 0 ? (
        <div
          className={
            firstCurriculum ? "empty-state empty-onboarding" : "empty-state"
          }
        >
          {firstCurriculum && (
            <Image
              src="/brand/mascote-cv.png"
              width={1254}
              height={1254}
              sizes="(min-width: 1024px) 144px, 112px"
              className="empty-mascot"
              alt=""
            />
          )}
          <div className="empty-copy">
            <h3>
              {firstCurriculum ? (
                <>
                  Seu{" "}
                  <span className="text-brand-blue-text">
                    primeiro currículo
                  </span>{" "}
                  começa aqui
                </>
              ) : (
                "Nenhum currículo nesta página"
              )}
            </h3>
            <p>
              {firstCurriculum
                ? "Prepare um PDF ou DOCX e a descrição da vaga para começar."
                : "Seus documentos não aparecem nesta página. Volte para consultar seus currículos."}
            </p>
            <Link
              className="text-link brand-action"
              href={
                firstCurriculum
                  ? "/curriculos/novo"
                  : page > 1
                    ? `/curriculos?pagina=${page - 1}`
                    : "/curriculos"
              }
            >
              {firstCurriculum
                ? "Preparar novo currículo"
                : page > 1
                  ? "Voltar uma página"
                  : "Voltar aos currículos"}
              <ArrowUpRight size={16} aria-hidden="true" />
            </Link>
          </div>
        </div>
      ) : (
        <>
          <p className="list-summary">
            {history.total}{" "}
            {history.total === 1 ? "documento salvo" : "documentos salvos"}
            {!full && history.total > size ? ` · ${size} mais recentes` : ""}
          </p>
          <ul className="resume-list">
            {history.itens.map((resume) => (
              <li key={resume.id}>
                <div className="resume-identity">
                  <FileText size={18} strokeWidth={1.5} aria-hidden="true" />
                  <div>
                    <Link
                      className="resume-name"
                      href={resumeDestination(resume)}
                    >
                      {resume.nome_arquivo}
                    </Link>
                    <div className="resume-meta">
                      <span className="status-label">
                        {resume.tipo === "original"
                          ? "Original"
                          : "Versão otimizada"}
                      </span>
                      {resume.tipo === "original" && (
                        <span>
                          {resume.texto_confirmado
                            ? "Texto confirmado"
                            : "Texto a revisar"}
                        </span>
                      )}
                      {resume.tipo === "otimizado" && (
                        <span>
                          {resume.revisao_humana_confirmada
                            ? "Revisão confirmada"
                            : "Revisão pendente"}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="resume-trailing">
                  <time dateTime={resume.created_at}>
                    {new Intl.DateTimeFormat("pt-BR", {
                      day: "2-digit",
                      month: "short",
                      timeZone: "America/Sao_Paulo",
                    }).format(new Date(resume.created_at))}
                  </time>
                  <Link
                    className="row-action"
                    href={resumeDestination(resume)}
                    aria-label={`Abrir ${resume.nome_arquivo}`}
                  >
                    <ArrowUpRight size={18} aria-hidden="true" />
                  </Link>
                </div>
                <div className="resume-secondary-actions">
                  <ResumeRecovery resume={resume} userId={userId} />
                  <DeleteResumeButton resume={resume} userId={userId} />
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      {full && history && history.total > size && (
        <nav aria-label="Paginação dos currículos" className="pagination">
          <span>
            Página {page} de {Math.ceil(history.total / size)}
          </span>
          <div>
            {page > 1 && (
              <Button asChild variant="outline">
                <Link href={`/curriculos?pagina=${page - 1}`}>
                  <ChevronLeft aria-hidden="true" />
                  Anterior
                </Link>
              </Button>
            )}
            {page * size < history.total && (
              <Button asChild variant="outline">
                <Link href={`/curriculos?pagina=${page + 1}`}>
                  Próxima
                  <ChevronRight aria-hidden="true" />
                </Link>
              </Button>
            )}
          </div>
        </nav>
      )}
    </section>
  );
}
