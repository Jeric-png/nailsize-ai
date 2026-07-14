export const YOLOV8_SEG_CONTRACT = {
  inputSize: 640,
  detectionChannels: 37,
  detectionCount: 8400,
  maskCoefficientCount: 32,
  prototypeWidth: 160,
  prototypeHeight: 160,
} as const;

const CLASS_SCORE_CHANNEL = 4;
const MASK_COEFFICIENT_START_CHANNEL = 5;
const PROTOTYPE_PIXEL_COUNT =
  YOLOV8_SEG_CONTRACT.prototypeWidth * YOLOV8_SEG_CONTRACT.prototypeHeight;
const OUTPUT0_LENGTH =
  YOLOV8_SEG_CONTRACT.detectionChannels *
  YOLOV8_SEG_CONTRACT.detectionCount;
const OUTPUT1_LENGTH =
  YOLOV8_SEG_CONTRACT.maskCoefficientCount * PROTOTYPE_PIXEL_COUNT;

export interface LetterboxTransform {
  readonly originalWidth: number;
  readonly originalHeight: number;
  readonly inputSize: typeof YOLOV8_SEG_CONTRACT.inputSize;
  readonly scale: number;
  readonly padX: number;
  readonly padY: number;
}

export interface BoundingBox {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface PixelBounds {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

export interface CroppedSegmentationMask extends PixelBounds {
  /** Row-major sigmoid probabilities in source-image pixel coordinates. */
  readonly probabilities: Float32Array;
  /** Row-major values of 0 or 1 after applying maskThreshold. */
  readonly binary: Uint8Array;
}

export interface ConnectedComponentMetadata {
  readonly count: number;
  readonly largestPixelCount: number;
  readonly largestForegroundRatio: number;
  /** Absolute source-image coordinates for the largest component. */
  readonly largestBounds: PixelBounds | null;
  readonly touchesCropEdge: boolean;
  readonly largestTouchesCropEdge: boolean;
}

export interface MaskQualityMetadata {
  readonly foregroundPixelCount: number;
  readonly foregroundRatio: number;
  readonly meanProbability: number;
  readonly meanForegroundProbability: number;
  readonly components: ConnectedComponentMetadata;
}

export interface YoloV8SegDetection {
  readonly candidateIndex: number;
  readonly classId: 0;
  readonly confidence: number;
  /** Detection box in the original image coordinate system. */
  readonly box: BoundingBox;
  readonly mask: CroppedSegmentationMask;
  readonly quality: MaskQualityMetadata;
}

export interface YoloV8SegPostprocessInput {
  /** Fixed layout: [1, 37, 8400], stored channel-major. */
  readonly output0: Float32Array;
  /** Fixed layout: [1, 32, 160, 160], stored channel-major. */
  readonly output1: Float32Array;
  readonly letterbox: LetterboxTransform;
}

export interface YoloV8SegPostprocessOptions {
  readonly confidenceThreshold?: number;
  readonly iouThreshold?: number;
  readonly maskThreshold?: number;
  readonly maxDetections?: number;
}

interface ResolvedOptions {
  confidenceThreshold: number;
  iouThreshold: number;
  maskThreshold: number;
  maxDetections: number;
}

interface Candidate {
  index: number;
  confidence: number;
  box: BoundingBox;
}

interface ComponentAccumulator {
  pixelCount: number;
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
  touchesCropEdge: boolean;
}

const DEFAULT_OPTIONS: Readonly<ResolvedOptions> = {
  confidenceThreshold: 0.25,
  iouThreshold: 0.45,
  maskThreshold: 0.5,
  maxDetections: 10,
};

/**
 * Creates the centered, floating-point letterbox transform expected by this
 * decoder. Preprocessing must draw the image with these exact scale and padding
 * values for the inverse mapping to remain exact.
 */
export function createLetterboxTransform(
  originalWidth: number,
  originalHeight: number,
): LetterboxTransform {
  assertPositiveInteger(originalWidth, "originalWidth");
  assertPositiveInteger(originalHeight, "originalHeight");

  const inputSize = YOLOV8_SEG_CONTRACT.inputSize;
  const scale = Math.min(
    inputSize / originalWidth,
    inputSize / originalHeight,
  );

  return {
    originalWidth,
    originalHeight,
    inputSize,
    scale,
    padX: (inputSize - originalWidth * scale) / 2,
    padY: (inputSize - originalHeight * scale) / 2,
  };
}

/**
 * Decodes the fixed one-class YOLOv8-seg output without DOM or runtime types.
 * Typed-array masks can be transferred directly from a Web Worker.
 */
export function postprocessYoloV8Seg(
  input: YoloV8SegPostprocessInput,
  options: YoloV8SegPostprocessOptions = {},
): YoloV8SegDetection[] {
  validateInput(input);
  const resolvedOptions = resolveOptions(options);
  const candidates = collectCandidates(
    input.output0,
    input.letterbox,
    resolvedOptions.confidenceThreshold,
  );
  const selected = classAgnosticNms(
    candidates,
    resolvedOptions.iouThreshold,
    resolvedOptions.maxDetections,
  );

  return selected.map((candidate) => {
    const prototypeProbabilities = combineMaskPrototypes(
      input.output0,
      input.output1,
      candidate.index,
    );
    const mask = cropMaskToSourceBox(
      prototypeProbabilities,
      candidate.box,
      input.letterbox,
      resolvedOptions.maskThreshold,
    );
    const quality = analyzeMask(mask);

    return {
      candidateIndex: candidate.index,
      classId: 0,
      confidence: candidate.confidence,
      box: candidate.box,
      mask,
      quality,
    };
  });
}

function resolveOptions(
  options: YoloV8SegPostprocessOptions,
): ResolvedOptions {
  const confidenceThreshold =
    options.confidenceThreshold ?? DEFAULT_OPTIONS.confidenceThreshold;
  const iouThreshold = options.iouThreshold ?? DEFAULT_OPTIONS.iouThreshold;
  const maskThreshold =
    options.maskThreshold ?? DEFAULT_OPTIONS.maskThreshold;
  const maxDetections =
    options.maxDetections ?? DEFAULT_OPTIONS.maxDetections;

  assertUnitInterval(confidenceThreshold, "confidenceThreshold");
  assertUnitInterval(iouThreshold, "iouThreshold");
  assertUnitInterval(maskThreshold, "maskThreshold");
  assertPositiveInteger(maxDetections, "maxDetections");

  return {
    confidenceThreshold,
    iouThreshold,
    maskThreshold,
    maxDetections,
  };
}

function validateInput(input: YoloV8SegPostprocessInput) {
  if (!(input.output0 instanceof Float32Array))
    throw new TypeError("output0 must be a Float32Array");
  if (!(input.output1 instanceof Float32Array))
    throw new TypeError("output1 must be a Float32Array");
  if (input.output0.length !== OUTPUT0_LENGTH)
    throw new RangeError(
      `output0 must contain ${OUTPUT0_LENGTH} values for [1, 37, 8400]`,
    );
  if (input.output1.length !== OUTPUT1_LENGTH)
    throw new RangeError(
      `output1 must contain ${OUTPUT1_LENGTH} values for [1, 32, 160, 160]`,
    );

  const { letterbox } = input;
  assertPositiveInteger(letterbox.originalWidth, "originalWidth");
  assertPositiveInteger(letterbox.originalHeight, "originalHeight");
  if (letterbox.inputSize !== YOLOV8_SEG_CONTRACT.inputSize)
    throw new RangeError(
      `inputSize must be ${YOLOV8_SEG_CONTRACT.inputSize}`,
    );
  if (!Number.isFinite(letterbox.scale) || letterbox.scale <= 0)
    throw new RangeError("scale must be a positive finite number");
  if (!Number.isFinite(letterbox.padX) || letterbox.padX < 0)
    throw new RangeError("padX must be a non-negative finite number");
  if (!Number.isFinite(letterbox.padY) || letterbox.padY < 0)
    throw new RangeError("padY must be a non-negative finite number");

  const epsilon = 1e-6;
  if (
    letterbox.padX + letterbox.originalWidth * letterbox.scale >
      letterbox.inputSize + epsilon ||
    letterbox.padY + letterbox.originalHeight * letterbox.scale >
      letterbox.inputSize + epsilon
  )
    throw new RangeError("letterbox content must fit inside the 640 input");
}

function collectCandidates(
  output0: Float32Array,
  letterbox: LetterboxTransform,
  confidenceThreshold: number,
) {
  const candidates: Candidate[] = [];

  for (let index = 0; index < YOLOV8_SEG_CONTRACT.detectionCount; index += 1) {
    const confidence = detectionValue(output0, CLASS_SCORE_CHANNEL, index);
    if (!Number.isFinite(confidence) || confidence < confidenceThreshold)
      continue;

    const centerX = detectionValue(output0, 0, index);
    const centerY = detectionValue(output0, 1, index);
    const width = detectionValue(output0, 2, index);
    const height = detectionValue(output0, 3, index);
    if (
      !Number.isFinite(centerX) ||
      !Number.isFinite(centerY) ||
      !Number.isFinite(width) ||
      !Number.isFinite(height) ||
      width <= 0 ||
      height <= 0
    )
      continue;

    const box = undoLetterboxBox(centerX, centerY, width, height, letterbox);
    if (!box || box.width <= 0 || box.height <= 0) continue;
    candidates.push({ index, confidence, box });
  }

  return candidates;
}

function detectionValue(
  output0: Float32Array,
  channel: number,
  index: number,
) {
  return (
    output0[channel * YOLOV8_SEG_CONTRACT.detectionCount + index] ??
    Number.NaN
  );
}

function undoLetterboxBox(
  centerX: number,
  centerY: number,
  width: number,
  height: number,
  letterbox: LetterboxTransform,
): BoundingBox | null {
  const modelLeft = centerX - width / 2;
  const modelTop = centerY - height / 2;
  const modelRight = centerX + width / 2;
  const modelBottom = centerY + height / 2;
  if (
    !Number.isFinite(modelLeft) ||
    !Number.isFinite(modelTop) ||
    !Number.isFinite(modelRight) ||
    !Number.isFinite(modelBottom)
  )
    return null;

  const left = clamp(
    (modelLeft - letterbox.padX) / letterbox.scale,
    0,
    letterbox.originalWidth,
  );
  const top = clamp(
    (modelTop - letterbox.padY) / letterbox.scale,
    0,
    letterbox.originalHeight,
  );
  const right = clamp(
    (modelRight - letterbox.padX) / letterbox.scale,
    0,
    letterbox.originalWidth,
  );
  const bottom = clamp(
    (modelBottom - letterbox.padY) / letterbox.scale,
    0,
    letterbox.originalHeight,
  );

  return {
    x: left,
    y: top,
    width: Math.max(0, right - left),
    height: Math.max(0, bottom - top),
  };
}

function classAgnosticNms(
  candidates: Candidate[],
  iouThreshold: number,
  maxDetections: number,
) {
  const sorted = [...candidates].sort(
    (left, right) =>
      right.confidence - left.confidence || left.index - right.index,
  );
  const selected: Candidate[] = [];

  for (const candidate of sorted) {
    if (
      selected.some(
        (existing) =>
          intersectionOverUnion(candidate.box, existing.box) > iouThreshold,
      )
    )
      continue;
    selected.push(candidate);
    if (selected.length === maxDetections) break;
  }

  return selected;
}

function intersectionOverUnion(left: BoundingBox, right: BoundingBox) {
  const intersectionLeft = Math.max(left.x, right.x);
  const intersectionTop = Math.max(left.y, right.y);
  const intersectionRight = Math.min(
    left.x + left.width,
    right.x + right.width,
  );
  const intersectionBottom = Math.min(
    left.y + left.height,
    right.y + right.height,
  );
  const intersectionWidth = Math.max(0, intersectionRight - intersectionLeft);
  const intersectionHeight = Math.max(0, intersectionBottom - intersectionTop);
  const intersectionArea = intersectionWidth * intersectionHeight;
  const unionArea =
    left.width * left.height +
    right.width * right.height -
    intersectionArea;
  return unionArea > 0 ? intersectionArea / unionArea : 0;
}

function combineMaskPrototypes(
  output0: Float32Array,
  output1: Float32Array,
  candidateIndex: number,
) {
  const logits = new Float32Array(PROTOTYPE_PIXEL_COUNT);

  for (
    let channel = 0;
    channel < YOLOV8_SEG_CONTRACT.maskCoefficientCount;
    channel += 1
  ) {
    const coefficient = detectionValue(
      output0,
      MASK_COEFFICIENT_START_CHANNEL + channel,
      candidateIndex,
    );
    if (!Number.isFinite(coefficient))
      throw new RangeError(
        `mask coefficient ${channel} for candidate ${candidateIndex} is not finite`,
      );
    if (coefficient === 0) continue;

    const prototypeOffset = channel * PROTOTYPE_PIXEL_COUNT;
    for (let pixel = 0; pixel < PROTOTYPE_PIXEL_COUNT; pixel += 1) {
      const prototype = output1[prototypeOffset + pixel];
      if (!Number.isFinite(prototype))
        throw new RangeError(
          `prototype ${channel} contains a non-finite value`,
        );
      logits[pixel] += coefficient * prototype;
    }
  }

  for (let pixel = 0; pixel < logits.length; pixel += 1)
    logits[pixel] = sigmoid(logits[pixel]);
  return logits;
}

function cropMaskToSourceBox(
  prototypeProbabilities: Float32Array,
  box: BoundingBox,
  letterbox: LetterboxTransform,
  maskThreshold: number,
): CroppedSegmentationMask {
  const left = clamp(Math.floor(box.x), 0, letterbox.originalWidth);
  const top = clamp(Math.floor(box.y), 0, letterbox.originalHeight);
  const right = clamp(
    Math.ceil(box.x + box.width),
    left,
    letterbox.originalWidth,
  );
  const bottom = clamp(
    Math.ceil(box.y + box.height),
    top,
    letterbox.originalHeight,
  );
  const width = right - left;
  const height = bottom - top;
  const pixelCount = width * height;
  const probabilities = new Float32Array(pixelCount);
  const binary = new Uint8Array(pixelCount);
  const prototypeScale =
    YOLOV8_SEG_CONTRACT.prototypeWidth / letterbox.inputSize;
  const boxRight = box.x + box.width;
  const boxBottom = box.y + box.height;

  for (let maskY = 0; maskY < height; maskY += 1) {
    const sourceY = top + maskY + 0.5;
    if (sourceY < box.y || sourceY > boxBottom) continue;
    const modelY = sourceY * letterbox.scale + letterbox.padY;
    const prototypeY = modelY * prototypeScale - 0.5;

    for (let maskX = 0; maskX < width; maskX += 1) {
      const sourceX = left + maskX + 0.5;
      if (sourceX < box.x || sourceX > boxRight) continue;
      const modelX = sourceX * letterbox.scale + letterbox.padX;
      const prototypeX = modelX * prototypeScale - 0.5;
      const probability = bilinearSample(
        prototypeProbabilities,
        prototypeX,
        prototypeY,
      );
      const maskIndex = maskY * width + maskX;
      probabilities[maskIndex] = probability;
      binary[maskIndex] = probability >= maskThreshold ? 1 : 0;
    }
  }

  return { x: left, y: top, width, height, probabilities, binary };
}

function bilinearSample(values: Float32Array, x: number, y: number) {
  const boundedX = clamp(x, 0, YOLOV8_SEG_CONTRACT.prototypeWidth - 1);
  const boundedY = clamp(y, 0, YOLOV8_SEG_CONTRACT.prototypeHeight - 1);
  const x0 = Math.floor(boundedX);
  const y0 = Math.floor(boundedY);
  const x1 = Math.min(x0 + 1, YOLOV8_SEG_CONTRACT.prototypeWidth - 1);
  const y1 = Math.min(y0 + 1, YOLOV8_SEG_CONTRACT.prototypeHeight - 1);
  const xWeight = boundedX - x0;
  const yWeight = boundedY - y0;
  const topLeft = values[y0 * YOLOV8_SEG_CONTRACT.prototypeWidth + x0];
  const topRight = values[y0 * YOLOV8_SEG_CONTRACT.prototypeWidth + x1];
  const bottomLeft = values[y1 * YOLOV8_SEG_CONTRACT.prototypeWidth + x0];
  const bottomRight = values[y1 * YOLOV8_SEG_CONTRACT.prototypeWidth + x1];
  const top = topLeft + (topRight - topLeft) * xWeight;
  const bottom = bottomLeft + (bottomRight - bottomLeft) * xWeight;
  return top + (bottom - top) * yWeight;
}

function analyzeMask(mask: CroppedSegmentationMask): MaskQualityMetadata {
  const pixelCount = mask.width * mask.height;
  let probabilitySum = 0;
  let foregroundProbabilitySum = 0;
  let foregroundPixelCount = 0;

  for (let index = 0; index < pixelCount; index += 1) {
    const probability = mask.probabilities[index];
    probabilitySum += probability;
    if (mask.binary[index] === 0) continue;
    foregroundPixelCount += 1;
    foregroundProbabilitySum += probability;
  }

  return {
    foregroundPixelCount,
    foregroundRatio: pixelCount > 0 ? foregroundPixelCount / pixelCount : 0,
    meanProbability: pixelCount > 0 ? probabilitySum / pixelCount : 0,
    meanForegroundProbability:
      foregroundPixelCount > 0
        ? foregroundProbabilitySum / foregroundPixelCount
        : 0,
    components: connectedComponents(mask, foregroundPixelCount),
  };
}

function connectedComponents(
  mask: CroppedSegmentationMask,
  foregroundPixelCount: number,
): ConnectedComponentMetadata {
  const pixelCount = mask.width * mask.height;
  const visited = new Uint8Array(pixelCount);
  const queue = new Int32Array(pixelCount);
  let count = 0;
  let touchesCropEdge = false;
  let largest: ComponentAccumulator | null = null;

  for (let start = 0; start < pixelCount; start += 1) {
    if (mask.binary[start] === 0 || visited[start] !== 0) continue;
    count += 1;
    const component = floodComponent(mask, start, visited, queue);
    touchesCropEdge ||= component.touchesCropEdge;
    if (!largest || component.pixelCount > largest.pixelCount)
      largest = component;
  }

  return {
    count,
    largestPixelCount: largest?.pixelCount ?? 0,
    largestForegroundRatio:
      largest && foregroundPixelCount > 0
        ? largest.pixelCount / foregroundPixelCount
        : 0,
    largestBounds: largest
      ? {
          x: mask.x + largest.minX,
          y: mask.y + largest.minY,
          width: largest.maxX - largest.minX + 1,
          height: largest.maxY - largest.minY + 1,
        }
      : null,
    touchesCropEdge,
    largestTouchesCropEdge: largest?.touchesCropEdge ?? false,
  };
}

function floodComponent(
  mask: CroppedSegmentationMask,
  start: number,
  visited: Uint8Array,
  queue: Int32Array,
) {
  let head = 0;
  let tail = 1;
  queue[0] = start;
  visited[start] = 1;
  const startX = start % mask.width;
  const startY = Math.floor(start / mask.width);
  const component: ComponentAccumulator = {
    pixelCount: 0,
    minX: startX,
    minY: startY,
    maxX: startX,
    maxY: startY,
    touchesCropEdge: false,
  };

  while (head < tail) {
    const index = queue[head];
    head += 1;
    const x = index % mask.width;
    const y = Math.floor(index / mask.width);
    component.pixelCount += 1;
    component.minX = Math.min(component.minX, x);
    component.minY = Math.min(component.minY, y);
    component.maxX = Math.max(component.maxX, x);
    component.maxY = Math.max(component.maxY, y);
    component.touchesCropEdge ||=
      x === 0 || y === 0 || x === mask.width - 1 || y === mask.height - 1;

    for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
      const nextY = y + offsetY;
      if (nextY < 0 || nextY >= mask.height) continue;
      for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
        if (offsetX === 0 && offsetY === 0) continue;
        const nextX = x + offsetX;
        if (nextX < 0 || nextX >= mask.width) continue;
        const nextIndex = nextY * mask.width + nextX;
        if (mask.binary[nextIndex] === 0 || visited[nextIndex] !== 0) continue;
        visited[nextIndex] = 1;
        queue[tail] = nextIndex;
        tail += 1;
      }
    }
  }

  return component;
}

function sigmoid(value: number) {
  if (value >= 0) return 1 / (1 + Math.exp(-value));
  const exponential = Math.exp(value);
  return exponential / (1 + exponential);
}

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function assertUnitInterval(value: number, name: string) {
  if (!Number.isFinite(value) || value < 0 || value > 1)
    throw new RangeError(`${name} must be between 0 and 1`);
}

function assertPositiveInteger(value: number, name: string) {
  if (!Number.isSafeInteger(value) || value <= 0)
    throw new RangeError(`${name} must be a positive integer`);
}
