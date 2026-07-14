import {
  createLetterboxTransform,
  type LetterboxTransform,
  YOLOV8_SEG_CONTRACT,
} from "./yoloV8SegPostprocess";

export const YOLO_LETTERBOX_FILL = 114 as const;
export const YOLO_INPUT_SHAPE = [
  1,
  3,
  YOLOV8_SEG_CONTRACT.inputSize,
  YOLOV8_SEG_CONTRACT.inputSize,
] as const;

export interface RgbaImageData {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8Array | Uint8ClampedArray;
}

export interface YoloPreprocessedInput {
  /** Normalized RGB pixels in NCHW/CHW order. */
  readonly data: Float32Array;
  readonly shape: typeof YOLO_INPUT_SHAPE;
  readonly letterbox: LetterboxTransform;
}

export type YoloPreprocessErrorCode =
  "invalid-image-dimensions" | "invalid-image-data";

export class YoloPreprocessError extends Error {
  readonly name = "YoloPreprocessError";

  constructor(
    readonly code: YoloPreprocessErrorCode,
    message: string,
    readonly recovery: string,
  ) {
    super(message);
  }
}

/**
 * Converts browser ImageData-compatible RGBA pixels to the fixed YOLOv8-seg
 * input. Resizing is deterministic bilinear sampling, transparent pixels are
 * composited over the model's neutral 114 fill, and no DOM canvas is required.
 */
export function preprocessYoloRgba(
  image: RgbaImageData,
): YoloPreprocessedInput {
  validateImage(image);

  const letterbox = createLetterboxTransform(image.width, image.height);
  const inputSize = letterbox.inputSize;
  const planeSize = inputSize * inputSize;
  const output = new Float32Array(planeSize * 3);
  const normalizedFill = YOLO_LETTERBOX_FILL / 255;
  output.fill(normalizedFill);

  for (let destinationY = 0; destinationY < inputSize; destinationY += 1) {
    const sourceY =
      (destinationY + 0.5 - letterbox.padY) / letterbox.scale - 0.5;
    if (sourceY < -0.5 || sourceY >= image.height - 0.5) continue;

    const clampedY = clamp(sourceY, 0, image.height - 1);
    const top = Math.floor(clampedY);
    const bottom = Math.min(top + 1, image.height - 1);
    const yWeight = clampedY - top;

    for (let destinationX = 0; destinationX < inputSize; destinationX += 1) {
      const sourceX =
        (destinationX + 0.5 - letterbox.padX) / letterbox.scale - 0.5;
      if (sourceX < -0.5 || sourceX >= image.width - 0.5) continue;

      const clampedX = clamp(sourceX, 0, image.width - 1);
      const left = Math.floor(clampedX);
      const right = Math.min(left + 1, image.width - 1);
      const xWeight = clampedX - left;
      const destinationIndex = destinationY * inputSize + destinationX;

      for (let channel = 0; channel < 3; channel += 1) {
        const topValue = lerp(
          compositedChannel(image, left, top, channel),
          compositedChannel(image, right, top, channel),
          xWeight,
        );
        const bottomValue = lerp(
          compositedChannel(image, left, bottom, channel),
          compositedChannel(image, right, bottom, channel),
          xWeight,
        );
        output[channel * planeSize + destinationIndex] =
          lerp(topValue, bottomValue, yWeight) / 255;
      }
    }
  }

  return { data: output, shape: YOLO_INPUT_SHAPE, letterbox };
}

function validateImage(image: RgbaImageData) {
  if (
    !Number.isInteger(image.width) ||
    image.width <= 0 ||
    !Number.isInteger(image.height) ||
    image.height <= 0
  ) {
    throw new YoloPreprocessError(
      "invalid-image-dimensions",
      "The nail photo must have positive whole-number pixel dimensions.",
      "Choose the photo again or take a new photo.",
    );
  }

  if (
    !(
      image.data instanceof Uint8Array ||
      image.data instanceof Uint8ClampedArray
    ) ||
    image.data.length !== image.width * image.height * 4
  ) {
    throw new YoloPreprocessError(
      "invalid-image-data",
      "The nail photo does not contain complete RGBA pixel data.",
      "Decode the photo to browser ImageData before sizing.",
    );
  }
}

function compositedChannel(
  image: RgbaImageData,
  x: number,
  y: number,
  channel: number,
) {
  const pixelOffset = (y * image.width + x) * 4;
  const alpha = (image.data[pixelOffset + 3] ?? 0) / 255;
  const value = image.data[pixelOffset + channel] ?? 0;
  return value * alpha + YOLO_LETTERBOX_FILL * (1 - alpha);
}

function lerp(start: number, end: number, weight: number) {
  return start + (end - start) * weight;
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(Math.max(value, minimum), maximum);
}
