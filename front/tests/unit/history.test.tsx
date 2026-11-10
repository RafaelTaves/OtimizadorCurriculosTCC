import React from "react";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect } from "vitest";
import { HistoryPanel } from "@/features/curriculos/history-panel";
import type { History } from "@/lib/contracts";
import type { LoadResult } from "@/lib/http/errors";

function history(total: number, page = 1): LoadResult<History> {
  return { data: { itens: [], total, pagina: page, tamanho: 20 } };
}
function renderHistory(initial: LoadResult<History>, page = 1) {
  const client = new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <HistoryPanel
        initial={initial}
        userId="synthetic-history-test"
        page={page}
        full
      />
    </QueryClientProvider>,
  );
}
describe("orientação para o primeiro currículo", () => {
  it("mostra mascote e ação somente quando o total é zero na primeira página", () => {
    const { container } = renderHistory(history(0));
    expect(container.querySelector(".empty-mascot")).toHaveAttribute("alt", "");
    expect(
      screen.getByRole("heading", {
        name: "Seu primeiro currículo começa aqui",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Preparar novo currículo/ }),
    ).toHaveAttribute("href", "/curriculos/novo");
  });
  it.each([
    [3, 1],
    [3, 2],
    [0, 2],
  ])(
    "não confunde total %s e página %s sem itens com conta nova",
    (total, page) => {
      const { container } = renderHistory(history(total, page), page);
      expect(container.querySelector(".empty-mascot")).toBeNull();
      expect(screen.queryByText(/primeiro currículo/)).not.toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Nenhum currículo nesta página" }),
      ).toBeInTheDocument();
    },
  );
  it("não mostra recepção no erro", () => {
    const { container } = renderHistory({ error: "Falha sintética" });
    expect(container.querySelector(".empty-mascot")).toBeNull();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
});
