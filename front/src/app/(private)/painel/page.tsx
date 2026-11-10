import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeading } from "@/components/layout/page-heading";
import { Button } from "@/components/ui/button";
import { HistoryPanel } from "@/features/curriculos/history-panel";
import { Workflow } from "@/features/curriculos/workflow";
import { UsagePanel } from "@/features/uso/usage-panel";
import { requireSession } from "@/lib/server/session";
import { loadHistory, loadUsage } from "@/lib/server/data";
export const metadata = { title: "Painel" };
export default async function Dashboard() {
  const { user } = await requireSession("/painel");
  const [history, usage] = await Promise.all([loadHistory(), loadUsage()]);
  return (
    <>
      <PageHeading
        title="Painel"
        description="Seus currículos e o próximo passo para cada vaga."
        action={
          <Button asChild>
            <Link href="/curriculos/novo">
              <Plus aria-hidden="true" />
              Novo currículo
            </Link>
          </Button>
        }
      />
      <div className="dashboard-grid">
        <HistoryPanel initial={history} userId={user.id} />
        <UsagePanel initial={usage} userId={user.id} />
      </div>
      <Workflow />
      <p className="page-footnote">
        A otimização ajuda a apresentar sua experiência. Não garante aprovação
        em processos seletivos.
      </p>
    </>
  );
}
