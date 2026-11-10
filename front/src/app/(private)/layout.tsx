import { AppShell } from "@/components/layout/app-shell";
import { QueryProvider } from "@/providers/query-provider";
import { requireSession } from "@/lib/server/session";
export default async function PrivateLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user } = await requireSession();
  return (
    <QueryProvider key={user.id}>
      <AppShell user={user}>{children}</AppShell>
    </QueryProvider>
  );
}
