import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("marca compartilhada, mascote e alternativa sem imagens", async ({
  page,
  context,
}) => {
  for (const route of ["/login", "/cadastro"]) {
    await page.goto(route);
    const brand = page.getByRole("link", {
      name: "Otimizador de currículos — início",
    });
    await expect(brand).toHaveAttribute("href", "/login");
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      await expect(brand.locator("img")).toBeVisible();
    }
  }
  await context.addCookies([
    {
      name: "curriculo_session",
      value: "empty-test-token",
      domain: "localhost",
      path: "/",
    },
  ]);
  for (const route of ["/painel", "/curriculos"]) {
    await page.goto(route);
    for (const width of [320, 390, 768, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      const brand = page.getByRole("link", {
        name: "Otimizador de currículos — início",
      });
      await expect(brand).toHaveAttribute("href", "/painel");
      await expect
        .poll(() =>
          brand
            .locator("img")
            .evaluate(
              (image: HTMLImageElement) =>
                image.complete && image.naturalWidth > 0,
            ),
        )
        .toBe(true);
      const mascot = page.locator(".empty-mascot");
      await expect
        .poll(() =>
          mascot.evaluate(
            (image: HTMLImageElement) =>
              image.complete && image.naturalWidth > 0,
          ),
        )
        .toBe(true);
      await expect(mascot).toHaveAttribute("alt", "");
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
      ).toBe(true);
      const imageSize = await mascot.boundingBox();
      expect(imageSize?.width).toBe(width >= 1024 ? 144 : 112);
      expect(imageSize?.height).toBe(imageSize?.width);
      expect(
        (
          await new AxeBuilder({ page })
            .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
            .analyze()
        ).violations,
      ).toEqual([]);
    }
  }
  await page.route("**/_next/image?*", (route) => route.abort());
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Seu primeiro currículo começa aqui" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /Preparar novo currículo/ }),
  ).toHaveAttribute("href", "/curriculos/novo");
  const brand = page.getByRole("link", {
    name: "Otimizador de currículos — início",
  });
  await brand.focus();
  await expect(brand).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/painel$/);
});
