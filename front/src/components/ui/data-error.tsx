"use client";
import Link from "next/link";
import { AlertCircle, RotateCw } from "lucide-react";
import { HttpError } from "@/lib/http/errors";
import { Button } from "./button";
export function DataError({
  error,
  retry,
  busy = false,
}: {
  error: unknown;
  retry: () => void;
  busy?: boolean;
}) {
  const expired = error instanceof HttpError && error.status === 401;
  return (
    <div className="data-error" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <div>
        <p>
          {expired
            ? "Sua sessão expirou. Entre novamente para continuar."
            : "Não foi possível atualizar estes dados. Tente novamente."}
        </p>
        {expired ? (
          <Button asChild variant="outline">
            <Link href="/login">Entrar novamente</Link>
          </Button>
        ) : (
          <Button variant="ghost" onClick={retry} disabled={busy}>
            <RotateCw aria-hidden="true" />
            {busy ? "Atualizando…" : "Tentar novamente"}
          </Button>
        )}
      </div>
    </div>
  );
}
