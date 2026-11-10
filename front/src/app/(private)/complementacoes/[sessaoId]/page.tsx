import { PageHeading } from "@/components/layout/page-heading";
import { InterviewPanel } from "@/features/complementacao/interview-panel";
import { requireSession } from "@/lib/server/session";

export const metadata = { title: "Entrevista" };
export default async function InterviewSession({
  params,
}: {
  params: Promise<{ sessaoId: string }>;
}) {
  const { sessaoId } = await params;
  const { user } = await requireSession("/complementacoes/" + sessaoId);
  return (
    <>
      <PageHeading
        title="Entrevista de complementação"
        description="Responda, revise cada fonte e confirme antes da geração."
      />
      <InterviewPanel interviewId={sessaoId} userId={user.id} />
    </>
  );
}
