import { test, expect } from "@playwright/test";

test("news archive filters, detail, sources and mobile layout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/news");
  await expect(page.locator(".news-item").first()).toBeVisible({
    timeout: 45000,
  });
  await page
    .getByRole("combobox", { name: "Symbol", exact: true })
    .selectOption("TCS");
  for (const item of await page.locator(".news-item").all())
    await expect(item).toContainText("TCS");
  await page.screenshot({ path: "test-results/news.png", fullPage: false });
  await page
    .locator(".news-item")
    .first()
    .getByRole("link", { name: "Details & past events →" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Article sentiment", exact: true }),
  ).toBeVisible({ timeout: 45000 });
  await expect(
    page.getByText("Anecdotal similarity, not statistical evidence.", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Find similar past events" }).click();
  await expect(
    page.getByRole("button", { name: "Find similar past events" }),
  ).toBeEnabled({ timeout: 45000 });
  await expect(page.locator(".error[role=alert]")).toHaveCount(0);
  await page.goto("/sources");
  await expect(page.locator("tbody tr")).toHaveCount(7, { timeout: 45000 });
  await expect(page.getByText("Disabled", { exact: true })).toBeVisible();
  await page.screenshot({ path: "test-results/sources.png", fullPage: false });
  await page.goto("/news");
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".news-item").first()).toBeVisible({
    timeout: 45000,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/news-mobile.png",
    fullPage: false,
  });
  expect(errors).toEqual([]);
});

test("local semantic search and abnormal event studies", async ({ page }) => {
  await page.goto("/search");
  await page
    .getByLabel("What are you researching?")
    .fill("TCS quarterly earnings profit");
  await page
    .getByRole("combobox", { name: "Symbol", exact: true })
    .selectOption("TCS");
  await page.getByRole("button", { name: "Search stories" }).click();
  await expect(page.locator(".news-item").first()).toBeVisible({
    timeout: 45000,
  });
  await expect(page.locator(".news-item").first()).toContainText("TCS");
  await page.screenshot({ path: "test-results/search.png", fullPage: false });
  await page.goto("/lab");
  await page
    .getByRole("combobox", { name: "Study source", exact: true })
    .selectOption("news");
  await page
    .getByRole("combobox", { name: "Market adjustment", exact: true })
    .selectOption("true");
  await expect(page.locator("tbody tr").first()).toBeVisible({
    timeout: 45000,
  });
  await expect(page.locator("tbody tr").first()).toContainText("news:");
  await expect(
    page.getByRole("columnheader", { name: "Absolute move", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("combobox", { name: "Study source", exact: true })
    .selectOption("sentiment");
  await expect(page.locator("tbody tr").first()).toContainText("sentiment:", {
    timeout: 45000,
  });
  await page.goto("/stocks/TCS");
  await expect(
    page.getByRole("heading", { name: "Daily news sentiment" }),
  ).toBeVisible();
  await expect(page.locator(".sentiment-day").first()).toBeVisible({
    timeout: 45000,
  });
  await expect(
    page.getByRole("heading", { name: "Corporate actions", exact: true }),
  ).toBeVisible();
});
