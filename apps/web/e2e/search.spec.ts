import { expect, test } from "@playwright/test";

const shots = process.env.E2E_SCREENSHOTS;

async function shot(page: import("@playwright/test").Page, name: string, projectName: string) {
  if (shots) await page.screenshot({ path: `${shots}/${projectName}-${name}.png`, fullPage: true });
}

test("root redirects to the visitor's language", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/fa$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});

test("search from the home page shows results with sources and evidence", async ({ page }, info) => {
  await page.goto("/fa");
  await shot(page, "home", info.project.name);

  await page.getByLabel("کشور").selectOption("CA");
  await expect(page.getByLabel("شهر")).toBeEnabled();
  await page.getByLabel("شهر").selectOption("toronto");
  await page.getByRole("button", { name: "رستوران و کافه" }).click();
  await page.getByRole("button", { name: "جست‌وجو", exact: true }).click();

  await expect(page).toHaveURL(/\/fa\/search\?country=CA&city=toronto&categories=restaurant/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText("تورنتو");
  const cards = page.locator("article");
  await expect(cards.first()).toBeVisible();
  await expect(cards.first().getByText("چرا ایرانی؟")).toBeVisible();
  await expect(cards.first().getByText("منابع:")).toBeVisible();
  await expect(cards.first().getByRole("link", { name: "Google Maps" })).toHaveAttribute(
    "href",
    /google\.com\/maps\/search/,
  );
  await shot(page, "results", info.project.name);
});

test("form validation asks for a category", async ({ page }) => {
  await page.goto("/fa");
  await page.getByLabel("کشور").selectOption("DE");
  await page.getByLabel("شهر").selectOption("hamburg");
  await page.getByRole("button", { name: "جست‌وجو", exact: true }).click();
  await expect(page.locator("form").getByRole("alert")).toHaveText("حداقل یک دسته را انتخاب کنید");
});

test("language switch keeps the search", async ({ page }, info) => {
  await page.goto("/fa/search?country=DE&city=hamburg&categories=restaurant");
  await page.getByRole("link", { name: "English" }).click();
  await expect(page).toHaveURL(/\/en\/search\?country=DE&city=hamburg&categories=restaurant/);
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Hamburg");
  await expect(page.locator("article").first().getByText("Why Iranian?")).toBeVisible();
  await shot(page, "results-en", info.project.name);
});

test("report dialog sends a report", async ({ page }, info) => {
  await page.goto("/fa/search?country=CA&city=toronto&categories=grocery");
  const card = page.locator("article").first();
  await card.getByRole("button", { name: "گزارش اشتباه" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("اطلاعات اشتباه است").check();
  await shot(page, "report", info.project.name);
  await dialog.getByRole("button", { name: "ارسال" }).click();
  await expect(dialog.getByText("ممنون! گزارش شما ثبت شد.")).toBeVisible();
});

test("static pages render", async ({ page }) => {
  for (const [path, heading] of [
    ["/fa/how-it-works", "فارسی‌یاب چطور کار می‌کند؟"],
    ["/en/about", "About FarsiYab"],
    ["/fa/privacy", "حریم خصوصی"],
  ]) {
    await page.goto(path);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
  }
});
