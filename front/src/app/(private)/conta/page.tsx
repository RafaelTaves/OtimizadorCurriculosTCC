import { PageHeading } from "@/components/layout/page-heading";
import { UsagePanel } from "@/features/uso/usage-panel";
import { LogoutButton } from "@/features/auth/logout-button";
import { requireSession } from "@/lib/server/session";
import { loadUsage } from "@/lib/server/data";
export const metadata = { title: "Conta" };
export default async function Account() {
  const { user } = await requireSession("/conta");
  const usage = await loadUsage();
  return (
    <>
      <PageHeading
        title="Conta"
        description="Sua identificação e o uso do serviço."
      />
      <div className="settings-row">
        <div>
          <h2>Dados da conta</h2>
          <p>Informações usadas para acessar seus currículos.</p>
        </div>
        <section className="panel">
          <dl className="account-fields">
            <div>
              <dt>Nome de usuário</dt>
              <dd>{user.username}</dd>
            </div>
            <div>
              <dt>E-mail</dt>
              <dd>{user.email}</dd>
            </div>
          </dl>
          <p className="text-sm text-muted-foreground mt-5">
            Os dados da conta estão disponíveis apenas para consulta.
          </p>
        </section>
      </div>
      <div className="settings-row">
        <div>
          <h2>Uso mensal</h2>
          <p>O limite inclui otimizações utilizadas e reservadas.</p>
        </div>
        <UsagePanel initial={usage} userId={user.id} detailsLink={false} />
      </div>
      <div className="settings-row">
        <div>
          <h2>Sessão</h2>
          <p>Encerre o acesso neste navegador.</p>
        </div>
        <div>
          <LogoutButton />
        </div>
      </div>
    </>
  );
}
