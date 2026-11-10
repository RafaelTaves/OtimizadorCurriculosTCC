import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const originalName = "Currículo — dados sintéticos.pdf";
const originalId = "00000000-0000-4000-8000-000000000010";
const interviewId = "00000000-0000-4000-8000-000000000066";

test.beforeEach(async ({ context }) => {
  await context.addCookies([
    {
      name: "curriculo_session",
      value: "synthetic-browser-test-token",
      domain: "localhost",
      path: "/",
    },
  ]);
});

test("lista compacta mantém ações e revela a retomada sob demanda", async ({
  page,
}) => {
  let interviewRequests = 0;
  await page.route(
    `**/api/backend/v1/curriculos/${originalId}/complementacoes?*`,
    (route) => {
      interviewRequests++;
      return route.fulfill({
        json: {
          itens: [
            {
              id: interviewId,
              curriculo_id: originalId,
              status: "aguardando_respostas",
              revisao: 1,
              rodada_atual: 1,
              created_at: "2026-10-23T12:00:00Z",
              expires_at: null,
            },
          ],
          total: 1,
          pagina: 1,
          tamanho: 20,
        },
      });
    },
  );
  await page.goto("/curriculos");
  const panel = page.getByRole("region", { name: "Documentos salvos" });
  await expect(panel.locator(".history-count")).toHaveText(
    "Total de documentos salvos: 3",
  );
  const details = panel.getByRole("button", {
    name: `Detalhes de ${originalName}`,
  });
  await expect(details).toHaveAttribute("aria-expanded", "false");
  expect(interviewRequests).toBe(0);
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(panel.getByText("Texto a revisar")).toBeVisible();
    await expect(panel.getByText("Revisão pendente")).toBeVisible();
    if (width < 640) {
      expect((await details.boundingBox())?.height).toBeGreaterThanOrEqual(44);
    }
  }
  await page.setViewportSize({ width: 390, height: 844 });
  await details.focus();
  await page.keyboard.press("Enter");
  await expect(details).toHaveAttribute("aria-expanded", "true");
  await expect(panel.getByRole("link", { name: "Continuar" })).toHaveAttribute(
    "href",
    `/complementacoes/${interviewId}`,
  );
  await expect(
    panel.getByRole("link", { name: "Revisar proposta" }),
  ).toBeVisible();
  expect(interviewRequests).toBe(1);
  expect(
    (
      await new AxeBuilder({ page })
        .include(".history-panel")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await details.press("Space");
  await expect(details).toHaveAttribute("aria-expanded", "false");
  await expect(
    panel.getByRole("heading", { name: "Entrevistas" }),
  ).toBeHidden();
});

test("lixeira tem tooltip e exige confirmação antes de atualizar a lista", async ({
  page,
}) => {
  let deleteRequests = 0;
  await page.route(`**/api/backend/v1/curriculos/${originalId}`, (route) => {
    expect(route.request().method()).toBe("DELETE");
    deleteRequests++;
    return route.fulfill({ status: 204 });
  });
  await page.route("**/api/backend/v1/curriculos?*", async (route) => {
    const response = await route.fetch();
    const json = await response.json();
    if (deleteRequests) {
      json.itens = json.itens.filter(
        ({ id }: { id: string }) => id !== originalId,
      );
      json.total--;
    }
    await route.fulfill({ response, json });
  });
  await page.goto("/curriculos");
  const remove = page.getByRole("button", { name: `Excluir ${originalName}` });
  const tooltip = remove.locator("+ .delete-tooltip");
  await remove.hover();
  await expect(tooltip).toBeVisible();
  await expect(remove).toHaveCSS("color", "rgb(172, 32, 38)");
  await page.keyboard.press("Escape");
  await expect(tooltip).toBeHidden();
  await page.mouse.move(0, 0);
  await page
    .getByRole("button", { name: `Detalhes de ${originalName}` })
    .focus();
  await page.keyboard.press("Tab");
  await expect(remove).toBeFocused();
  await expect(tooltip).toBeVisible();
  await expect(remove).toHaveCSS("color", "rgb(172, 32, 38)");
  await page.keyboard.press("Escape");
  await expect(tooltip).toBeHidden();

  const confirmations: string[] = [];
  page.on("dialog", (dialog) => {
    confirmations.push(dialog.message());
    return confirmations.length === 1 ? dialog.dismiss() : dialog.accept();
  });
  await remove.press("Enter");
  expect(confirmations[0]).toContain(originalName);
  expect(confirmations[0]).toContain("também remove suas versões, entrevistas");
  expect(confirmations[0]).toContain("A exclusão não pode ser desfeita.");
  expect(deleteRequests).toBe(0);
  await remove.press("Enter");
  await expect(remove).toHaveCount(0);
  await expect(page.locator(".history-count")).toHaveText(
    "Total de documentos salvos: 2",
  );
  expect(deleteRequests).toBe(1);
});
