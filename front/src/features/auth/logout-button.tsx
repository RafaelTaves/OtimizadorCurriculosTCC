"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
export function LogoutButton() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(false);
  async function logout() {
    setBusy(true);
    setError(false);
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error();
      await queryClient.cancelQueries();
      queryClient.clear();
      // Full document navigation discards private React state and the router cache.
      window.location.replace("/login");
    } catch {
      setError(true);
      setBusy(false);
    }
  }
  return (
    <div>
      <Button variant="ghost" onClick={logout} disabled={busy}>
        <LogOut aria-hidden="true" />
        {busy ? "Saindo…" : "Sair da conta"}
      </Button>
      {error && (
        <p role="alert" className="text-sm">
          Não foi possível sair. Tente novamente.
        </p>
      )}
    </div>
  );
}
