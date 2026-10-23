import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

test("watchlist opens a real chart and mobile layout fits", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/stocks");
  await page.getByRole("link", { name: "RELIANCE ↗ NSE equity" }).click();
  await expect(page).toHaveURL(/stocks\/RELIANCE/);
  await expect(
    page.getByRole("heading", { name: "RELIANCE", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".chart canvas").first()).toBeVisible();
  await expect(page.locator(".stats")).toContainText("jugaad");
  await page.screenshot({
    path: "test-results/stock-desktop.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator(".chart canvas").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/stock-mobile.png",
    fullPage: false,
  });
  expect(errors).toEqual([]);
});

test("live feed receives actual code-written events and reconnects", async ({
  page,
  context,
}) => {
  await page.goto("/");
  await expect(page.locator(".connection")).toHaveText("Live", {
    timeout: 30000,
  });
  const marker = `browser_drill_${Date.now()}`;
  const python =
    process.platform === "win32"
      ? "../.venv/Scripts/python.exe"
      : "../.venv/bin/python";
  execFileSync(path.resolve(python), [
    "-c",
    `from shared.logbook import log_event; from uuid import uuid4; assert log_event(uuid4(),'setup','${marker}','success',output_summary='Browser verified live delivery')`,
  ]);
  await expect(
    page
      .locator(".event-title")
      .filter({ hasText: marker.replaceAll("_", " ") }),
  ).toBeVisible({ timeout: 10000 });
  await context.setOffline(true);
  await expect(page.locator(".connection")).toHaveText("Reconnecting", {
    timeout: 45000,
  });
  await context.setOffline(false);
  await expect(page.locator(".connection")).toHaveText("Live", {
    timeout: 30000,
  });
  await page.screenshot({
    path: "test-results/live-feed.png",
    fullPage: false,
  });
});

test("logbook filters and run navigation work", async ({ page }) => {
  await page.goto("/logbook");
  await page.getByLabel("Status", { exact: true }).selectOption("failed");
  await expect(page.locator(".event").first()).toBeVisible();
  await expect
    .poll(async () => {
      const statuses = await page
        .locator(".event summary .badge")
        .allTextContents();
      return statuses.length > 0 && statuses.every((s) => s === "failed");
    })
    .toBe(true);
  await page.locator(".event summary").first().click();
  await page.locator('.event[open] a[href^="/logbook/run/"]').click();
  await expect(
    page.getByRole("heading", { name: "Run timeline" }),
  ).toBeVisible();
  await expect(page.locator(".event").first()).toBeVisible();
});
