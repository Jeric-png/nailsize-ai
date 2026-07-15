import { afterEach, describe, expect, it, vi } from "vitest";
import {
  calculateTargetSize,
  decodeBitmap,
  detectImageMimeType,
  fingerprintImage,
  isKnownAnimated,
  prepareImage,
  readImageDimensions,
} from "./imagePreparation";

const { heicToMock } = vi.hoisted(() => ({ heicToMock: vi.fn() }));

vi.mock("heic-to/csp", () => ({ heicTo: heicToMock }));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  heicToMock.mockReset();
});

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

function webpChunkFloodBytes() {
  const validVp8x = new Uint8Array(18);
  validVp8x.set(new TextEncoder().encode("VP8X"));
  new DataView(validVp8x.buffer).setUint32(4, 10, true);
  const emptyChunk = new Uint8Array(8);
  emptyChunk.set(new TextEncoder().encode("EXIF"));
  const bytes = new Uint8Array(
    12 + validVp8x.length + 4097 * emptyChunk.length,
  );
  bytes.set(new TextEncoder().encode("RIFF"));
  new DataView(bytes.buffer).setUint32(4, bytes.length - 8, true);
  bytes.set(new TextEncoder().encode("WEBP"), 8);
  bytes.set(validVp8x, 12);
  for (
    let offset = 12 + validVp8x.length;
    offset < bytes.length;
    offset += emptyChunk.length
  )
    bytes.set(emptyChunk, offset);
  return bytes;
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

function uint32(value: number) {
  return [
    (value >>> 24) & 0xff,
    (value >>> 16) & 0xff,
    (value >>> 8) & 0xff,
    value & 0xff,
  ];
}

function isoImageBytes(brand: string, width: number, height: number) {
  const text = (value: string) => [...new TextEncoder().encode(value)];
  const box = (type: string, payload: number[]) => [
    ...uint32(payload.length + 8),
    ...text(type),
    ...payload,
  ];
  const ftyp = [
    ...uint32(20),
    ...text("ftyp"),
    ...text(brand),
    0,
    0,
    0,
    0,
    ...text(brand),
  ];
  const ispe = box("ispe", [0, 0, 0, 0, ...uint32(width), ...uint32(height)]);
  const ipco = box("ipco", ispe);
  const iprp = box("iprp", ipco);
  const meta = box("meta", [0, 0, 0, 0, ...iprp]);
  return new Uint8Array([...ftyp, ...meta]);
}

function oversizedFtypBytes(brand: string) {
  const bytes = new Uint8Array(4096);
  const view = new DataView(bytes.buffer);
  view.setUint32(0, bytes.length);
  bytes.set(new TextEncoder().encode("ftyp"), 4);
  for (let offset = 8; offset < bytes.length; offset += 4)
    bytes.set(new TextEncoder().encode(brand), offset);
  return bytes;
}

function pngChunkFloodBytes() {
  const ihdr = pngChunk("IHDR", [0, 0, 0, 1, 0, 0, 0, 1, 8, 2, 0, 0, 0]);
  const emptyChunk = pngChunk("tEXt");
  const bytes = new Uint8Array(8 + ihdr.length + 4097 * emptyChunk.length);
  bytes.set([137, 80, 78, 71, 13, 10, 26, 10]);
  bytes.set(ihdr, 8);
  for (
    let offset = 8 + ihdr.length;
    offset < bytes.length;
    offset += emptyChunk.length
  )
    bytes.set(emptyChunk, offset);
  return bytes;
}

function gifFrameBytes(width: number, height: number) {
  return [
    0x2c,
    0,
    0,
    0,
    0,
    width & 0xff,
    (width >>> 8) & 0xff,
    height & 0xff,
    (height >>> 8) & 0xff,
    0,
    2,
    2,
    0x4c,
    0x01,
    0,
  ];
}

function gifBytes(
  logicalWidth: number,
  logicalHeight: number,
  frameWidth = logicalWidth,
  frameHeight = logicalHeight,
) {
  return new Uint8Array([
    ...new TextEncoder().encode("GIF89a"),
    logicalWidth & 0xff,
    (logicalWidth >>> 8) & 0xff,
    logicalHeight & 0xff,
    (logicalHeight >>> 8) & 0xff,
    0,
    0,
    0,
    ...gifFrameBytes(frameWidth, frameHeight),
    0x3b,
  ]);
}

function animatedGifBytes() {
  const header = gifBytes(1, 1).subarray(0, 13);
  const frame = gifFrameBytes(1, 1);
  return new Uint8Array([...header, ...frame, ...frame, 0x3b]);
}

function bmpBytes(width: number, height: number) {
  const bytes = new Uint8Array(54);
  const view = new DataView(bytes.buffer);
  bytes.set(new TextEncoder().encode("BM"));
  view.setUint32(14, 40, true);
  view.setInt32(18, width, true);
  view.setInt32(22, height, true);
  return bytes;
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
    expect(isKnownAnimated(animatedGifBytes(), "image/gif")).toBe(true);
    expect(isKnownAnimated(isoImageBytes("avis", 64, 48), "image/avif")).toBe(
      true,
    );
    expect(isKnownAnimated(isoImageBytes("hevm", 64, 48), "image/heic")).toBe(
      true,
    );
    expect(isKnownAnimated(isoImageBytes("hevs", 64, 48), "image/heic")).toBe(
      true,
    );
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

  it("reads GIF, BMP, AVIF, and HEIC dimensions before full decoding", () => {
    expect(readImageDimensions(gifBytes(640, 480), "image/gif")).toEqual({
      width: 640,
      height: 480,
    });
    expect(readImageDimensions(bmpBytes(800, 600), "image/bmp")).toEqual({
      width: 800,
      height: 600,
    });
    expect(
      readImageDimensions(isoImageBytes("avif", 1200, 900), "image/avif"),
    ).toEqual({ width: 1200, height: 900 });
    expect(
      readImageDimensions(isoImageBytes("heic", 4032, 3024), "image/heic"),
    ).toEqual({ width: 4032, height: 3024 });
  });

  it("does not trust ispe-like bytes hidden inside an ISO media payload", () => {
    const text = (value: string) => [...new TextEncoder().encode(value)];
    const payload = [
      ...uint32(20),
      ...text("ispe"),
      0,
      0,
      0,
      0,
      ...uint32(640),
      ...uint32(480),
    ];
    const bytes = new Uint8Array([
      ...uint32(20),
      ...text("ftyp"),
      ...text("avif"),
      0,
      0,
      0,
      0,
      ...text("avif"),
      ...uint32(payload.length + 8),
      ...text("mdat"),
      ...payload,
    ]);

    expect(readImageDimensions(bytes, "image/avif")).toBeNull();
  });
});

describe("detectImageMimeType", () => {
  it("recognizes common formats by content instead of unreliable file MIME", () => {
    expect(detectImageMimeType(jpegBytes(640, 480))).toBe("image/jpeg");
    expect(detectImageMimeType(pngBytes(pngChunk("IEND")))).toBe("image/png");
    expect(detectImageMimeType(webpBytes("VP8X"))).toBe("image/webp");
    expect(detectImageMimeType(gifBytes(640, 480))).toBe("image/gif");
    expect(detectImageMimeType(bmpBytes(640, 480))).toBe("image/bmp");
    expect(detectImageMimeType(isoImageBytes("avif", 640, 480))).toBe(
      "image/avif",
    );
    expect(detectImageMimeType(isoImageBytes("heic", 640, 480))).toBe(
      "image/heic",
    );
  });

  it("fails closed on an unbounded ISO compatible-brand table", () => {
    expect(detectImageMimeType(oversizedFtypBytes("heic"))).toBeNull();
  });
});

describe("decodeBitmap", () => {
  it("uses native HEIC decoding without loading the fallback when available", async () => {
    const bitmap = {
      width: 64,
      height: 48,
      close: vi.fn(),
    } as unknown as ImageBitmap;
    const nativeDecode = vi.fn().mockResolvedValue(bitmap);
    vi.stubGlobal("createImageBitmap", nativeDecode);

    const file = new File([isoImageBytes("heic", 64, 48)], "capture.heic", {
      type: "image/heic",
    });

    await expect(decodeBitmap(file, "image/heic")).resolves.toBe(bitmap);
    expect(nativeDecode).toHaveBeenCalledOnce();
    expect(heicToMock).not.toHaveBeenCalled();
  });

  it("loads the local HEIC fallback only after native decoding fails", async () => {
    const bitmap = {
      width: 64,
      height: 48,
      close: vi.fn(),
    } as unknown as ImageBitmap;
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn().mockRejectedValue(new Error("native HEIC unavailable")),
    );
    heicToMock.mockResolvedValue(bitmap);
    const file = new File([isoImageBytes("heic", 64, 48)], "capture.heic", {
      type: "",
    });

    await expect(decodeBitmap(file, "image/heic")).resolves.toBe(bitmap);
    expect(heicToMock).toHaveBeenCalledWith(
      expect.objectContaining({ blob: expect.any(File), type: "bitmap" }),
    );
  });
});

describe("prepareImage", () => {
  it("rejects renamed or malformed files instead of trusting their MIME", async () => {
    const file = new File(["not-an-image"], "capture.jpg", {
      type: "image/jpeg",
    });

    await expect(prepareImage(file)).rejects.toThrow(
      /JPEG, PNG, WebP, HEIC\/HEIF, AVIF, GIF, or BMP/i,
    );
  });

  it("accepts HEIC content and reaches the local browser decoder", async () => {
    const file = new File([isoImageBytes("heic", 4032, 3024)], "capture.HEIC", {
      type: "",
    });

    await expect(prepareImage(file)).rejects.toThrow(
      /cannot safely normalize/i,
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

  it("rejects an oversized source before reading or decoding it", async () => {
    const decode = vi.fn();
    vi.stubGlobal("createImageBitmap", decode);
    const file = new File(
      [new Uint8Array(12 * 1024 * 1024 + 1)],
      "capture.jpg",
      { type: "image/jpeg" },
    );

    await expect(prepareImage(file)).rejects.toThrow(/12 MB/i);
    expect(decode).not.toHaveBeenCalled();
  });

  it("rejects an oversized ISO brand table before image decoding", async () => {
    const decode = vi.fn();
    vi.stubGlobal("createImageBitmap", decode);
    const file = new File([oversizedFtypBytes("heic")], "capture.heic", {
      type: "image/heic",
    });

    await expect(prepareImage(file)).rejects.toThrow(/Choose a JPEG/i);
    expect(decode).not.toHaveBeenCalled();
  });

  it.each([
    ["PNG", pngChunkFloodBytes(), "capture.png", "image/png"],
    ["WebP", webpChunkFloodBytes(), "capture.webp", "image/webp"],
  ])(
    "rejects a %s chunk flood before image decoding",
    async (_label, bytes, name, type) => {
      const decode = vi.fn();
      vi.stubGlobal("createImageBitmap", decode);
      const file = new File([bytes], name, { type });

      await expect(prepareImage(file)).rejects.toThrow(/header is invalid/i);
      expect(decode).not.toHaveBeenCalled();
    },
  );

  it("rejects GIF frame dimensions that exceed its logical screen", async () => {
    const decode = vi.fn();
    vi.stubGlobal("createImageBitmap", decode);
    const file = new File([gifBytes(1, 1, 9000, 1)], "capture.gif", {
      type: "image/gif",
    });

    await expect(prepareImage(file)).rejects.toThrow(/8192 pixels/i);
    expect(decode).not.toHaveBeenCalled();
  });

  it("rejects animated GIFs before allocating a decoded bitmap", async () => {
    const decode = vi.fn();
    vi.stubGlobal("createImageBitmap", decode);
    const file = new File([animatedGifBytes()], "capture.gif", {
      type: "image/gif",
    });

    await expect(prepareImage(file)).rejects.toThrow(/Animated images/i);
    expect(decode).not.toHaveBeenCalled();
  });

  it("closes the decoded bitmap and releases the canvas after normalization", async () => {
    const close = vi.fn();
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn().mockResolvedValue({ width: 640, height: 480, close }),
    );
    const context = {
      drawImage: vi.fn(),
      fillRect: vi.fn(),
      fillStyle: "",
    };
    const canvas = {
      width: 1,
      height: 1,
      getContext: vi.fn(() => context),
      toBlob: vi.fn((callback: BlobCallback) =>
        callback(new Blob(["normalized"], { type: "image/jpeg" })),
      ),
    };
    vi.stubGlobal("document", { createElement: vi.fn(() => canvas) });
    const file = new File([jpegBytes(640, 480)], "capture.jpg", {
      type: "application/octet-stream",
    });

    const prepared = await prepareImage(file);

    expect(prepared).toMatchObject({ width: 640, height: 480 });
    expect(prepared.file).toMatchObject({
      name: "capture.jpg",
      type: "image/jpeg",
    });
    expect(close).toHaveBeenCalledOnce();
    expect(canvas).toMatchObject({ width: 0, height: 0 });
  });

  it("closes a decoded bitmap whose dimensions disagree with the safe header", async () => {
    const close = vi.fn();
    vi.stubGlobal(
      "createImageBitmap",
      vi.fn().mockResolvedValue({ width: 9000, height: 1, close }),
    );
    const file = new File([jpegBytes(640, 480)], "capture.jpg", {
      type: "image/jpeg",
    });

    await expect(prepareImage(file)).rejects.toThrow(/8192 pixels/i);
    expect(close).toHaveBeenCalledOnce();
  });

  it("preflights oversized ISO-BMFF images before native or fallback decode", async () => {
    const file = new File(
      [isoImageBytes("heic", 10_000, 10_000)],
      "capture.heic",
      { type: "image/heic" },
    );

    await expect(prepareImage(file)).rejects.toThrow(/20 megapixels/i);
  });
});
