import { WorkflowProgress } from "@/components/layout/workflow-progress";
import { PageHeading } from "@/components/layout/page-heading";
import { ResumeEditor } from "@/features/editor/resume-editor";
import { requireSession } from "@/lib/server/session";

export const metadata = { title: "Editor do currículo" };
export default async function EditResume({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { user } = await requireSession("/curriculos/" + id + "/editor");
  return (
    <>
      <PageHeading
        title="Editor do currículo"
        description="Edite o LaTeX, confira uma prévia e exporte a revisão salva."
      />
      <WorkflowProgress current={3} />
      <ResumeEditor resumeId={id} userId={user.id} />
    </>
  );
}
