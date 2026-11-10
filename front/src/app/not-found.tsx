import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  return (
    <div className="error-page">
      <h1>Página não encontrada</h1>
      <p>Este endereço não existe ou não está disponível para sua conta.</p>
      <Button asChild>
        <Link href="/painel">Voltar ao painel</Link>
      </Button>
    </div>
  );
}
