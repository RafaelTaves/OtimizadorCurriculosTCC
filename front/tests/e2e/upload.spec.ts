import { expect, test } from "@playwright/test";

test("envia currículo, exige revisar o texto e só habilita a IA após consentimento", async ({
  page,
}) => {
  await page.goto("/login");
  await page.getByLabel("E-mail ou nome de usuário").fill("demonstracao");
  await page.getByLabel("Senha", { exact: true }).fill("senha-sintetica");
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Painel", exact: true }),
  ).toBeVisible();

  await page.goto("/curriculos/novo");
  const file = page.locator("#arquivo");
  await file.setInputFiles({
    name: "curriculo-sintetico.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7 synthetic test only"),
  });
  await page
    .getByLabel("Descrição da vaga")
    .fill(
      "Vaga de demonstração para desenvolvimento de software com APIs e testes automatizados.",
    );
  await page
    .getByRole("button", { name: "Enviar e revisar", exact: true })
    .click();
  await expect(page).toHaveURL(
    /\/curriculos\/00000000-0000-4000-8000-000000000099\/revisao$/,
  );
  await expect(page.getByLabel("Texto extraído")).toHaveValue(/Ana Silva/);
  await expect(
    page.getByRole("button", { name: "Confirmar texto" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("heading", { name: "Como deseja continuar?" }),
  ).toHaveCount(0);

  await page.getByRole("button", { name: "Confirmar texto" }).click();
  await expect(
    page.getByRole("heading", { name: "Como deseja continuar?" }),
  ).toBeVisible();
  const optimize = page.getByRole("button", {
    name: "Gerar com o texto confirmado",
  });
  await expect(optimize).toBeDisabled();
  await page
    .getByRole("checkbox", { name: /Autorizo enviar o texto confirmado/ })
    .check();
  await expect(optimize).toBeEnabled();
});

test("a tela de envio reflowa em 320 a 1440 px", async ({ page, context }) => {
  await context.addCookies([
    {
      name: "curriculo_session",
      value: "synthetic-browser-test-token",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.goto("/curriculos/novo");
  await expect(
    page.getByRole("heading", { name: "Novo currículo", exact: true }),
  ).toBeVisible();
  for (const width of [320, 390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await expect(page.getByLabel("Arquivo do currículo")).toBeAttached();
    await expect(page.getByLabel("Descrição da vaga")).toBeVisible();
  }
});

test("consulta a sessão ativa e oferece retomada sem iniciar outra", async ({
  page,
  context,
}) => {
  await context.addCookies([
    {
      name: "curriculo_session",
      value: "synthetic-browser-test-token",
      domain: "localhost",
      path: "/",
    },
  ]);
  await page.goto(
    "/curriculos/00000000-0000-4000-8000-000000000099/complementacoes",
  );
  const resume = page.getByRole("link", { name: "Continuar entrevista" });
  await expect(resume).toHaveAttribute(
    "href",
    "/complementacoes/00000000-0000-4000-8000-000000000066",
  );
  await expect(
    page.getByText("Há uma sessão que pode ser retomada."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Consentir e iniciar entrevista" }),
  ).toBeDisabled();
});
