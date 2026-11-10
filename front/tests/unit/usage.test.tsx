import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect } from "vitest";
import { UsagePanel } from "@/features/uso/usage-panel";
describe("cota retornada pela API", () => {
  it("mostra zero, a reserva e a renovação sem recalcular o saldo", () => {
    const client = new QueryClient({
      defaultOptions: { queries: { staleTime: Infinity, retry: false } },
    });
    render(
      <QueryClientProvider client={client}>
        <UsagePanel
          userId="fixture"
          initial={{
            data: {
              limite: 7,
              usado: 7,
              restante: 0,
              inicio_periodo: "2026-10-01T00:00:00Z",
              proximo_reinicio: "2026-11-01T00:00:00Z",
            },
          }}
        />
      </QueryClientProvider>,
    );
    expect(
      screen.getByText("Limite atingido neste período."),
    ).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("value", "7");
    expect(screen.getByText(/31 de out/)).toBeInTheDocument();
  });
});
