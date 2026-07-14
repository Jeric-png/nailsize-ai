import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const captureDigits = {
  left_fingers: ["index", "middle", "ring", "pinky"],
  left_thumb: ["thumb"],
  right_fingers: ["index", "middle", "ring", "pinky"],
  right_thumb: ["thumb"],
} as const;

async function expectNoSeriousAccessibilityViolations(page: Page) {
  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter((item) =>
      ["critical", "serious"].includes(item.impact ?? ""),
    ),
  ).toEqual([]);
}

let syntheticPhotoSequence = 0;

interface SyntheticPhotoOptions {
  width?: number;
  height?: number;
}

async function syntheticPhotoBytes(
  page: Page,
  sequence: number,
  options: SyntheticPhotoOptions = {},
) {
  const bytes = await page.evaluate(
    async (fixture) => {
      const canvas = document.createElement("canvas");
      canvas.width = fixture.width;
      canvas.height = fixture.height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Synthetic fixture canvas is unavailable.");
      context.fillStyle = `rgb(${220 + (fixture.sequence % 20)}, 232, 239)`;
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.fillStyle = "#101820";
      context.font = "24px sans-serif";
      context.fillText(`fixture-${fixture.sequence}`, 24, 40);
      const coinCenter = { x: canvas.width * 0.23, y: canvas.height * 0.22 };
      const coinRadius = Math.min(canvas.width, canvas.height) * 0.18;
      context.beginPath();
      context.arc(coinCenter.x, coinCenter.y, coinRadius, 0, Math.PI * 2);
      context.fillStyle = "#d5d9dc";
      context.fill();
      context.lineWidth = 3;
      context.strokeStyle = "#4b5258";
      context.stroke();
      context.fillStyle = "#30363a";
      context.font = "bold 24px sans-serif";
      context.fillText("50", coinCenter.x - 15, coinCenter.y + 5);
      const blob = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(
          (value) =>
            value ? resolve(value) : reject(new Error("PNG encoding failed.")),
          "image/png",
        ),
      );
      return [...new Uint8Array(await blob.arrayBuffer())];
    },
    {
      sequence,
      width: options.width ?? 600,
      height: options.height ?? 800,
    },
  );
  return Buffer.from(bytes);
}

async function selectTestPhoto(
  page: Page,
  sequence = ++syntheticPhotoSequence,
  options: SyntheticPhotoOptions = {},
) {
  await uploadTestPhoto(page, sequence, options);
  await expect(
    page.getByRole("button", { name: "Mark coin rim" }),
  ).toBeEnabled();
}

async function uploadTestPhoto(
  page: Page,
  sequence: number,
  options: SyntheticPhotoOptions = {},
) {
  const buffer = await syntheticPhotoBytes(page, sequence, options);
  await page.locator('input[type="file"]').setInputFiles({
    name: "synthetic-nail-capture.png",
    mimeType: "image/png",
    buffer,
  });
}

async function confirmCoinAndStart(
  page: Page,
  captureType: keyof typeof captureDigits = "left_fingers",
) {
  await page.goto("/prepare");
  await page
    .getByRole("checkbox", { name: /I have the Third Series/i })
    .check();
  await page.getByRole("button", { name: "I’m ready" }).click();
  if (captureType !== "left_fingers") {
    await page.evaluate((path) => {
      window.history.pushState({}, "", path);
      window.dispatchEvent(new PopStateEvent("popstate"));
    }, `/capture/${captureType}/1`);
  }
  await expect(page).toHaveURL(new RegExp(`/capture/${captureType}/1$`));
}

async function placeCoinRim(
  page: Page,
  dimensions = { width: 600, height: 800 },
) {
  const overlay = page.locator(".annotation-overlay--calibration");
  await overlay.scrollIntoViewIfNeeded();
  const bounds = await overlay.boundingBox();
  expect(bounds).not.toBeNull();
  const radiusPx = Math.min(dimensions.width, dimensions.height) * 0.18;
  const centerPx = {
    x: dimensions.width * 0.23,
    y: dimensions.height * 0.22,
  };
  for (let index = 0; index < 8; index += 1) {
    const angle = -Math.PI / 2 + index * (Math.PI / 4);
    const normalized = {
      x: (centerPx.x + Math.cos(angle) * radiusPx) / dimensions.width,
      y: (centerPx.y + Math.sin(angle) * radiusPx) / dimensions.height,
    };
    await overlay.dispatchEvent("pointerdown", {
      pointerId: index + 1,
      pointerType: "touch",
      isPrimary: true,
      clientX: bounds!.x + bounds!.width * normalized.x,
      clientY: bounds!.y + bounds!.height * normalized.y,
    });
    await expect(
      page.getByText(new RegExp(`Coin-rim placement: ${index + 1} of 8`)),
    ).toBeVisible();
  }
}

function coinMarker(page: Page, label: string) {
  return page.getByRole("button", {
    name: new RegExp(`^${label} coin rim marker,`, "i"),
  });
}

async function moveCoinMarker(
  page: Page,
  label: string,
  key: "ArrowUp" | "ArrowDown" | "ArrowRight",
  shiftSteps: number,
  singleSteps: number,
) {
  const marker = coinMarker(page, label);
  for (let index = 0; index < shiftSteps; index += 1)
    await marker.press(`Shift+${key}`);
  for (let index = 0; index < singleSteps; index += 1) await marker.press(key);
}

async function markCurrentNail(
  page: Page,
  digit: string,
  index: number,
  widthFraction: number,
  last: boolean,
) {
  const overlay = page.locator(".annotation-overlay--nail");
  await overlay.scrollIntoViewIfNeeded();
  const bounds = await overlay.boundingBox();
  expect(bounds).not.toBeNull();
  const y = 0.32 + index * 0.1;
  const start = 0.43;
  const hasCoarsePointer = await page.evaluate(
    () => window.matchMedia("(pointer: coarse)").matches,
  );
  const placeMarker = async (x: number) => {
    const point = {
      x: bounds!.x + bounds!.width * x,
      y: bounds!.y + bounds!.height * y,
    };
    if (hasCoarsePointer) {
      await page.touchscreen.tap(point.x, point.y);
      return;
    }
    await page.mouse.click(point.x, point.y);
  };
  await placeMarker(start);
  await placeMarker(start + widthFraction);
  await page
    .getByRole("button", {
      name: last ? "Calculate this measurement" : `Save ${digit} and continue`,
    })
    .click();
}

async function completePhoto(
  page: Page,
  captureType: keyof typeof captureDigits,
  sample: 1 | 2,
  widthFraction = 0.23,
) {
  await expect(page).toHaveURL(
    new RegExp(`/capture/${captureType}/${sample}$`),
  );
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Mark coin rim" }).click();
  await expect(page).toHaveURL(new RegExp(`/guide/${captureType}/${sample}$`));
  await placeCoinRim(page);
  await page.getByRole("button", { name: "Confirm coin rim" }).click();

  const digits = captureDigits[captureType];
  for (const [index, digit] of digits.entries())
    await markCurrentNail(
      page,
      digit,
      index,
      widthFraction,
      index === digits.length - 1,
    );
}

test("landing, preparation, and capture explain the local guided flow", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "one clear sizing result per nail",
  );
  await expect(page.getByText("Photos stay in this browser")).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("link", { name: "Start guided sizing" }).click();
  await expect(page).toHaveURL(/\/prepare$/);
  await expect(page.getByText(/23\.0 mm wide/)).toBeVisible();
  await expect(page.getByRole("button", { name: "I’m ready" })).toBeDisabled();
  await page
    .getByRole("checkbox", { name: /I have the Third Series/i })
    .check();
  await expect(page.getByText(/Older Singapore 50-cent coins/)).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("button", { name: "I’m ready" }).click();
  await expect(page).toHaveURL(/\/capture\/left_fingers\/1$/);
  await expect(page.getByText(/measurement 1 of 2/i)).toBeVisible();
  await expect(page.getByText(/fill about one-third/i)).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
});

test("same-route annotation steps focus each updated instruction", async ({
  page,
}) => {
  await confirmCoinAndStart(page);
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Mark coin rim" }).click();
  await placeCoinRim(page);
  await page.getByRole("button", { name: "Confirm coin rim" }).click();

  await expect(
    page.getByRole("heading", { level: 1, name: "Mark the index nail." }),
  ).toBeFocused();
  await markCurrentNail(page, "index", 0, 0.23, false);
  await expect(
    page.getByRole("heading", { level: 1, name: "Mark the middle nail." }),
  ).toBeFocused();
});

test("locked coin markers do not block nail-edge taps", async ({ page }) => {
  await confirmCoinAndStart(page, "left_thumb");
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Mark coin rim" }).click();
  await placeCoinRim(page);
  await page.getByRole("button", { name: "Confirm coin rim" }).click();

  const overlay = page.locator(".annotation-overlay--nail");
  await overlay.scrollIntoViewIfNeeded();
  const bounds = await overlay.boundingBox();
  expect(bounds).not.toBeNull();
  const tapAt = async (x: number, y: number) => {
    const point = {
      x: bounds!.x + bounds!.width * x,
      y: bounds!.y + bounds!.height * y,
    };
    const coarse = await page.evaluate(
      () => window.matchMedia("(pointer: coarse)").matches,
    );
    if (coarse) await page.touchscreen.tap(point.x, point.y);
    else await page.mouse.click(point.x, point.y);
  };

  // These coordinates are directly over two locked coin-rim handles.
  await tapAt(0.23, 0.085);
  await tapAt(0.357, 0.125);

  await expect(
    page.getByRole("button", { name: /Left edge of thumb/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Right edge of thumb/i }),
  ).toBeVisible();
});

test("the exact same normalized photo cannot satisfy the independent repeat", async ({
  page,
}) => {
  await confirmCoinAndStart(page, "left_thumb");
  await uploadTestPhoto(page, 991);
  await page.getByRole("button", { name: "Mark coin rim" }).click();
  await placeCoinRim(page);
  await page.getByRole("button", { name: "Confirm coin rim" }).click();
  await markCurrentNail(page, "thumb", 0, 0.23, true);
  await page.getByRole("button", { name: "Take verification photo" }).click();

  await uploadTestPhoto(page, 991);
  await expect(
    page.getByText(/same image used for measurement 1/i),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Mark coin rim" }),
  ).toBeDisabled();
});

test("capture routes require the supported coin confirmation", async ({
  page,
}) => {
  await page.goto("/capture/left_thumb/1");
  await expect(page).toHaveURL(/\/prepare$/);
  await expect(
    page.getByRole("checkbox", { name: /I have the Third Series/i }),
  ).toBeVisible();
});

test("an oval-looking coin calibration is rejected before nail sizing", async ({
  page,
}) => {
  await confirmCoinAndStart(page, "left_thumb");
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Mark coin rim" }).click();

  await placeCoinRim(page);
  await moveCoinMarker(page, "Top", "ArrowDown", 2, 2);
  await moveCoinMarker(page, "Upper right", "ArrowDown", 1, 5);
  await moveCoinMarker(page, "Right", "ArrowRight", 0, 1);
  await moveCoinMarker(page, "Lower right", "ArrowUp", 1, 5);
  await moveCoinMarker(page, "Bottom", "ArrowUp", 2, 2);
  await moveCoinMarker(page, "Lower left", "ArrowUp", 1, 5);
  await moveCoinMarker(page, "Left", "ArrowRight", 0, 1);
  await moveCoinMarker(page, "Upper left", "ArrowDown", 1, 5);

  await page.getByRole("button", { name: "Confirm coin rim" }).click();
  await expect(page.getByText(/coin looks oval/i)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Trace the 50-cent coin rim",
  );
});

test("a high-resolution photo is rejected when the coin renders too small to mark", async ({
  page,
}) => {
  const dimensions = { width: 4096, height: 1000 };
  await confirmCoinAndStart(page, "left_thumb");
  await selectTestPhoto(page, ++syntheticPhotoSequence, dimensions);
  await page.getByRole("button", { name: "Mark coin rim" }).click();
  await placeCoinRim(page, dimensions);

  await page.getByRole("button", { name: "Confirm coin rim" }).click();
  await expect(page.getByText(/at least 120 screen pixels/i)).toBeVisible();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Trace the 50-cent coin rim",
  );
});

test("tapping untouched default markers cannot confirm a coin scale", async ({
  page,
}) => {
  await confirmCoinAndStart(page, "left_thumb");
  await selectTestPhoto(page);
  await page.getByRole("button", { name: "Mark coin rim" }).click();

  for (const label of [
    "Top",
    "Upper right",
    "Right",
    "Lower right",
    "Bottom",
    "Lower left",
    "Left",
    "Upper left",
  ])
    await coinMarker(page, label).click();

  await page.getByRole("button", { name: "Confirm coin rim" }).click();
  await expect(page.getByText(/Place every coin-rim marker/i)).toBeVisible();
  await expect(page.getByText(/Coin-rim placement: 0 of 8/i)).toBeVisible();
});

test("privacy notice promises and explains the no-upload boundary", async ({
  page,
}) => {
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "never leave this browser",
  );
  await expect(page.getByText(/does not send selected photos/)).toBeVisible();
  await expect(page.getByText(/does not train or run/)).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
});

test("unknown routes recover to the landing page", async ({ page }) => {
  await page.goto("/does-not-exist");
  await expect(page).toHaveURL(/\/$/);
  await expect(
    page.getByRole("link", { name: "Start guided sizing" }),
  ).toBeVisible();
});

test("unsupported local files receive an actionable replacement path", async ({
  page,
}) => {
  await confirmCoinAndStart(page, "left_thumb");
  await page.locator('input[type="file"]').setInputFiles({
    name: "capture.heic",
    mimeType: "image/heic",
    buffer: Buffer.from("not-a-browser-image"),
  });
  await expect(
    page.getByText(/Choose a JPEG, PNG, or WebP photo/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Mark coin rim" }),
  ).toBeDisabled();
  await expectNoSeriousAccessibilityViolations(page);
});

test("an inconsistent second photo blocks sizing and targets the verification retake", async ({
  page,
}) => {
  await confirmCoinAndStart(page, "left_thumb");
  await completePhoto(page, "left_thumb", 1, 0.2);
  await page.getByRole("button", { name: "Take verification photo" }).click();
  await completePhoto(page, "left_thumb", 2, 0.23);

  const repeatHeading = page.getByRole("heading", {
    level: 1,
    name: /need another check/i,
  });
  await expect(repeatHeading).toBeFocused();
  await expect(page.getByText(/Consistency check failed/)).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "First" }),
  ).toBeAttached();
  if ((page.viewportSize()?.width ?? 1280) <= 560)
    await expect(
      page.getByText("First measurement", { exact: true }).first(),
    ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
  await expect(
    page.getByRole("button", { name: "Accept and continue" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Retake verification photo" }).click();
  await expect(page).toHaveURL(/\/capture\/left_thumb\/2$/);
  await expect(page.getByText("First measurement complete")).toBeVisible();
});

test("eight local photos produce one clear result per nail without uploading image data", async ({
  context,
  page,
}) => {
  const requests: Array<{ method: string; url: string }> = [];
  page.on("request", (request) =>
    requests.push({ method: request.method(), url: request.url() }),
  );
  await context.addInitScript(() => {
    const clipboardState = window as typeof window & {
      __NAILSIZE_COPIED_TEXT__?: string;
    };
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: {
        writeText: async (value: string) => {
          clipboardState.__NAILSIZE_COPIED_TEXT__ = value;
        },
      },
    });
  });

  await confirmCoinAndStart(page);

  for (const captureType of Object.keys(captureDigits) as Array<
    keyof typeof captureDigits
  >) {
    const firstWidthFraction = captureType === "left_thumb" ? 0.29 : 0.23;
    const verificationWidthFraction =
      captureType === "left_thumb" ? 0.296 : 0.236;
    await completePhoto(page, captureType, 1, firstWidthFraction);
    await page.getByRole("button", { name: "Take verification photo" }).click();
    await completePhoto(page, captureType, 2, verificationWidthFraction);
    await expect(page.getByText("Consistency check passed")).toBeVisible();
    await page.getByRole("button", { name: "Accept and continue" }).click();
  }

  await expect(page).toHaveURL(/\/results$/);
  const mobile = (page.viewportSize()?.width ?? 1280) < 800;
  await expect(page.locator(".measurement-row:visible")).toHaveCount(
    mobile ? 5 : 10,
  );
  await expect(
    page
      .locator(".measurement-row:visible")
      .filter({ hasText: "Best-fit size 2" })
      .first(),
  ).toBeVisible();
  const visibleResultRows = page.locator(".measurement-row:visible");
  await expect(visibleResultRows).toHaveCount(mobile ? 5 : 10);
  for (let index = 0; index < (mobile ? 5 : 10); index += 1) {
    const row = visibleResultRows.nth(index);
    const bestFitCount = await row.getByText(/Best-fit size \d/).count();
    const artistReviewCount = await row
      .getByText("Outside default chart", { exact: true })
      .count();
    expect(bestFitCount + artistReviewCount).toBe(1);
    await expect(row).not.toContainText(/average-only|alternate size/i);
  }
  await expect(
    visibleResultRows.filter({ hasText: "Outside default chart" }),
  ).toHaveCount(1);
  await expect(
    page
      .locator(".measurement-row:visible")
      .filter({
        hasText: /Borderline measurement—confirm this nail physically/i,
      })
      .first(),
  ).toBeVisible();
  await expect(page.getByText(/Two-photo agreement passed/)).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);

  await page.getByRole("button", { name: "Copy results" }).click();
  await expect(
    page.getByText("Results copied. No photos were included."),
  ).toBeVisible();
  const copiedText = await page.evaluate(
    () =>
      (
        window as typeof window & {
          __NAILSIZE_COPIED_TEXT__?: string;
        }
      ).__NAILSIZE_COPIED_TEXT__,
  );
  expect(copiedText).toContain("guided projected-width results");
  expect(copiedText).toContain("best-fit size 2");
  expect(copiedText).toMatch(/Left thumb: .* — manual chart check/u);
  expect(copiedText).toContain("borderline measurement—confirm physically");
  expect(copiedText).not.toContain("boundary size 3");
  expect(copiedText).not.toMatch(/average-only|alternate size/i);
  expect(copiedText).toContain("do not measure nail curvature or guarantee");

  expect(requests.every((request) => request.method === "GET")).toBe(true);
  expect(
    requests.every(
      (request) => new URL(request.url).origin === "http://127.0.0.1:4173",
    ),
  ).toBe(true);

  await page
    .getByRole("button", { name: "Remeasure", exact: true })
    .first()
    .click();
  await expect(page).toHaveURL(/\/capture\/left_fingers\/1$/);
  await page.goto("/results");
  await expect(page).toHaveURL(/\/recover\/session$/);
});

test("starting over erases the in-memory result session", async ({ page }) => {
  await page.goto("/results");
  await expect(page).toHaveURL(/\/recover\/session$/);
  await page
    .getByRole("button", { name: "Start a new sizing session" })
    .click();
  await expect(page).toHaveURL(/\/$/);
});
