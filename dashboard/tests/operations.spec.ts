import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { parseEnv } from "node:util";
import { createClient } from "@supabase/supabase-js";
const env = parseEnv(readFileSync("../.env", "utf8")) as Record<string, string>;

test("operations protect writes and display real adjustment previews", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const unauthorized = await request.post("/api/ops", {
    data: { id: 1, action: "retry" },
  });
  expect(unauthorized.status()).toBe(401);
  await page.goto("/ops");
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
  await page.goto("/corporate-actions");
  await expect(
    page.getByRole("heading", { name: "Corporate-action review" }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: /RELIANCE raw/ })).toBeVisible();
  await expect(
    page.getByText("Passed within 0.5% tolerance", { exact: false }),
  ).toHaveCount(2);
  await expect(
    page.getByRole("button", { name: "Approve factor" }).first(),
  ).toBeDisabled();
  await page.screenshot({
    path: "test-results/adjustment-review.png",
    fullPage: true,
  });
  // Exercise the authenticated route without changing a real job or approving an action.
  const auth = createClient(
    env.SUPABASE_URL,
    env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    { auth: { persistSession: false } },
  );
  const login = await auth.auth.signInWithPassword({
    email: env.DASHBOARD_EMAIL,
    password: env.DASHBOARD_PASSWORD,
  });
  expect(login.error).toBeNull();
  const token = login.data.session!.access_token;
  const invalid = await request.post("/api/ops", {
    headers: { Authorization: `Bearer ${token}` },
    data: { id: -1, action: "retry" },
  });
  expect(invalid.status()).toBe(400);
  const noTarget = await request.post("/api/ops", {
    headers: { Authorization: `Bearer ${token}` },
    data: { id: 9007199254740990, action: "cancel" },
  });
  expect(noTarget.status()).toBe(200);
  expect((await noTarget.json()).changed).toBe(false);
  const crossOrigin = await request.post("/api/ops", {
    headers: {
      Authorization: `Bearer ${token}`,
      Origin: "https://untrusted.example",
    },
    data: { id: 1, action: "retry" },
  });
  expect(crossOrigin.status()).toBe(403);
  await page.goto("/alerts");
  await expect(
    page.getByRole("heading", { name: "Alerts", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/backup_missing/).first()).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/ops");
  await expect(
    page.getByRole("heading", { name: "Pipeline operations" }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
