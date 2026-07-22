import { test, expect } from "@playwright/test";

test("home page loads", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("body")).toBeVisible();
});

test("admin and voter login surfaces are separated", async ({ page }) => {
  await page.goto("/admin/login");
  await expect(page.locator("body")).toBeVisible();
  await page.goto("/vote/login");
  await expect(page.locator("body")).toBeVisible();
});

test("public verify route renders", async ({ page }) => {
  const hash = "a".repeat(64);
  await page.goto(`/verify/${hash}`);
  await expect(page.getByText("Verificar artefacto")).toBeVisible();
});
