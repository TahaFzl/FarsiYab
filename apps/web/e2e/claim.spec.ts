import { expect, test } from "@playwright/test";

// Needs the API started with FARSIYAB_ADMIN_TOKEN and E2E_ADMIN_TOKEN set (README).
const token = process.env.E2E_ADMIN_TOKEN;

test("an owner claims a business by manual check and edits it", async ({ page, request }, info) => {
  test.skip(!token || info.project.name !== "desktop", "needs E2E_ADMIN_TOKEN; runs once");

  // A shown Toronto restaurant, taken from the API like the site does.
  const search = await request.get("/api/v1/search?country=CA&city=toronto&categories=bakery&lang=fa");
  const business = (await search.json()).results[0];

  await page.goto("/fa/search?country=CA&city=toronto&categories=bakery");
  await page.locator(`#b-${business.id}`).getByRole("link", { name: "صاحب این کسب‌وکار هستید؟" }).click();
  await expect(page).toHaveURL(new RegExp(`/fa/claim/${business.id}$`));
  await page.getByLabel(/بررسی دستی توسط ما/).check();
  await page.getByLabel("ایمیل شما").fill("owner@example.com");
  await page.getByRole("button", { name: "ادامه" }).click();
  await expect(page.getByRole("status")).toContainText("کد پیگیری");

  // The admin verifies it and gets the owner link.
  await page.goto("/fa/admin/login");
  await page.getByLabel("توکن مدیریت").fill(token!);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/fa\/admin$/);
  await page.goto("/fa/admin/claims");
  const item = page.locator("li").filter({ hasText: "owner@example.com" }).first();
  await item.getByRole("button", { name: "تأیید و ساخت لینک" }).click();
  const link = (await item.locator("p[dir=ltr]").textContent())!.trim();
  expect(link).toMatch(/\/fa\/owner\/[0-9a-f-]+#key=/);

  // The owner opens the private link and changes the phone number.
  await page.goto(link.replace(/^https?:\/\/[^/]+/, ""));
  await page.getByLabel("تلفن").fill("+1 416 555 0123");
  await page.getByRole("button", { name: "ذخیره" }).click();
  await expect(page.getByRole("status")).toHaveText("ذخیره شد.");

  const card = await request.get(`/api/v1/businesses/${business.id}?lang=fa`);
  const updated = await card.json();
  expect(updated.contact.phone).toBe("+14165550123");
  expect(updated.owner_verified).toBe(true);

  // Put the original number back (the test runs against real indexed data).
  if (business.contact.phone) {
    await page.getByLabel("تلفن").fill(business.contact.phone);
    await page.getByRole("button", { name: "ذخیره" }).click();
    await expect(page.getByRole("status")).toHaveText("ذخیره شد.");
  }
});
