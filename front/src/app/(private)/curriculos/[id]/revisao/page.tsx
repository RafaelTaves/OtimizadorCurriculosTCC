import { WorkflowProgress } from "@/components/layout/workflow-progress";
import { PageHeading } from "@/components/layout/page-heading";
import { ExtractedTextReview } from "@/features/curriculos/extracted-text-review";
import { requireSession } from "@/lib/server/session";

export const metadata = { title: "Revisar texto" };
export default async function ReviewResume({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { user } = await requireSession(`/curriculos/${id}/revisao`);
  return (
    <>
      <PageHeading
        title="Revisar texto"
        description="Confira o conteúdo extraído antes de escolher o próximo passo."
      />
      <WorkflowProgress current={1} />
      <ExtractedTextReview resumeId={id} userId={user.id} />
    </>
  );
}
