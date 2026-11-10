import { redirect } from "next/navigation";
import { session } from "@/lib/server/session";
import { safeReturnPath } from "@/lib/navigation";
import { LoginForm } from "@/features/auth/auth-form";
export const metadata = { title: "Entrar" };
export default async function Login({
  searchParams,
}: {
  searchParams: Promise<{ retorno?: string; cadastro?: string }>;
}) {
  const params = await searchParams;
  if (await session()) redirect(safeReturnPath(params.retorno));
  return (
    <>
      <h1>Entrar na sua conta</h1>
      <p className="auth-description">
        Acesse <span className="text-brand-blue-text">seus currículos</span> e
        continue de onde parou.
      </p>
      <LoginForm
        returnTo={safeReturnPath(params.retorno)}
        registered={params.cadastro === "concluido"}
      />
    </>
  );
}
