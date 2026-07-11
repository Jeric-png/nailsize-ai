const MAX_EDGE = 4096;
const MAX_PIXELS = 16_000_000;
const MAX_SOURCE_BYTES = 12 * 1024 * 1024;
const BROWSER_DECODABLE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
]);

export interface PreparedImage {
  file: File;
  normalizedInBrowser: boolean;
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
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  };
}

function containsAscii(bytes: Uint8Array, value: string) {
  const signature = new TextEncoder().encode(value);
  outer: for (
    let offset = 0;
    offset <= bytes.length - signature.length;
    offset += 1
  ) {
    for (let index = 0; index < signature.length; index += 1)
      if (bytes[offset + index] !== signature[index]) continue outer;
    return true;
  }
  return false;
}

export function isKnownAnimated(bytes: Uint8Array, mimeType: string) {
  if (mimeType === "image/png") return containsAscii(bytes, "acTL");
  if (mimeType === "image/webp")
    return containsAscii(bytes, "ANIM") || containsAscii(bytes, "ANMF");
  return false;
}

function canvasBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/webp", 0.9),
  );
}

export async function prepareImage(file: File): Promise<PreparedImage> {
  if (
    file.size > MAX_SOURCE_BYTES ||
    !BROWSER_DECODABLE_TYPES.has(file.type) ||
    typeof createImageBitmap !== "function"
  )
    return { file, normalizedInBrowser: false };

  if (
    (file.type === "image/png" || file.type === "image/webp") &&
    isKnownAnimated(new Uint8Array(await file.arrayBuffer()), file.type)
  )
    return { file, normalizedInBrowser: false };

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
    const context = canvas.getContext("2d", { alpha: true });
    if (!context) return { file, normalizedInBrowser: false };
    context.drawImage(bitmap, 0, 0, target.width, target.height);
    const blob = await canvasBlob(canvas);
    if (!blob || blob.type !== "image/webp")
      return { file, normalizedInBrowser: false };

    const baseName = file.name.replace(/\.[^.]+$/, "") || "nail-capture";
    return {
      file: new File([blob], `${baseName}.webp`, {
        type: "image/webp",
        lastModified: file.lastModified,
      }),
      normalizedInBrowser: true,
    };
  } catch {
    return { file, normalizedInBrowser: false };
  } finally {
    bitmap?.close();
  }
}
