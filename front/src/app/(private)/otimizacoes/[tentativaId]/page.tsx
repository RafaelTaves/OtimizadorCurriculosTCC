import { PageHeading } from "@/components/layout/page-heading";
import { ProposalReview } from "@/features/otimizacao/proposal-review";
import { requireSession } from "@/lib/server/session";

export const metadata = { title: "Revisar proposta" };
export default async function OptimizationAttempt({
  params,
}: {
  params: Promise<{ tentativaId: string }>;
}) {
  const { tentativaId } = await params;
  const { user } = await requireSession("/otimizacoes/" + tentativaId);
  return (
    <>
      <PageHeading
        title="Proposta de currículo"
        description="Acompanhe a geração e revise o conteúdo com as evidências disponíveis."
      />
      <ProposalReview attemptId={tentativaId} userId={user.id} />
    </>
  );
}
