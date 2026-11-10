// Run only against real_api.py (disposable SQLite) and a Next server on 3012.
import { chromium, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch({ channel: "msedge" });
const context = await browser.newContext({ baseURL: "http://localhost:3012" });
const page = await context.newPage();
const username = `smoke_${Date.now()}`;
const output = new URL("../../../.taste-skill/real-smoke/", import.meta.url);
await mkdir(output, { recursive: true });
try {
  await page.goto("/cadastro");
  await page.getByLabel("Nome de usuário", { exact: true }).fill(username);
  await page
    .getByLabel("E-mail", { exact: true })
    .fill(`${username}@example.org`);
  await page.getByLabel("Senha", { exact: true }).fill("senha-local-de-teste");
  await page.getByLabel("Confirmar senha").fill("senha-local-de-teste");
  await page.getByRole("button", { name: "Criar conta", exact: true }).click();
  await expect(
    page.getByText("Conta criada. Entre com seus dados para continuar."),
  ).toBeVisible();
  await page.getByLabel("E-mail ou nome de usuário").fill(username);
  await page.getByLabel("Senha", { exact: true }).fill("senha-local-de-teste");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Painel", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Seu primeiro currículo começa aqui" }),
  ).toBeVisible();
  await expect(page.getByText("0 utilizadas ou reservadas")).toBeVisible();
  const usage = await context.request.get("/api/backend/v1/uso");
  expect(usage.status()).toBe(200);
  expect((await usage.json()).restante).toBe(5);
  expect(usage.headers()["cache-control"]).toBe("private, no-store");
  for (const route of ["painel", "curriculos", "curriculos/novo", "conta"]) {
    await page.goto(`/${route}`);
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: new URL(
          `${route.replaceAll("/", "-")}-${width}.png`,
          output,
        ).pathname.replace(/^\/(\w:)/, "$1"),
        fullPage: true,
      });
    }
  }
  await page.getByRole("button", { name: "Sair da conta" }).first().click();
  await expect(page).toHaveURL(/\/login/);
  expect((await context.request.get("/api/backend/v1/uso")).status()).toBe(401);
  for (const route of ["login", "cadastro"]) {
    await page.goto(`/${route}`);
    for (const width of [390, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
      await page.screenshot({
        path: new URL(`${route}-${width}.png`, output).pathname.replace(
          /^\/(\w:)/,
          "$1",
        ),
        fullPage: true,
      });
    }
  }
  console.log(
    "FastAPI real + SQLite: cadastro, login, painel vazio, cota, conta e logout passaram. Axe/reflow: seis telas, duas larguras, sem violações.",
  );
} finally {
  await browser.close();
}
