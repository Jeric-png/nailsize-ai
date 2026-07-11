import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const captureDigits = {
  left_fingers: ["index", "middle", "ring", "pinky"],
  left_thumb: ["thumb"],
  right_fingers: ["index", "middle", "ring", "pinky"],
  right_thumb: ["thumb"],
} as const;

const onePixelPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4AWJi+M/wHwAAAP//Qn/6uQAAAAZJREFUAwAECwIBcGRBzAAAAABJRU5ErkJggg==",
  "base64",
);

function captureTypeFromMultipart(body: Buffer | null) {
  const value = body?.toString("utf8") ?? "";
  return Object.keys(captureDigits).find((type) => value.includes(type)) as
    keyof typeof captureDigits | undefined;
}

function successfulMeasurement(captureType: keyof typeof captureDigits) {
  return {
    status: "ok",
    request_id: `request-${captureType}`,
    capture_type: captureType,
    measurements: captureDigits[captureType].map((digit, index, digits) => {
      const left = digits.length === 1 ? 0.38 : 0.08 + index * 0.22;
      return {
        digit,
        projected_width_mm: 10.4 + index,
        uncertainty_mm: 0.3,
        recommended_size: String(8 - index),
        alternate_size: null,
        confidence: "high",
        contour: [
          [left, 0.25],
          [left + 0.14, 0.25],
          [left + 0.14, 0.72],
          [left, 0.72],
        ],
      };
    }),
    quality_issues: [],
    model_version: "e2e-fixture",
    chart_id: "platform-default",
    chart_version: "1",
    processing_ms: 12,
  };
}

async function selectTestPhoto(page: Page) {
  await page.locator('input[type="file"]').setInputFiles({
    name: "nails.png",
    mimeType: "image/png",
    buffer: onePixelPng,
  });
}

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
}

async function expectVisual(page: Page, name: string) {
  if (process.env.NAILSIZE_SKIP_VISUAL_ASSERTIONS === "1") return;
  await expect(page).toHaveScreenshot(name, { fullPage: true });
}

test("landing, preparation, and capture have no serious accessibility violations", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Size every nail",
  );
  await expect(
    page.getByText("Photos are processed transiently"),
  ).toBeVisible();
  await expectVisual(page, "landing.png");

  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("link", { name: "Start sizing" }).click();
  await expect(page).toHaveURL(/\/prepare$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Prepare",
  );
  await expectVisual(page, "preparation.png");
  await expectNoSeriousAccessibilityViolations(page);
  await page.getByRole("link", { name: "I’m ready" }).click();
  await expect(page).toHaveURL(/\/capture\/left_fingers$/);
  await expect(page.getByText("Capture 1 of 4")).toBeVisible();
  await expectVisual(page, "capture.png");
  await expectNoSeriousAccessibilityViolations(page);
});

test("unknown routes recover to the landing page", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("link", { name: "Start sizing" })).toBeVisible();
});

test("privacy notice explains transient processing without hidden persistence", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Privacy notice" }).click();
  await expect(page).toHaveURL(/\/privacy$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Your photos stay temporary.",
  );
  await expect(page.getByText("transient memory")).toBeVisible();
  await expect(page.getByText("does not write photos")).toBeVisible();
  await expect(page.getByText("not added to a training dataset")).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
});

test("primary capture navigation is keyboard operable", async ({
  browserName,
  page,
}) => {
  await page.goto("/");
  const brand = page.getByRole("link", { name: "NAILSIZE / AI" });
  const start = page.getByRole("link", { name: "Start sizing" });

  if (browserName === "webkit") await brand.focus();
  else await page.keyboard.press("Tab");
  await expect(brand).toBeFocused();
  if (browserName === "webkit") await start.focus();
  else await page.keyboard.press("Tab");
  await expect(start).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/prepare$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();

  const ready = page.getByRole("link", { name: "I’m ready" });
  if (browserName === "webkit") await ready.focus();
  else await page.keyboard.press("Tab");
  await expect(ready).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/capture\/left_fingers$/);
  await expect(page.getByRole("heading", { level: 1 })).toBeFocused();

  const capture = page.getByRole("button", { name: "Take or choose photo" });
  if (browserName === "webkit") await capture.focus();
  else await page.keyboard.press("Tab");
  await expect(capture).toBeFocused();
});

test("an expired in-memory session explains the privacy-safe reset", async ({
  page,
}) => {
  await page.goto("/results");
  await expect(page).toHaveURL(/\/recover\/session$/);
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "no longer available",
  );
  await expectVisual(page, "session-recovery.png");
  await expectNoSeriousAccessibilityViolations(page);
  await page
    .getByRole("button", { name: "Start a new sizing session" })
    .click();
  await expect(page).toHaveURL(/\/$/);
});

test("camera denial and picker cancellation preserve the file fallback", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: {
        getUserMedia: () =>
          Promise.reject(new DOMException("Camera denied", "NotAllowedError")),
      },
    });
  });
  await page.goto("/capture/left_fingers");

  const chooserPromise = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Take or choose photo" }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles([]);
  await expect(
    page.getByRole("button", { name: "Check this photo" }),
  ).toBeDisabled();

  await selectTestPhoto(page);
  await expect(
    page.getByRole("button", { name: "Check this photo" }),
  ).toBeEnabled();
});

test("offline interruption retries the same in-memory capture", async ({
  page,
}) => {
  let attempts = 0;
  await page.route("http://localhost:8000/v1/measure", async (route) => {
    attempts += 1;
    if (attempts === 1) {
      await route.abort("internetdisconnected");
      return;
    }
    await route.fulfill({ json: successfulMeasurement("left_thumb") });
  });
  await page.goto("/capture/left_thumb");
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Check this photo" }).click();

  await expect(
    page.getByText(
      "The sizing service could not be reached. Check your connection and retry.",
    ),
  ).toBeVisible();
  await page.getByRole("button", { name: "Retry check" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Photo accepted.",
  );
  expect(attempts).toBe(2);
});

test("four accepted captures produce ten shareable results and a targeted correction", async ({
  context,
  page,
}) => {
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: async () => undefined },
    });
  });
  await page.route("http://localhost:8000/v1/measure", async (route) => {
    const body = route.request().postDataBuffer();
    const captureType = captureTypeFromMultipart(body);
    expect(captureType).toBeTruthy();
    const multipart = body?.toString("latin1") ?? "";
    const hasWebpPayload = multipart.includes('filename="nails.webp"');
    const hasPngFallback = multipart.includes('filename="nails.png"');
    expect(hasWebpPayload || hasPngFallback).toBe(true);
    expect(multipart).toContain(
      hasWebpPayload ? "Content-Type: image/webp" : "Content-Type: image/png",
    );
    await route.fulfill({ json: successfulMeasurement(captureType!) });
  });

  await page.goto("/capture/left_fingers");
  for (const [index, captureType] of Object.keys(captureDigits).entries()) {
    await expect(page).toHaveURL(new RegExp(`/capture/${captureType}$`));
    await selectTestPhoto(page);
    await page.getByRole("button", { name: "Check this photo" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Photo accepted.",
    );
    if (index === 0) {
      await expectVisual(page, "quality-accepted.png");
      await expectNoSeriousAccessibilityViolations(page);
    }
    await page
      .getByRole("button", {
        name: index === 3 ? "Finish measurements" : "Continue",
      })
      .click();
  }

  await expect(page).toHaveURL(/\/processing$/);
  await expectVisual(page, "processing.png");
  await expectNoSeriousAccessibilityViolations(page);
  await page.getByRole("button", { name: "Review results" }).click();
  await expect(page).toHaveURL(/\/results$/);
  const mobile = (page.viewportSize()?.width ?? 1280) < 800;
  await expect(page.locator(".measurement-row:visible")).toHaveCount(
    mobile ? 5 : 10,
  );
  await expectVisual(page, "results.png");
  await expectNoSeriousAccessibilityViolations(page);
  await page.getByRole("button", { name: "Copy results" }).click();
  await expect(
    page.getByText("Results copied. No photos were included."),
  ).toBeVisible();

  await page
    .getByRole("button", { name: "Retake", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/capture\/left_fingers$/);
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Check this photo" }).click();
  await expect(
    page.getByRole("button", { name: "Return to results" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Return to results" }).click();
  await expect(page.locator(".measurement-row:visible")).toHaveCount(
    mobile ? 5 : 10,
  );
  if (mobile) await page.getByRole("tab", { name: "Right hand" }).click();
  await expect(
    page.locator(".measurement-row:visible").filter({ hasText: "thumb" }),
  ).toHaveCount(mobile ? 1 : 2);
  await page
    .getByRole("button", { name: "Start over and erase session" })
    .click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/results");
  await expect(page).toHaveURL(/\/recover\/session$/);
});

test("unsupported uploads show a typed replacement path", async ({ page }) => {
  await page.route("http://localhost:8000/v1/measure", async (route) => {
    await route.fulfill({ status: 415, body: "unsupported" });
  });
  await page.goto("/capture/left_thumb");
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Check this photo" }).click();

  await expect(
    page.getByText(
      "This file is not a supported JPEG, PNG, WebP, HEIC, or HEIF image.",
    ),
  ).toBeVisible();
  await expectVisual(page, "unsupported-error.png");
  await expectNoSeriousAccessibilityViolations(page);
  await page.getByRole("button", { name: "Choose another photo" }).click();
  await expect(page).toHaveURL(/\/capture\/left_thumb$/);
  await expect(
    page.getByRole("button", { name: "Choose another photo" }),
  ).toBeVisible();
});
