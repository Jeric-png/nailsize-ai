export const MAX_ANALYSIS_EDGE = 1600;
export const MAX_ANALYSIS_PIXELS = 2_560_000;

export interface RgbaImage {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8ClampedArray;
}

export function calculateAnalysisSize(width: number, height: number) {
  if (
    !Number.isFinite(width) ||
    !Number.isFinite(height) ||
    width <= 0 ||
    height <= 0
  )
    throw new RangeError("Image dimensions must be positive finite numbers.");
  const edgeScale = Math.min(1, MAX_ANALYSIS_EDGE / Math.max(width, height));
  const pixelScale = Math.min(
    1,
    Math.sqrt(MAX_ANALYSIS_PIXELS / (width * height)),
  );
  const scale = Math.min(edgeScale, pixelScale);
  return {
    width: Math.max(1, Math.floor(width * scale)),
    height: Math.max(1, Math.floor(height * scale)),
  };
}

export async function decodeImageForAnalysis(file: Blob): Promise<RgbaImage> {
  if (typeof createImageBitmap !== "function")
    throw new Error("This browser cannot decode the photo for local sizing.");
  let bitmap: ImageBitmap | undefined;
  try {
    bitmap = await createImageBitmap(file, {
      imageOrientation: "none",
      premultiplyAlpha: "default",
      colorSpaceConversion: "default",
    });
    const size = calculateAnalysisSize(bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = size.width;
    canvas.height = size.height;
    const context = canvas.getContext("2d", {
      alpha: false,
      willReadFrequently: true,
    });
    if (!context)
      throw new Error("Browser canvas analysis is unavailable.");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, size.width, size.height);
    context.drawImage(bitmap, 0, 0, size.width, size.height);
    const pixels = context.getImageData(0, 0, size.width, size.height);
    return { width: size.width, height: size.height, data: pixels.data };
  } catch (error) {
    throw new Error("The selected photo could not be analyzed locally.", {
      cause: error,
    });
  } finally {
    bitmap?.close();
  }
}
