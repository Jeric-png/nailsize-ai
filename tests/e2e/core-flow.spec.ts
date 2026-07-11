import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("landing and preparation are usable without serious accessibility violations", async ({
  page,
}, testInfo) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Size every nail",
  );
  await expect(
    page.getByText("Photos are processed transiently"),
  ).toBeVisible();

  const landingA11y = await new AxeBuilder({ page }).analyze();
  expect(
    landingA11y.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);

  await page.getByRole("link", { name: "Start sizing" }).click();
  await expect(page).toHaveURL(/\/prepare$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Prepare",
  );
  await page.getByRole("link", { name: "I’m ready" }).click();
  await expect(page).toHaveURL(/\/capture\/left_fingers$/);
  await expect(page.getByText("Capture 1 of 4")).toBeVisible();

  await page.screenshot({
    path: `test-results/${testInfo.project.name}-capture.png`,
    fullPage: true,
  });
});

test("unknown routes recover to the landing page", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("link", { name: "Start sizing" })).toBeVisible();
});
