const MAX_EDGE = 4096;
const MAX_PIXELS = 16_000_000;
const MAX_DECODE_PIXELS = 20_000_000;
const MAX_SOURCE_EDGE = 8192;
const MAX_SOURCE_BYTES = 12 * 1024 * 1024;
const BROWSER_DECODABLE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

export interface PreparedImage {
  file: File;
  width: number;
  height: number;
}

export interface ImageDimensions {
  width: number;
  height: number;
}

export async function fingerprintImage(file: Blob): Promise<string> {
  if (!globalThis.crypto?.subtle)
    throw new Error("This browser cannot compare local verification photos.");
  const digest = await globalThis.crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export function calculateTargetSize(width: number, height: number) {
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  )
    throw new RangeError("Image dimensions must be positive finite numbers");

  const edgeScale = Math.min(1, MAX_EDGE / Math.max(width, height));
  const pixelScale = Math.min(1, Math.sqrt(MAX_PIXELS / (width * height)));
  const scale = Math.min(edgeScale, pixelScale);
  return {
    width: Math.max(1, Math.floor(width * scale)),
    height: Math.max(1, Math.floor(height * scale)),
  };
}

function ascii(bytes: Uint8Array, offset: number, length: number) {
  return String.fromCharCode(...bytes.subarray(offset, offset + length));
}

function pngChunks(bytes: Uint8Array) {
  const chunks: Array<{ type: string; dataOffset: number; length: number }> =
    [];
  if (
    bytes.length < 8 ||
    ![137, 80, 78, 71, 13, 10, 26, 10].every(
      (value, index) => bytes[index] === value,
    )
  )
    return chunks;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 8;
  while (offset + 12 <= bytes.length) {
    const length = view.getUint32(offset);
    const end = offset + 12 + length;
    if (end > bytes.length) return [];
    const type = ascii(bytes, offset + 4, 4);
    chunks.push({ type, dataOffset: offset + 8, length });
    offset = end;
    if (type === "IEND") break;
  }
  return chunks;
}

function webpChunks(bytes: Uint8Array) {
  const chunks: Array<{ type: string; dataOffset: number; length: number }> =
    [];
  if (
    bytes.length < 12 ||
    ascii(bytes, 0, 4) !== "RIFF" ||
    ascii(bytes, 8, 4) !== "WEBP"
  )
    return chunks;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let offset = 12;
  while (offset + 8 <= bytes.length) {
    const length = view.getUint32(offset + 4, true);
    const end = offset + 8 + length;
    if (end > bytes.length) return [];
    chunks.push({
      type: ascii(bytes, offset, 4),
      dataOffset: offset + 8,
      length,
    });
    offset = end + (length % 2);
  }
  return chunks;
}

export function isKnownAnimated(bytes: Uint8Array, mimeType: string) {
  if (mimeType === "image/png")
    return pngChunks(bytes).some((chunk) => chunk.type === "acTL");
  if (mimeType === "image/webp")
    return webpChunks(bytes).some(
      (chunk) => chunk.type === "ANIM" || chunk.type === "ANMF",
    );
  return false;
}

export function readImageDimensions(
  bytes: Uint8Array,
  mimeType: string,
): ImageDimensions | null {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (mimeType === "image/png") {
    const header = pngChunks(bytes).find((chunk) => chunk.type === "IHDR");
    if (!header || header.length !== 13) return null;
    const width = view.getUint32(header.dataOffset);
    const height = view.getUint32(header.dataOffset + 4);
    return validDimensions(width, height);
  }
  if (mimeType === "image/webp") {
    for (const chunk of webpChunks(bytes)) {
      const offset = chunk.dataOffset;
      if (chunk.type === "VP8X" && chunk.length >= 10) {
        const width = 1 + readUint24LE(bytes, offset + 4);
        const height = 1 + readUint24LE(bytes, offset + 7);
        return validDimensions(width, height);
      }
      if (
        chunk.type === "VP8L" &&
        chunk.length >= 5 &&
        bytes[offset] === 0x2f
      ) {
        const width = 1 + bytes[offset + 1] + ((bytes[offset + 2] & 0x3f) << 8);
        const height =
          1 +
          ((bytes[offset + 2] & 0xc0) >> 6) +
          (bytes[offset + 3] << 2) +
          ((bytes[offset + 4] & 0x0f) << 10);
        return validDimensions(width, height);
      }
      if (
        chunk.type === "VP8 " &&
        chunk.length >= 10 &&
        bytes[offset + 3] === 0x9d &&
        bytes[offset + 4] === 0x01 &&
        bytes[offset + 5] === 0x2a
      ) {
        const width = view.getUint16(offset + 6, true) & 0x3fff;
        const height = view.getUint16(offset + 8, true) & 0x3fff;
        return validDimensions(width, height);
      }
    }
    return null;
  }
  if (mimeType === "image/jpeg") {
    if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
    let offset = 2;
    while (offset + 3 < bytes.length) {
      while (offset < bytes.length && bytes[offset] !== 0xff) offset += 1;
      while (offset < bytes.length && bytes[offset] === 0xff) offset += 1;
      if (offset >= bytes.length) break;
      const marker = bytes[offset++];
      if (
        marker === 0xd8 ||
        marker === 0xd9 ||
        marker === 0x01 ||
        (marker >= 0xd0 && marker <= 0xd7)
      )
        continue;
      if (offset + 2 > bytes.length) return null;
      const length = view.getUint16(offset);
      if (length < 2 || offset + length > bytes.length) return null;
      if (isStartOfFrame(marker) && length >= 7) {
        const height = view.getUint16(offset + 3);
        const width = view.getUint16(offset + 5);
        return validDimensions(width, height);
      }
      offset += length;
    }
  }
  return null;
}

function readUint24LE(bytes: Uint8Array, offset: number) {
  return bytes[offset] + (bytes[offset + 1] << 8) + (bytes[offset + 2] << 16);
}

function validDimensions(width: number, height: number) {
  return width > 0 && height > 0 ? { width, height } : null;
}

function isStartOfFrame(marker: number) {
  return [
    0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce,
    0xcf,
  ].includes(marker);
}

function canvasBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", 0.9),
  );
}

export async function prepareImage(file: File): Promise<PreparedImage> {
  if (file.size > MAX_SOURCE_BYTES)
    throw new RangeError("Image exceeds the local 12 MB preparation limit.");
  if (!BROWSER_DECODABLE_TYPES.has(file.type))
    throw new TypeError(
      "Image type cannot be prepared safely in this browser.",
    );
  const sourceBytes = new Uint8Array(await file.arrayBuffer());
  const sourceDimensions = readImageDimensions(sourceBytes, file.type);
  if (!sourceDimensions)
    throw new TypeError("The image header is invalid or unsupported.");
  if (
    sourceDimensions.width * sourceDimensions.height > MAX_DECODE_PIXELS ||
    Math.max(sourceDimensions.width, sourceDimensions.height) > MAX_SOURCE_EDGE
  )
    throw new RangeError(
      "Choose a photo no larger than 20 megapixels or 8192 pixels on either side so it can be prepared safely on this device.",
    );
  if (
    (file.type === "image/png" || file.type === "image/webp") &&
    isKnownAnimated(sourceBytes, file.type)
  )
    throw new TypeError("Animated images are not supported.");
  if (typeof createImageBitmap !== "function")
    throw new Error("This browser cannot safely normalize the selected image.");

  let bitmap: ImageBitmap | undefined;
  try {
    bitmap = await createImageBitmap(file, {
      imageOrientation: "from-image",
      premultiplyAlpha: "default",
      colorSpaceConversion: "default",
    });
    const target = calculateTargetSize(bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = target.width;
    canvas.height = target.height;
    const context = canvas.getContext("2d", { alpha: false });
    if (!context) throw new Error("Browser canvas preparation is unavailable.");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, target.width, target.height);
    context.drawImage(bitmap, 0, 0, target.width, target.height);
    const blob = await canvasBlob(canvas);
    if (!blob || blob.type !== "image/jpeg")
      throw new Error("Browser image re-encoding failed.");

    const baseName = file.name.replace(/\.[^.]+$/, "") || "nail-capture";
    return {
      file: new File([blob], `${baseName}.jpg`, {
        type: "image/jpeg",
        lastModified: file.lastModified,
      }),
      width: target.width,
      height: target.height,
    };
  } catch (error) {
    throw new Error(
      "The image could not be normalized safely in this browser.",
      {
        cause: error,
      },
    );
  } finally {
    bitmap?.close();
  }
}
