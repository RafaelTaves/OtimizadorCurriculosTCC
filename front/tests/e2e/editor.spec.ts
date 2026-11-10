import { expect, test, type Page } from "@playwright/test";

// Synthetic resume and compilation responses; no real account or AI calls.
const resumeId = "00000000-0000-4000-8000-000000000098";
const attemptId = "00000000-0000-4000-8000-000000000077";
const path = `/v1/curriculos/${resumeId}`;
const draft =
  "\\documentclass{article}\n\\begin{document}\nCurrículo sintético revisado\n\\end{document}";

async function editor(
  page: Page,
  scenario?: "save" | "render" | "download" | "cached",
) {
  const calls: string[] = [];
  let savedCode = "Currículo sintético inicial";
  let revision = 1;
  let polls = 0;
  const resume = () => ({
    id: resumeId,
    tipo: "otimizado",
    curriculo_origem_id: null,
    nome_arquivo: "Currículo — demonstração sintética.tex",
    descricao_vaga: null,
    texto_extraido: null,
    texto_confirmado: true,
    latex_gerado: savedCode,
    latex_revisao: revision,
    pdf_revisao: null,
    template_versao: "synthetic-v1",
    conteudo_estruturado: null,
    created_at: "2026-11-10T12:00:00Z",
    updated_at: "2026-11-10T12:00:00Z",
    pdf_disponivel: false,
    revisao_humana_confirmada: true,
    avisos: [],
  });
  const attempt = (status: string) => ({
    id: attemptId,
    curriculo_id: resumeId,
    curriculo_gerado_id: null,
    tipo_operacao: "exportacao",
    status,
    etapa: "compilacao",
    codigo_erro: null,
    mensagem_erro:
      status === "falhou" ? "Falha sintética de compilação." : null,
    modelo: null,
    tokens_entrada: null,
    tokens_saida: null,
    created_at: "2026-11-10T12:00:00Z",
    completed_at: null,
    expires_at: null,
    acompanhamento: `/v1/renderizacoes/${attemptId}`,
    download_pdf: `${path}/download?formato=pdf`,
  });
  await page.context().addCookies([
    {
      name: "curriculo_session",
      value: "synthetic-browser-test-token",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.route("**/api/backend/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname.replace("/api/backend", "");
    if (endpoint === path && request.method() === "GET") {
      return route.fulfill({
        json: resume(),
        headers: { etag: `"${revision}"` },
      });
    }
    if (endpoint === `${path}/latex`) {
      calls.push("save");
      expect(request.headers()["if-match"]).toBe(`"${revision}"`);
      if (scenario === "save")
        return route.fulfill({
          status: 412,
          json: {
            detail: { codigo: "conflito", mensagem: "Conflito sintético." },
          },
        });
      savedCode = request.postDataJSON().latex;
      revision++;
      return route.fulfill({
        json: resume(),
        headers: { etag: `"${revision}"` },
      });
    }
    if (endpoint === `${path}/preview`) {
      calls.push("preview");
      expect(request.postDataJSON().latex).toBe(savedCode);
      return route.fulfill({ status: 202, json: attempt("pendente") });
    }
    if (endpoint === `/v1/previews/${attemptId}`)
      return route.fulfill({ json: attempt("pendente") });
    if (endpoint === `${path}/renderizacoes`) {
      calls.push("render");
      expect(savedCode).toBe(draft);
      return route.fulfill({
        status: 202,
        json: attempt(scenario === "cached" ? "concluida" : "pendente"),
      });
    }
    if (endpoint === `/v1/renderizacoes/${attemptId}`) {
      if (scenario === "cached") calls.push("poll");
      polls++;
      return route.fulfill({
        json: attempt(
          polls === 1
            ? "processando"
            : scenario === "render"
              ? "falhou"
              : "concluida",
        ),
      });
    }
    if (endpoint === `${path}/download`) {
      calls.push("download");
      expect(url.searchParams.get("formato")).toBe("pdf");
      if (scenario === "download")
        return route.fulfill({ status: 500, json: {} });
      return route.fulfill({
        contentType: "application/pdf",
        body: "%PDF-1.4\n% synthetic download fixture\n%%EOF",
      });
    }
    return route.fallback();
  });
  await page.goto(`/curriculos/${resumeId}/editor`);
  await expect(
    page.getByRole("button", { name: "Atualizar prévia" }),
  ).toBeEnabled();
  await page.getByText("Alternativa de edição em texto").click();
  await page.locator("#latex-fallback").fill(draft);
  return calls;
}

test("atualizar prévia salva primeiro e elimina ações redundantes", async ({
  page,
}) => {
  const calls = await editor(page);
  await expect(
    page.getByRole("button", { name: /^(Salvar|Baixar)/ }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Atualizar prévia" }).click();
  await expect(
    page.getByText("Alterações salvas. Prévia solicitada."),
  ).toBeVisible();
  expect(calls).toEqual(["save", "preview"]);
  await expect(page.getByText(/Rascunho não salvo/)).toHaveCount(0);
  await page.getByRole("button", { name: "Atualizar prévia" }).click();
  await expect.poll(() => calls.length).toBe(4);
  expect(calls).toEqual(["save", "preview", "save", "preview"]);
});

test("PDF final salva, aguarda compilação e baixa uma única vez", async ({
  page,
}) => {
  const calls = await editor(page);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Gerar PDF Final" }).click();
  await expect(
    page.getByRole("button", { name: "Gerando PDF…" }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Atualizar prévia" }),
  ).toBeDisabled();
  // Edits made while compiling remain a draft; the download uses the saved snapshot.
  await page.locator("#latex-fallback").fill(draft + "\n% nova edição");
  expect((await download).suggestedFilename()).toBe("curriculo.pdf");
  await expect(
    page.getByText("PDF final gerado. Download iniciado."),
  ).toBeVisible();
  expect(calls).toEqual(["save", "render", "download"]);
  await expect(page.getByText(/Rascunho não salvo/)).toBeVisible();
  await page.evaluate(() =>
    window.dispatchEvent(new Event("visibilitychange")),
  );
  await expect(
    page.getByRole("button", { name: "Gerar PDF Final" }),
  ).toBeEnabled();
  expect(calls.filter((call) => call === "download")).toHaveLength(1);
});

test("baixa um PDF já pronto sem consultar a fila em cada clique", async ({
  page,
}) => {
  const calls = await editor(page, "cached");
  for (let count = 0; count < 2; count++) {
    const download = page.waitForEvent("download");
    await page.getByRole("button", { name: "Gerar PDF Final" }).click();
    expect((await download).suggestedFilename()).toBe("curriculo.pdf");
    await expect(
      page.getByText("PDF final gerado. Download iniciado."),
    ).toBeVisible();
  }
  expect(calls).toEqual([
    "save",
    "render",
    "download",
    "save",
    "render",
    "download",
  ]);
});

for (const action of ["Atualizar prévia", "Gerar PDF Final"]) {
  test(`${action} preserva rascunho e interrompe fluxo em conflito`, async ({
    page,
  }) => {
    const calls = await editor(page, "save");
    await page.getByRole("button", { name: action }).click();
    await expect(
      page.getByRole("heading", { name: "O currículo mudou em outra revisão" }),
    ).toBeVisible();
    expect(calls).toEqual(["save"]);
    await expect(page.locator("#latex-fallback")).toHaveValue(draft);
    await expect(page.getByRole("button", { name: action })).toBeDisabled();
  });
}

test("falha de compilação não baixa arquivo e permite nova tentativa", async ({
  page,
}) => {
  const calls = await editor(page, "render");
  await page.getByRole("button", { name: "Gerar PDF Final" }).click();
  await expect(page.getByText("Falha sintética de compilação.")).toBeVisible();
  expect(calls).toEqual(["save", "render"]);
  await expect(
    page.getByRole("button", { name: "Gerar PDF Final" }),
  ).toBeEnabled();
});

test("falha de download é exibida e libera as ações", async ({ page }) => {
  const calls = await editor(page, "download");
  await page.getByRole("button", { name: "Gerar PDF Final" }).click();
  await expect(page.locator(".field-error[role=alert]")).toBeVisible();
  expect(calls).toEqual(["save", "render", "download"]);
  await expect(
    page.getByRole("button", { name: "Gerar PDF Final" }),
  ).toBeEnabled();
});

test("ações e editor cabem no desktop, tablet e celular", async ({ page }) => {
  await editor(page);
  await page.getByText("Alternativa de edição em texto").click();
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await expect(
      page.getByRole("button", { name: "Gerar PDF Final" }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: `../.taste-skill/editor-actions/editor-${width}.png`,
      fullPage: true,
    });
  }
});
