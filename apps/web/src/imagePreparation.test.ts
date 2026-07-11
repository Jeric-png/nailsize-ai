import { describe, expect, it } from "vitest";
import {
  calculateTargetSize,
  isKnownAnimated,
  prepareImage,
} from "./imagePreparation";

describe("calculateTargetSize", () => {
  it("preserves an image already inside the upload envelope", () => {
    expect(calculateTargetSize(1600, 1200)).toEqual({
      width: 1600,
      height: 1200,
    });
  });

  it("downscales a wide image without changing its aspect ratio", () => {
    const target = calculateTargetSize(8000, 4000);
    expect(target).toEqual({ width: 4096, height: 2048 });
    expect(target.width / target.height).toBe(2);
  });

  it("keeps high-megapixel images below the client pixel budget", () => {
    const target = calculateTargetSize(6000, 4000);
    expect(target.width * target.height).toBeLessThanOrEqual(16_000_000);
    expect(target.width / target.height).toBeCloseTo(1.5, 3);
  });

  it("rejects invalid dimensions", () => {
    expect(() => calculateTargetSize(0, 100)).toThrow(RangeError);
    expect(() => calculateTargetSize(Number.NaN, 100)).toThrow(RangeError);
  });
});

describe("isKnownAnimated", () => {
  it("detects APNG and animated WebP markers before browser rewriting", () => {
    expect(
      isKnownAnimated(new TextEncoder().encode("png-acTL-data"), "image/png"),
    ).toBe(true);
    expect(
      isKnownAnimated(new TextEncoder().encode("webp-ANIM-data"), "image/webp"),
    ).toBe(true);
  });

  it("does not classify ordinary static bytes as animated", () => {
    expect(
      isKnownAnimated(new TextEncoder().encode("static-image"), "image/png"),
    ).toBe(false);
    expect(
      isKnownAnimated(new TextEncoder().encode("static-image"), "image/jpeg"),
    ).toBe(false);
  });
});

describe("prepareImage", () => {
  it("preserves HEIC for the server when the browser cannot safely normalize it", async () => {
    const file = new File(["heic"], "capture.heic", { type: "image/heic" });

    await expect(prepareImage(file)).resolves.toEqual({
      file,
      normalizedInBrowser: false,
    });
  });
});
