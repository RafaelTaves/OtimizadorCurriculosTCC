"use client";
import Link from "next/link";
import { Button } from "@/components/ui/button";
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="error-page">
      <h1>Não foi possível abrir a página</h1>
      <p>
        O serviço está temporariamente indisponível. Seus documentos salvos
        permanecem na sua conta.
      </p>
      <div className="flex flex-wrap gap-3">
        <Button onClick={reset}>Tentar novamente</Button>
        <Button asChild variant="outline">
          <Link href="/login">Ir para o login</Link>
        </Button>
      </div>
    </div>
  );
}
