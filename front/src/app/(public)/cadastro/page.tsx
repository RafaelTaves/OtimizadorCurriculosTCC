import { redirect } from "next/navigation";
import { session } from "@/lib/server/session";
import { SignupForm } from "@/features/auth/auth-form";
export const metadata = { title: "Criar conta" };
export default async function Signup() {
  if (await session()) redirect("/painel");
  return (
    <>
      <h1>Criar sua conta</h1>
      <p className="auth-description">
        Um espaço para organizar e{" "}
        <span className="text-brand-blue-text">revisar seus currículos</span>.
      </p>
      <SignupForm />
    </>
  );
}
