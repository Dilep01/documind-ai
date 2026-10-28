import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const root = fileURLToPath(new URL("../../", import.meta.url));
const config = fs.readFileSync(path.join(root, ".env"), "utf8");
const password =
  process.env.DOCUMIND_ADMIN_PASSWORD ||
  config.match(/^DOCUMIND_ADMIN_PASSWORD=(.+)$/m)?.[1].trim();
if (!password)
  throw new Error("Local test administrator configuration is missing.");

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "A clearer view of your paperwork." }),
  ).toBeVisible();
});

test("upload, evidence, revision, approval, export, and approval invalidation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const name = `browser-demo-${Date.now()}.pdf`;
  await page.locator("input[type=file]").setInputFiles({
    name,
    mimeType: "application/pdf",
    buffer: fs.readFileSync(path.join(root, "data/samples/digital_basic.pdf")),
  });
  const row = page.getByRole("row").filter({ hasText: name });
  await expect(row.getByText("needs review", { exact: true })).toBeVisible({
    timeout: 90000,
  });
  await row
    .getByRole("button", { name: "Review " + name, exact: true })
    .click();
  await expect(page.getByLabel("vendor name", { exact: true })).toHaveValue(
    "Cedar Office Supplies",
  );
  await page
    .getByRole("button", { name: "Show source for total", exact: true })
    .click();
  await expect(page.locator("svg.source-overlay rect")).toBeVisible();
  await page.screenshot({
    path: path.join(root, "docs/demo/review.png"),
    fullPage: true,
  });
  await page
    .getByLabel("vendor name", { exact: true })
    .fill("Reviewed Cedar Office Supplies");
  await page
    .getByRole("combobox", { name: "Totals calculation", exact: true })
    .selectOption("tax_exclusive");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Checked the source and selected tax-exclusive totals.");
  await page
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(
    page.locator(".review-heading").getByText(/Revision 2/),
  ).toBeVisible();
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Verified every printed field and line item against the original.");
  await page.getByLabel("I checked the warnings against the source.").check();
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Export approved revision" }),
  ).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export approved revision" }).click();
  const download = await downloadEvent;
  await download.saveAs(path.join(root, "docs/demo/approved-example.csv"));
  await expect(page.getByLabel("vendor name", { exact: true })).toHaveValue(
    "Reviewed Cedar Office Supplies",
  );
  await page
    .getByLabel("customer name", { exact: true })
    .fill("Updated Demo Studio");
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Changed the customer; approval must be checked again.");
  await page
    .getByRole("button", { name: "Save revision", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Export approved revision" }),
  ).toHaveCount(0);
  await expect(page.locator(".badge.needs_review")).toBeVisible();
  await page.getByRole("button", { name: "Back to documents" }).click();
  await page.getByRole("button", { name: "Search & ask", exact: true }).click();
  await page.getByLabel("Search documents", { exact: true }).fill("Cedar");
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await expect(page.locator(".result-card").first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile workspace remains usable without horizontal overflow", async ({
  page,
}) => {
  await page.screenshot({
    path: path.join(root, "docs/demo/overview.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(
    page.getByRole("button", { name: "Upload documents", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: path.join(root, "docs/demo/mobile.png"),
    fullPage: true,
  });
});
