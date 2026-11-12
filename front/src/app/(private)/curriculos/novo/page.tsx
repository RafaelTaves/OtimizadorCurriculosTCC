import { WorkflowProgress } from "@/components/layout/workflow-progress";
import { PageHeading } from "@/components/layout/page-heading";
import { Workflow } from "@/features/curriculos/workflow";
import { UploadForm } from "@/features/curriculos/upload-form";
import { requireSession } from "@/lib/server/session";
export const metadata = { title: "Novo currículo" };
export default async function NewResume() {
  await requireSession("/curriculos/novo");
  return (
    <>
      <PageHeading
        title="Novo currículo"
        description="Prepare seu currículo e a descrição da vaga."
      />
      <WorkflowProgress current={0} />
      <UploadForm />
      <Workflow />
    </>
  );
}
