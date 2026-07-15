const MAX_EDGE = 4096;
const MAX_PIXELS = 16_000_000;
const MAX_DECODE_PIXELS = 20_000_000;
const MAX_SOURCE_EDGE = 8192;
const MAX_SOURCE_BYTES = 12 * 1024 * 1024;
const MAX_ISO_FTYP_BYTES = 256;
const MAX_CONTAINER_ENTRIES = 4096;

export const IMAGE_FILE_ACCEPT =
  "image/*,.jpg,.jpeg,.jfif,.png,.webp,.heic,.heif,.avif,.gif,.bmp,.dib";
export const COMMON_IMAGE_FORMATS =
  "JPEG, PNG, WebP, HEIC/HEIF, AVIF, GIF, or BMP";

export type SupportedImageMime =
  | "image/jpeg"
  | "image/png"
  | "image/webp"
  | "image/heic"
  | "image/avif"
  | "image/gif"
  | "image/bmp";

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

function hasBytes(bytes: Uint8Array, expected: readonly number[]) {
  return (
    bytes.length >= expected.length &&
    expected.every((value, index) => bytes[index] === value)
  );
}

function isoBmffBrands(bytes: Uint8Array) {
  if (bytes.length < 16 || ascii(bytes, 4, 4) !== "ftyp") return [];
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const declaredSize = view.getUint32(0);
  if (
    declaredSize < 16 ||
    declaredSize > bytes.length ||
    declaredSize > MAX_ISO_FTYP_BYTES ||
    declaredSize % 4 !== 0
  )
    return [];
  const end = declaredSize;
  const brands = [ascii(bytes, 8, 4)];
  for (let offset = 16; offset + 4 <= end; offset += 4)
    brands.push(ascii(bytes, offset, 4));
  return brands;
}

export function detectImageMimeType(
  bytes: Uint8Array,
): SupportedImageMime | null {
  if (hasBytes(bytes, [0xff, 0xd8])) return "image/jpeg";
  if (hasBytes(bytes, [137, 80, 78, 71, 13, 10, 26, 10])) return "image/png";
  if (
    bytes.length >= 12 &&
    ascii(bytes, 0, 4) === "RIFF" &&
    ascii(bytes, 8, 4) === "WEBP"
  )
    return "image/webp";
  if (
    bytes.length >= 10 &&
    (ascii(bytes, 0, 6) === "GIF87a" || ascii(bytes, 0, 6) === "GIF89a")
  )
    return "image/gif";
  if (bytes.length >= 26 && ascii(bytes, 0, 2) === "BM") return "image/bmp";

  const brands = isoBmffBrands(bytes);
  if (brands.some((brand) => brand === "avif" || brand === "avis"))
    return "image/avif";
  if (
    brands.some((brand) =>
      [
        "heic",
        "heix",
        "hevc",
        "hevx",
        "heim",
        "heis",
        "hevm",
        "hevs",
        "mif1",
        "msf1",
      ].includes(brand),
    )
  )
    return "image/heic";
  return null;
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
  let entries = 0;
  while (offset + 12 <= bytes.length) {
    if (entries >= MAX_CONTAINER_ENTRIES) return [];
    entries += 1;
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
  let entries = 0;
  while (offset + 8 <= bytes.length) {
    if (entries >= MAX_CONTAINER_ENTRIES) return [];
    entries += 1;
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

interface GifInfo extends ImageDimensions {
  frames: number;
}

function readGifInfo(bytes: Uint8Array): GifInfo | null {
  if (
    bytes.length < 13 ||
    (ascii(bytes, 0, 6) !== "GIF87a" && ascii(bytes, 0, 6) !== "GIF89a")
  )
    return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const logicalWidth = view.getUint16(6, true);
  const logicalHeight = view.getUint16(8, true);
  if (!validDimensions(logicalWidth, logicalHeight)) return null;
  let offset = 13;
  const globalColorTable = (bytes[10] & 0x80) !== 0;
  if (globalColorTable) offset += 3 * 2 ** ((bytes[10] & 0x07) + 1);
  if (offset > bytes.length) return null;
  let frames = 0;
  let width = logicalWidth;
  let height = logicalHeight;
  let entries = 0;
  while (offset < bytes.length) {
    if (entries >= MAX_CONTAINER_ENTRIES) return null;
    entries += 1;
    const marker = bytes[offset];
    if (marker === 0x3b) return { width, height, frames };
    if (marker === 0x21) {
      if (offset + 2 > bytes.length) return null;
      const next = skipGifSubBlocks(bytes, offset + 2);
      if (next === null) return null;
      offset = next;
      continue;
    }
    if (marker === 0x2c) {
      if (offset + 10 > bytes.length) return null;
      const left = view.getUint16(offset + 1, true);
      const top = view.getUint16(offset + 3, true);
      const frameWidth = view.getUint16(offset + 5, true);
      const frameHeight = view.getUint16(offset + 7, true);
      if (!validDimensions(frameWidth, frameHeight)) return null;
      width = Math.max(width, left + frameWidth);
      height = Math.max(height, top + frameHeight);
      frames += 1;
      const localTableFlags = bytes[offset + 9];
      offset += 10;
      if ((localTableFlags & 0x80) !== 0)
        offset += 3 * 2 ** ((localTableFlags & 0x07) + 1);
      if (offset >= bytes.length) return null;
      const next = skipGifSubBlocks(bytes, offset + 1);
      if (next === null) return null;
      offset = next;
      continue;
    }
    return null;
  }
  return null;
}

function skipGifSubBlocks(bytes: Uint8Array, start: number) {
  let offset = start;
  while (offset < bytes.length) {
    const length = bytes[offset];
    offset += 1;
    if (length === 0) return offset;
    if (offset + length > bytes.length) return null;
    offset += length;
  }
  return null;
}

export function isKnownAnimated(bytes: Uint8Array, mimeType: string) {
  if (mimeType === "image/png")
    return pngChunks(bytes).some((chunk) => chunk.type === "acTL");
  if (mimeType === "image/webp")
    return webpChunks(bytes).some(
      (chunk) => chunk.type === "ANIM" || chunk.type === "ANMF",
    );
  if (mimeType === "image/gif") return (readGifInfo(bytes)?.frames ?? 0) > 1;
  if (mimeType === "image/avif") return isoBmffBrands(bytes).includes("avis");
  if (mimeType === "image/heic")
    return isoBmffBrands(bytes).some(
      (brand) =>
        brand === "msf1" ||
        brand === "hevc" ||
        brand === "hevx" ||
        brand === "hevm" ||
        brand === "hevs",
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
  if (mimeType === "image/gif") {
    const info = readGifInfo(bytes);
    return info ? { width: info.width, height: info.height } : null;
  }
  if (mimeType === "image/bmp") {
    if (bytes.length < 26 || ascii(bytes, 0, 2) !== "BM") return null;
    const dibSize = view.getUint32(14, true);
    if (dibSize === 12)
      return validDimensions(
        view.getUint16(18, true),
        view.getUint16(20, true),
      );
    if (dibSize >= 40 && bytes.length >= 26)
      return validDimensions(
        Math.abs(view.getInt32(18, true)),
        Math.abs(view.getInt32(22, true)),
      );
    return null;
  }
  if (mimeType === "image/avif" || mimeType === "image/heic")
    return readIsoBmffDimensions(bytes);
  return null;
}

function readIsoBmffDimensions(bytes: Uint8Array): ImageDimensions | null {
  if (isoBmffBrands(bytes).length === 0) return null;
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const state: {
    largest: ImageDimensions | null;
    boxes: number;
    invalid: boolean;
  } = {
    largest: null,
    boxes: 0,
    invalid: false,
  };
  walkIsoBmffBoxes(view, 0, bytes.length, 0, state);
  return state.invalid ? null : state.largest;
}

const ISO_CONTAINER_BOXES = new Set(["meta", "iprp", "ipco"]);

function readFourCc(view: DataView, offset: number) {
  return String.fromCharCode(
    view.getUint8(offset),
    view.getUint8(offset + 1),
    view.getUint8(offset + 2),
    view.getUint8(offset + 3),
  );
}

function walkIsoBmffBoxes(
  view: DataView,
  start: number,
  end: number,
  depth: number,
  state: {
    largest: ImageDimensions | null;
    boxes: number;
    invalid: boolean;
  },
) {
  if (depth > 6) {
    state.invalid = true;
    return;
  }
  let offset = start;
  while (offset + 8 <= end) {
    if (state.boxes >= MAX_CONTAINER_ENTRIES) {
      state.invalid = true;
      return;
    }
    state.boxes += 1;
    const size32 = view.getUint32(offset);
    const type = readFourCc(view, offset + 4);
    let headerSize = 8;
    let size = size32;
    if (size32 === 1) {
      if (offset + 16 > end) {
        state.invalid = true;
        return;
      }
      const extended = view.getBigUint64(offset + 8);
      if (extended > BigInt(Number.MAX_SAFE_INTEGER)) {
        state.invalid = true;
        return;
      }
      size = Number(extended);
      headerSize = 16;
    } else if (size32 === 0) {
      size = end - offset;
    }
    if (size < headerSize || offset + size > end) {
      state.invalid = true;
      return;
    }

    const contentStart = offset + headerSize;
    const boxEnd = offset + size;
    if (type === "ispe" && contentStart + 12 <= boxEnd) {
      const dimensions = validDimensions(
        view.getUint32(contentStart + 4),
        view.getUint32(contentStart + 8),
      );
      if (
        dimensions &&
        (!state.largest ||
          dimensions.width * dimensions.height >
            state.largest.width * state.largest.height)
      )
        state.largest = dimensions;
    } else if (ISO_CONTAINER_BOXES.has(type)) {
      const childStart = contentStart + (type === "meta" ? 4 : 0);
      if (childStart <= boxEnd)
        walkIsoBmffBoxes(view, childStart, boxEnd, depth + 1, state);
    }
    offset = boxEnd;
  }
  if (offset !== end) state.invalid = true;
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

function assertSafeDimensions(dimensions: ImageDimensions) {
  if (
    dimensions.width * dimensions.height > MAX_DECODE_PIXELS ||
    Math.max(dimensions.width, dimensions.height) > MAX_SOURCE_EDGE
  )
    throw new RangeError(
      "Choose a photo no larger than 20 megapixels or 8192 pixels on either side so it can be prepared safely on this device.",
    );
}

export async function decodeBitmap(file: File, mimeType: SupportedImageMime) {
  if (typeof createImageBitmap !== "function")
    throw new Error("This browser cannot safely normalize the selected image.");
  const options: ImageBitmapOptions = {
    imageOrientation: "from-image",
    premultiplyAlpha: "default",
    colorSpaceConversion: "default",
  };
  const typedFile =
    file.type === mimeType
      ? file
      : new File([file], file.name, {
          type: mimeType,
          lastModified: file.lastModified,
        });
  try {
    return await createImageBitmap(typedFile, options);
  } catch (nativeError) {
    if (mimeType !== "image/heic") throw nativeError;
    try {
      const { heicTo } = await import("heic-to/csp");
      return await heicTo({ blob: typedFile, type: "bitmap", options });
    } catch (fallbackError) {
      throw new AggregateError(
        [nativeError, fallbackError],
        "This browser could not decode the HEIC/HEIF photo.",
      );
    }
  }
}

export async function prepareImage(file: File): Promise<PreparedImage> {
  if (file.size > MAX_SOURCE_BYTES)
    throw new RangeError("Image exceeds the local 12 MB preparation limit.");
  const sourceBytes = new Uint8Array(await file.arrayBuffer());
  const mimeType = detectImageMimeType(sourceBytes);
  if (!mimeType)
    throw new TypeError(
      `Choose a ${COMMON_IMAGE_FORMATS} photo. SVG, TIFF, RAW, and renamed non-image files are not supported.`,
    );
  const sourceDimensions = readImageDimensions(sourceBytes, mimeType);
  if (!sourceDimensions)
    throw new TypeError("The image header is invalid or unsupported.");
  assertSafeDimensions(sourceDimensions);
  if (isKnownAnimated(sourceBytes, mimeType))
    throw new TypeError("Animated images are not supported.");
  if (typeof createImageBitmap !== "function")
    throw new Error("This browser cannot safely normalize the selected image.");

  let bitmap: ImageBitmap | undefined;
  let canvas: HTMLCanvasElement | undefined;
  try {
    bitmap = await decodeBitmap(file, mimeType);
    assertSafeDimensions({ width: bitmap.width, height: bitmap.height });
    const target = calculateTargetSize(bitmap.width, bitmap.height);
    canvas = document.createElement("canvas");
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
    if (error instanceof RangeError) throw error;
    throw new Error(
      "The image could not be normalized safely in this browser.",
      {
        cause: error,
      },
    );
  } finally {
    bitmap?.close();
    if (canvas) {
      canvas.width = 0;
      canvas.height = 0;
    }
  }
}
