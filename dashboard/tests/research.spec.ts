import { test, expect } from "@playwright/test";

test("stock research loads overlays, indicators, range and signal filters", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/stocks/TCS");
  await expect(
    page.getByRole("heading", { name: "Recent signals" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible({
    timeout: 45000,
  });
  await page.getByRole("checkbox", { name: "SMA 20", exact: true }).check();
  await page.getByLabel("Visible history").selectOption("63");
  await expect(
    page.getByRole("img", {
      name: "63 daily candlesticks with indicator overlays and pattern markers",
    }),
  ).toBeVisible();
  await expect(
    page.getByText("Loading indicators for the selected dates…"),
  ).toBeHidden({ timeout: 45000 });
  await page.getByRole("combobox", { name: "Signal type", exact: true }).selectOption("pattern");
  await page.getByRole("combobox", { name: "Direction", exact: true }).selectOption("bullish");
  await expect(page.locator("tbody tr").first()).toBeVisible();
  for (const text of await page
    .locator("tbody tr td:nth-child(3)")
    .allTextContents())
    expect(text).toBe("bullish");
  await expect(
    page.getByRole("img", { name: "MACD indicator", exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/signals.png", fullPage: true });
  expect(errors).toEqual([]);
});

test("signal lab exposes baseline, independent counts and both samples", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/lab");
  await expect(page.locator("tbody tr").first()).toBeVisible({
    timeout: 45000,
  });
  await expect(
    page.getByRole("columnheader", { name: "IS edge / n", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "OOS edge / n", exact: true }),
  ).toBeVisible();
  await expect(page.locator("tr.insufficient").first()).toContainText(
    "Insufficient sample",
  );
  await page.getByRole("combobox", { name: "Scope", exact: true }).selectOption("TCS");
  await page
    .getByRole("combobox", { name: "Signal", exact: true })
    .selectOption("cdl_engulfing");
  await expect(page.locator("tbody tr").first()).toContainText("cdl_engulfing");
  await expect(page.locator("tbody tr").first()).toContainText("TCS");
  await page.screenshot({
    path: "test-results/signal-lab.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("backtest details compare strategy and benchmark with trades", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/backtests");
  await page
    .getByRole("link", { name: "rsi reversion", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", {
      name: "In-sample vs out-of-sample",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: "Strategy equity versus buy-and-hold" }),
  ).toBeVisible();
  await page.getByRole("combobox", { name: "Stock", exact: true }).selectOption("TCS");
  await page.getByRole("combobox", { name: "Sample", exact: true }).selectOption("all");
  await expect(
    page.getByRole("columnheader", { name: "Exit reason", exact: true }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/backtest.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});
