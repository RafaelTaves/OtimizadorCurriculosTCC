import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

async function login(
  page: import("@playwright/test").Page,
  username = "demonstracao",
) {
  await page.goto("/login");
  await page.getByLabel("E-mail ou nome de usuário").fill(username);
  await page.getByLabel("Senha", { exact: true }).fill("senha-sintetica");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Painel", exact: true }),
  ).toBeVisible();
}
test("protege página, valida cookie e mantém BFF em JSON", async ({
  page,
  request,
  context,
}) => {
  await page.goto("/painel");
  await expect(page).toHaveURL(/\/login/);
  const response = await request.get("/api/backend/v1/uso");
  expect(response.status()).toBe(401);
  expect(response.headers()["content-type"]).toContain("application/json");
  await context.addCookies([
    {
      name: "curriculo_session",
      value: "invalido",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.goto("/painel");
  await expect(page).toHaveURL(/\/login/);
});
test("recusa CSRF inclusive login, logout e cadastro", async ({ request }) => {
  for (const path of ["login", "logout", "cadastro"]) {
    for (const headers of [{}, { origin: "https://externo.example" }] as Record<
      string,
      string
    >[])
      expect(
        (
          await request.post(`/api/auth/${path}`, { headers, data: {} })
        ).status(),
      ).toBe(403);
  }
  expect((await request.get("/api/backend/segredos")).status()).toBe(404);
});
test("login, conta, destino do original, logout e cookie privado", async ({
  page,
  context,
}) => {
  await login(page);
  const cookie = (await context.cookies()).find(
    (c) => c.name === "curriculo_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Lax");
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "synthetic-browser",
  );
  await page
    .getByRole("link", {
      name: "Currículo — dados sintéticos.pdf",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Revisar texto", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Conta", exact: true }).click();
  await expect(page.getByText("demonstracao@example.org")).toBeVisible();
  await page.getByRole("button", { name: "Sair da conta" }).first().click();
  await expect(page).toHaveURL(/\/login/);
  expect(
    (await context.cookies()).some((c) => c.name === "curriculo_session"),
  ).toBe(false);
  await page.goto("/painel");
  await expect(page).toHaveURL(/\/login/);
});
test("painel vazio e falha são estados distintos", async ({
  page,
  context,
}) => {
  await login(page, "vazio");
  await expect(
    page.getByRole("heading", { name: "Seu primeiro currículo começa aqui" }),
  ).toBeVisible();
  await expect(page.getByText("0 utilizadas ou reservadas")).toBeVisible();
  await context.clearCookies();
  await login(page, "falha");
  await expect(
    page.getByText("Não foi possível atualizar estes dados. Tente novamente."),
  ).toHaveCount(2);
  await expect(
    page.getByRole("heading", { name: "Seu primeiro currículo começa aqui" }),
  ).toHaveCount(0);
});
test("reflow e acessibilidade em sete larguras; menu por teclado", async ({
  page,
}) => {
  await login(page);
  for (const width of [320, 375, 390, 768, 1024, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(result.violations).toEqual([]);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  const trigger = page.getByRole("button", { name: "Abrir menu" });
  await trigger.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(trigger).toBeFocused();
  await trigger.click();
  await page
    .getByRole("dialog")
    .getByRole("link", { name: "Currículos", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Seus currículos", exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});
