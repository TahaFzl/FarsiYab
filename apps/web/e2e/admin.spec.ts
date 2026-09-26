import { expect, test } from "@playwright/test";

// The admin tests need the API started with FARSIYAB_ADMIN_TOKEN and the same value
// in E2E_ADMIN_TOKEN (see apps/web/README.md).
const token = process.env.E2E_ADMIN_TOKEN;

test("a submission reaches the admin review queue", async ({ page }) => {
  test.skip(!token, "E2E_ADMIN_TOKEN is not set");
  const name = `E2E Test Kabab ${Date.now()}`;

  await page.goto("/fa/submit");
  await page.getByRole("combobox", { name: "شهر" }).fill("تورن");
  await page.getByRole("option", { name: /تورنتو/ }).click();
  await page.getByLabel("نام کسب‌وکار").fill(name);
  await page.locator('select[name="category"]').selectOption("restaurant");
  await page.getByLabel("لینک‌های عمومی 1").fill("https://e2e-kabab.example/");
  await page.getByRole("button", { name: "ارسال برای بررسی" }).click();
  await expect(page.getByRole("status")).toContainText("ممنون");

  await page.goto("/fa/admin");
  await expect(page).toHaveURL(/\/fa\/admin\/login/);
  await page.getByLabel("توکن مدیریت").fill("wrong-token");
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page.locator("form").getByRole("alert")).toHaveText("توکن اشتباه است.");
  await page.getByLabel("توکن مدیریت").fill(token!);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/fa\/admin$/);

  await page.getByRole("link", { name: /ثبت‌های جدید/ }).click();
  const item = page.locator("li").filter({ hasText: name });
  await expect(item.getByRole("link", { name: "https://e2e-kabab.example/" })).toBeVisible();
  // Reject, so the test leaves no business behind.
  await item.getByRole("button", { name: "رد" }).click();
  await expect(page.locator("li").filter({ hasText: name })).toHaveCount(0);
});

test("labeling page shows a business and the precision table", async ({ page }) => {
  test.skip(!token, "E2E_ADMIN_TOKEN is not set");
  await page.goto("/fa/admin/login");
  await page.getByLabel("توکن مدیریت").fill(token!);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/fa\/admin$/);
  await page.goto("/fa/admin/labels?city=toronto");
  await expect(page.getByRole("button", { name: "بله، ایرانی است" })).toBeVisible();
  await expect(page.getByText("بالا + متوسط")).toBeVisible();
});
