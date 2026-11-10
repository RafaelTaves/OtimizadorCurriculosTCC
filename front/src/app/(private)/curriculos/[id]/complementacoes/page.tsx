import { PageHeading } from "@/components/layout/page-heading";
import { InterviewHub } from "@/features/complementacao/interview-hub";
import { requireSession } from "@/lib/server/session";

export const metadata = { title: "Entrevistas" };
export default async function ResumeInterviews({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { user } = await requireSession(`/curriculos/${id}/complementacoes`);
  return (
    <>
      <PageHeading
        title="Complementar currículo"
        description="Retome uma entrevista ou inicie uma nova sessão para este original."
      />
      <InterviewHub resumeId={id} userId={user.id} />
    </>
  );
}
