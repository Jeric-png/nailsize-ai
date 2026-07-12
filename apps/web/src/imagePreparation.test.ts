import { describe, expect, it } from "vitest";
import {
  calculateTargetSize,
  fingerprintImage,
  isKnownAnimated,
  prepareImage,
  readImageDimensions,
} from "./imagePreparation";

function pngChunk(type: string, data: number[] = []) {
  const bytes = new Uint8Array(12 + data.length);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, data.length);
  bytes.set(new TextEncoder().encode(type), 4);
  bytes.set(data, 8);
  return [...bytes];
}

function pngBytes(...chunks: number[][]) {
  return new Uint8Array([137, 80, 78, 71, 13, 10, 26, 10, ...chunks.flat()]);
}

function webpBytes(type: string) {
  const payload = new Uint8Array(8);
  payload.set(new TextEncoder().encode(type));
  const view = new DataView(payload.buffer);
  view.setUint32(4, 0, true);
  return new Uint8Array([
    ...new TextEncoder().encode("RIFF"),
    4,
    0,
    0,
    0,
    ...new TextEncoder().encode("WEBP"),
    ...payload,
  ]);
}

function jpegBytes(width: number, height: number) {
  return new Uint8Array([
    0xff,
    0xd8,
    0xff,
    0xc0,
    0x00,
    0x11,
    0x08,
    (height >> 8) & 0xff,
    height & 0xff,
    (width >> 8) & 0xff,
    width & 0xff,
    0x03,
    0x01,
    0x11,
    0x00,
    0x02,
    0x11,
    0x00,
    0x03,
    0x11,
    0x00,
    0xff,
    0xd9,
  ]);
}

describe("fingerprintImage", () => {
  it("gives identical normalized bytes the same local fingerprint", async () => {
    const first = new Blob(["same pixels"], { type: "image/jpeg" });
    const second = new Blob(["same pixels"], { type: "image/jpeg" });
    const different = new Blob(["different pixels"], { type: "image/jpeg" });

    await expect(fingerprintImage(first)).resolves.toMatch(/^[a-f0-9]{64}$/);
    await expect(fingerprintImage(second)).resolves.toBe(
      await fingerprintImage(first),
    );
    await expect(fingerprintImage(different)).resolves.not.toBe(
      await fingerprintImage(first),
    );
  });
});

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

    const roundingEdge = calculateTargetSize(6665, 6670);
    expect(roundingEdge.width * roundingEdge.height).toBeLessThanOrEqual(
      16_000_000,
    );
  });

  it("rejects invalid dimensions", () => {
    expect(() => calculateTargetSize(0, 100)).toThrow(RangeError);
    expect(() => calculateTargetSize(Number.NaN, 100)).toThrow(RangeError);
  });
});

describe("isKnownAnimated", () => {
  it("detects APNG and animated WebP markers before browser rewriting", () => {
    expect(isKnownAnimated(pngBytes(pngChunk("acTL")), "image/png")).toBe(true);
    expect(isKnownAnimated(webpBytes("ANIM"), "image/webp")).toBe(true);
  });

  it("does not classify marker text inside static payloads as animation", () => {
    expect(
      isKnownAnimated(
        pngBytes(pngChunk("tEXt", [...new TextEncoder().encode("acTL")])),
        "image/png",
      ),
    ).toBe(false);
    expect(
      isKnownAnimated(new TextEncoder().encode("ANIM ANMF"), "image/jpeg"),
    ).toBe(false);
  });
});

describe("readImageDimensions", () => {
  it("reads JPEG dimensions without decoding the full bitmap", () => {
    expect(readImageDimensions(jpegBytes(8000, 6000), "image/jpeg")).toEqual({
      width: 8000,
      height: 6000,
    });
  });
});

describe("prepareImage", () => {
  it("rejects unsupported files instead of retaining an unbounded fallback preview", async () => {
    const file = new File(["heic"], "capture.heic", { type: "image/heic" });

    await expect(prepareImage(file)).rejects.toThrow(
      /cannot be prepared safely/i,
    );
  });

  it("fails closed when the browser cannot normalize a supported image", async () => {
    const file = new File([jpegBytes(600, 800)], "capture.jpg", {
      type: "image/jpeg",
    });

    await expect(prepareImage(file)).rejects.toThrow(
      /cannot safely normalize/i,
    );
  });

  it("rejects a high-megapixel source before allocating a decoded bitmap", async () => {
    const file = new File([jpegBytes(8000, 6000)], "capture.jpg", {
      type: "image/jpeg",
    });

    await expect(prepareImage(file)).rejects.toThrow(/20 megapixels/i);
  });
});
