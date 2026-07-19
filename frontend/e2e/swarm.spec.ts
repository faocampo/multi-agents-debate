import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("completes, restores, and exports a debate-enabled analysis", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Decision to analyze").fill("Should we launch a reversible pilot?");
  await page.getByRole("button", { name: /Analyze decision/i }).click();

  await expect(page.getByRole("heading", { name: "Customer Advocate" })).toBeVisible();
  await expect(page.getByText("Run a reversible pilot with explicit success thresholds.")).toBeVisible();
  await expect(page.getByText("completed", { exact: true }).first()).toBeVisible();

  await page.reload();
  await expect(page.getByText("Run a reversible pilot with explicit success thresholds.")).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: /Download .md/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/^swarm-analysis-\d{4}-\d{2}-\d{2}-[a-f0-9]{8}\.md$/);
  const path = await download.path();
  expect(path).not.toBeNull();
  const markdown = await readFile(path!, "utf8");
  expect(markdown).toContain("## Debate rebuttals");
  expect(markdown).toContain("## Final synthesis");
});

test("creates and uses a backend-selected saved role panel", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Settings", exact: true }).click();

  for (const [name, focus, bias] of [
    ["Market Strategist", "Market positioning", "Prefer optionality"],
    ["Delivery Lead", "Execution constraints", "Prefer simplicity"],
    ["Risk Reviewer", "Failure modes", "Prefer evidence"],
  ]) {
    await page.getByRole("textbox", { name: /^Name/ }).fill(name);
    await page.getByRole("textbox", { name: /^Focus/ }).fill(focus);
    await page.getByRole("textbox", { name: /^Bias/ }).fill(bias);
    await page.getByRole("button", { name: "Add role" }).click();
    await expect(page.getByText(name, { exact: true })).toBeVisible();
  }

  await page.getByRole("button", { name: "Analysis", exact: true }).click();
  await page.getByRole("checkbox", { name: /Use saved roles/i }).check();
  await page.getByLabel("Decision to analyze").fill("Should we use our saved panel?");
  await page.getByRole("button", { name: /Analyze decision/i }).click();

  await expect(page.getByRole("heading", { name: "Market Strategist" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Delivery Lead" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Risk Reviewer" })).toBeVisible();
});

test("skips debate when disabled", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Decision to analyze").fill("Should we use direct synthesis?");
  await page.getByRole("checkbox", { name: /Include expert debate/i }).uncheck();
  await page.getByRole("button", { name: /Analyze decision/i }).click();

  await expect(page.getByText("Run a reversible pilot with explicit success thresholds.")).toBeVisible();
  await expect(page.getByText("skipped", { exact: true })).toBeVisible();
});

test("shows a terminal stage failure while retaining experts", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Decision to analyze").fill("[FAIL_ADVOCATE] Test failure retention");
  await page.getByRole("button", { name: /Analyze decision/i }).click();

  await expect(page.getByRole("heading", { name: "Customer Advocate" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "This analysis stopped at one stage." })).toBeVisible();
  await expect(page.getByText(/model provider failed during devils advocate/i)).toBeVisible();
});

