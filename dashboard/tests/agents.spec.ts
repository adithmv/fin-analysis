import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

const env = Object.fromEntries(
  readFileSync(path.resolve("../.env"), "utf8")
    .split(/\r?\n/)
    .filter((l) => l.includes("=") && !l.startsWith("#"))
    .map((l) => {
      const i = l.indexOf("=");
      return [l.slice(0, i), l.slice(i + 1).replace(/^['"]|['"]$/g, "")];
    }),
);

test("private research requires login and owner can inspect evidence and outcomes", async ({
  page,
}) => {
  test.setTimeout(120000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/threads");
  await expect(
    page.getByRole("heading", { name: "Sign in to continue" }),
  ).toBeVisible();
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(env.DASHBOARD_EMAIL);
  await page
    .getByLabel("Password", { exact: true })
    .fill(env.DASHBOARD_PASSWORD);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "You’re signed in" }),
  ).toBeVisible();
  await page.goto("/threads");
  await expect(
    page.getByRole("heading", { name: "Research discussions" }),
  ).toBeVisible();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  const complete = page
    .locator("tbody tr")
    .filter({ hasText: "Completed" })
    .first();
  await complete.getByRole("link").click();
  await expect(
    page.getByRole("heading", { name: "Research report", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(
      ".message:not(.role-user):not(.role-system):not(.role-research_assistant)",
    ),
  ).toHaveCount(8);
  await page
    .getByRole("button", { name: /e\d{4}/ })
    .first()
    .click();
  await expect(
    page.getByRole("region", { name: "Selected evidence" }),
  ).toBeVisible();
  await page.screenshot({
    path: "test-results/discussion-desktop.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/discussion-mobile.png",
    fullPage: false,
  });
  const beforeRefusals = await page
    .getByText(
      /I can discuss stored research evidence, but cannot provide trading instructions/,
    )
    .count();
  await page.getByLabel("Your research question").fill("Should I buy this?");
  await page
    .getByRole("button", { name: "Ask the research assistant" })
    .click();
  await expect(page.getByText(/Question queued/)).toBeVisible();
  await expect(
    page.getByText(
      /I can discuss stored research evidence, but cannot provide trading instructions/,
    ),
  ).toHaveCount(beforeRefusals + 1, { timeout: 30000 });
  await page.goto("/usage");
  await expect(
    page.getByRole("heading", { name: "Research call budget" }),
  ).toBeVisible();
  await expect(page.locator(".stats")).toContainText(/\d+\s*\/\s*[1-9]\d*/);
  const historicalDay = await page
    .getByLabel("Usage day (Pacific)")
    .locator("option")
    .last()
    .getAttribute("value");
  await page.getByLabel("Usage day (Pacific)").selectOption(historicalDay!);
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.goto("/track-record");
  await expect(
    page.getByRole("heading", { name: "Report track record" }),
  ).toBeVisible();
  await expect(
    page.getByText("No directional outcomes yet", { exact: true }).first(),
  ).toBeVisible();
  await page.goto("/login");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.goto("/usage");
  await expect(
    page.getByRole("heading", { name: "Sign in to continue" }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});
