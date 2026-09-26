import { expect, test } from "@playwright/test";

test("city pages link to indexable category pages", async ({ page }) => {
  await page.goto("/fa");
  await page.getByRole("link", { name: "تورنتو", exact: true }).click();
  await expect(page).toHaveURL(/\/fa\/toronto$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("کسب‌وکارهای ایرانی و فارسی‌زبان در تورنتو");

  await page.getByRole("link", { name: /^رستوران و کافه/ }).click();
  await expect(page).toHaveURL(/\/fa\/toronto\/restaurant$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("رستوران و کافه ایرانی در تورنتو");
  await expect(page.locator("article").first()).toBeVisible();
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute("href", /\/fa\/toronto\/restaurant$/);
  await expect(page.locator('link[rel="alternate"][hreflang="en"]')).toHaveAttribute(
    "href",
    /\/en\/toronto\/restaurant$/,
  );
});

test("subcategory pages and unknown cities", async ({ page }) => {
  await page.goto("/en/toronto/doctor/dentist");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("in Toronto");
  const missing = await page.goto("/fa/atlantis");
  expect(missing?.status()).toBe(404);
});

test("sitemap lists city and category pages; robots hides search", async ({ request }) => {
  const sitemap = await (await request.get("/sitemap.xml")).text();
  expect(sitemap).toContain("/fa/toronto/restaurant</loc>");
  expect(sitemap).toContain('hreflang="en"');
  const robots = await (await request.get("/robots.txt")).text();
  expect(robots).toContain("Disallow: /fa/search");
});
