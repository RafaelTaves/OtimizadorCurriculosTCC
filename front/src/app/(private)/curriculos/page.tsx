import Link from "next/link";
import { Plus } from "lucide-react";
import { PageHeading } from "@/components/layout/page-heading";
import { Button } from "@/components/ui/button";
import { HistoryPanel } from "@/features/curriculos/history-panel";
import { requireSession } from "@/lib/server/session";
import { loadHistory } from "@/lib/server/data";
export const metadata = { title: "Currículos" };
export default async function Resumes({
  searchParams,
}: {
  searchParams: Promise<{ pagina?: string }>;
}) {
  const { user } = await requireSession("/curriculos");
  const requested = Number((await searchParams).pagina ?? 1);
  const page = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  const initial = await loadHistory(20, page);
  return (
    <>
      <PageHeading
        title="Seus currículos"
        description="Continue de onde parou ou prepare uma nova versão."
        action={
          <Button asChild>
            <Link href="/curriculos/novo">
              <Plus aria-hidden="true" />
              Novo currículo
            </Link>
          </Button>
        }
      />
      <HistoryPanel
        key={page}
        initial={initial}
        userId={user.id}
        full
        page={page}
      />
    </>
  );
}
