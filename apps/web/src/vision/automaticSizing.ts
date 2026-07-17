import {
  recommendClosestSize,
  recommendSize,
  type Digit,
} from "../guidedSizing";
import {
  estimateWidthWithCoinEllipse,
  measureWidthWithCoinEllipse,
  type CoinEllipseCalibration,
  type ImageSize,
  type PixelPoint,
} from "./coinCalibration";
import type {
  CroppedSegmentationMask,
  YoloV8SegDetection,
} from "./yoloV8SegPostprocess";

export type HandSide = "left" | "right";

export interface NailWidthLine {
  readonly start: PixelPoint;
  readonly end: PixelPoint;
}

export interface AutomaticNailMeasurement {
  readonly digit: Digit;
  readonly source: "automatic" | "user-corrected";
  readonly detectionIndex: number;
  readonly confidence: number;
  readonly widthLine: NailWidthLine;
  readonly projectedWidthMm: number;
  readonly uncertaintyMm: number;
  readonly recommendedSize: string | null;
  readonly requiresPhysicalConfirmation: boolean;
  readonly needsReview: boolean;
  readonly reviewReasons: readonly string[];
}

export type AutomaticHandSizingAssessment =
  | {
      readonly status: "accepted";
      readonly measurements: readonly AutomaticNailMeasurement[];
      readonly needsReview: boolean;
    }
  | {
      readonly status: "rejected";
      readonly message: string;
    };

const DIGITS_BY_X: Record<HandSide, readonly Digit[]> = {
  left: ["pinky", "ring", "middle", "index", "thumb"],
  right: ["thumb", "index", "middle", "ring", "pinky"],
};
const MIN_MASK_PIXELS = 36;
const MIN_DETECTION_CONFIDENCE = 0.25;
const REVIEW_DETECTION_CONFIDENCE = 0.55;
const REVIEW_COMPONENT_RATIO = 0.9;

export function deriveAutomaticHandSizing(input: {
  side: HandSide;
  image: ImageSize;
  detections: readonly YoloV8SegDetection[];
  calibration: CoinEllipseCalibration;
}): AutomaticHandSizingAssessment {
  if (!isValidImageSize(input.image))
    return rejected("The prepared photo dimensions are not usable.");

  const candidates = input.detections
    .map((detection, detectionIndex) => ({ detection, detectionIndex }))
    .filter(({ detection }) => isUsableDetection(detection))
    .sort(
      (left, right) =>
        detectionScore(right.detection) - detectionScore(left.detection),
    )
    .slice(0, 5)
    .sort((left, right) => centerX(left.detection) - centerX(right.detection));

  if (candidates.length !== 5)
    return rejected(
      `Only ${candidates.length} clear nail${candidates.length === 1 ? " was" : "s were"} found. Retake the photo with all five bare nails separated and visible.`,
    );

  const span =
    centerX(candidates.at(-1)!.detection) - centerX(candidates[0].detection);
  if (span < input.image.width * 0.24)
    return rejected(
      "The five suggested nails are too tightly grouped to label safely. Spread the fingers and retake the photo.",
    );

  const measurements: AutomaticNailMeasurement[] = [];
  const digits = DIGITS_BY_X[input.side];
  for (const [index, candidate] of candidates.entries()) {
    const measurement = measurementFor(
      digits[index],
      candidate,
      input.calibration,
    );
    if (typeof measurement === "string") return rejected(measurement);
    measurements.push(measurement);
  }

  return {
    status: "accepted",
    measurements,
    needsReview: measurements.some((measurement) => measurement.needsReview),
  };
}

export function deriveAutomaticSingleNailSizing(input: {
  digit: Digit;
  image: ImageSize;
  detections: readonly YoloV8SegDetection[];
  calibration: CoinEllipseCalibration;
}): AutomaticHandSizingAssessment {
  if (!isValidImageSize(input.image))
    return rejected("The prepared photo dimensions are not usable.");

  const candidate = input.detections
    .map((detection, detectionIndex) => ({ detection, detectionIndex }))
    .filter(({ detection }) => isUsableDetection(detection))
    .sort(
      (left, right) =>
        detectionScore(right.detection) - detectionScore(left.detection),
    )[0];
  if (!candidate)
    return rejected(
      "No clear nail was found. Retake the photo with one complete bare nail visible beside the round reference.",
    );

  const measurement = measurementFor(
    input.digit,
    candidate,
    input.calibration,
    true,
  );
  if (typeof measurement === "string") return rejected(measurement);
  return {
    status: "accepted",
    measurements: [measurement],
    needsReview: measurement.needsReview,
  };
}

export function recalculateAutomaticMeasurement(
  measurement: AutomaticNailMeasurement,
  widthLine: NailWidthLine,
  calibration: CoinEllipseCalibration,
): AutomaticNailMeasurement {
  const calibrated = measureWidthWithCoinEllipse(
    widthLine.start,
    widthLine.end,
    calibration,
  );
  const conservative = recommendSize(
    calibrated.widthMm + calibrated.uncertaintyMm,
  );
  const centre = recommendSize(calibrated.widthMm);
  return {
    ...measurement,
    source: "user-corrected",
    widthLine,
    projectedWidthMm: round(calibrated.widthMm, 1),
    uncertaintyMm: round(calibrated.uncertaintyMm, 1),
    recommendedSize: conservative,
    requiresPhysicalConfirmation:
      centre !== null && conservative !== null && centre !== conservative,
    needsReview: false,
    reviewReasons: [],
  };
}

function measurementFor(
  digit: Digit,
  candidate: {
    detection: YoloV8SegDetection;
    detectionIndex: number;
  },
  calibration: CoinEllipseCalibration,
  bestEffort = false,
): AutomaticNailMeasurement | string {
  const widthLine = transverseWidthLine(candidate.detection.mask);
  if (!widthLine)
    return `The ${digit} nail outline is incomplete. Retake the photo with the full nail visible.`;

  let calibrated;
  try {
    calibrated = bestEffort
      ? estimateWidthWithCoinEllipse(
          widthLine.start,
          widthLine.end,
          calibration,
        )
      : measureWidthWithCoinEllipse(
          widthLine.start,
          widthLine.end,
          calibration,
        );
  } catch (error) {
    return error instanceof RangeError
      ? error.message
      : "A suggested nail width could not be calibrated.";
  }

  const reviewReasons: string[] = [];
  if (candidate.detection.confidence < REVIEW_DETECTION_CONFIDENCE)
    reviewReasons.push("low outline confidence");
  if (
    candidate.detection.quality.components.largestForegroundRatio <
    REVIEW_COMPONENT_RATIO
  )
    reviewReasons.push("fragmented outline");
  if (candidate.detection.quality.components.largestTouchesCropEdge)
    reviewReasons.push("outline touches its detection edge");
  if (calibrated.uncertaintyMm > 0.6)
    reviewReasons.push("calibration uncertainty");

  const sizeRecommendation = bestEffort ? recommendClosestSize : recommendSize;
  const conservative = sizeRecommendation(
    calibrated.widthMm + calibrated.uncertaintyMm,
  );
  const centre = sizeRecommendation(calibrated.widthMm);
  return {
    digit,
    source: "automatic",
    detectionIndex: candidate.detectionIndex,
    confidence: candidate.detection.confidence,
    widthLine,
    projectedWidthMm: round(calibrated.widthMm, 1),
    uncertaintyMm: round(calibrated.uncertaintyMm, 1),
    recommendedSize: conservative,
    requiresPhysicalConfirmation:
      centre !== null && conservative !== null && centre !== conservative,
    needsReview: reviewReasons.length > 0,
    reviewReasons,
  };
}

function isUsableDetection(detection: YoloV8SegDetection) {
  const bounds = detection.quality.components.largestBounds;
  return (
    detection.confidence >= MIN_DETECTION_CONFIDENCE &&
    detection.quality.components.largestPixelCount >= MIN_MASK_PIXELS &&
    bounds !== null &&
    bounds.width >= 4 &&
    bounds.height >= 4
  );
}

function detectionScore(detection: YoloV8SegDetection) {
  return (
    detection.confidence *
    Math.max(0.25, detection.quality.components.largestForegroundRatio)
  );
}

function centerX(detection: YoloV8SegDetection) {
  const bounds = detection.quality.components.largestBounds ?? detection.box;
  return bounds.x + bounds.width / 2;
}

function transverseWidthLine(
  mask: CroppedSegmentationMask,
): NailWidthLine | null {
  const points = largestComponent(mask);
  if (points.length < MIN_MASK_PIXELS) return null;

  const centroid = points.reduce(
    (sum, point) => ({ x: sum.x + point.x, y: sum.y + point.y }),
    { x: 0, y: 0 },
  );
  centroid.x /= points.length;
  centroid.y /= points.length;

  let xx = 0;
  let xy = 0;
  let yy = 0;
  for (const point of points) {
    const x = point.x - centroid.x;
    const y = point.y - centroid.y;
    xx += x * x;
    xy += x * y;
    yy += y * y;
  }
  const angle = 0.5 * Math.atan2(2 * xy, xx - yy);
  const firstAxis = { x: Math.cos(angle), y: Math.sin(angle) };
  const firstVariance = axisVariance(points, centroid, firstAxis);
  const secondAxis = { x: -firstAxis.y, y: firstAxis.x };
  const secondVariance = axisVariance(points, centroid, secondAxis);
  const major = firstVariance >= secondVariance ? firstAxis : secondAxis;
  const minor = { x: -major.y, y: major.x };

  const projected = points.map((point) => {
    const x = point.x - centroid.x;
    const y = point.y - centroid.y;
    return {
      u: x * major.x + y * major.y,
      v: x * minor.x + y * minor.y,
    };
  });
  const minU = Math.min(...projected.map(({ u }) => u));
  const maxU = Math.max(...projected.map(({ u }) => u));
  const length = maxU - minU;
  if (!Number.isFinite(length) || length < 3) return null;

  const centralMin = minU + length * 0.15;
  const centralMax = maxU - length * 0.15;
  const binSize = Math.max(1, length / 80);
  const bins = new Map<
    number,
    { minV: number; maxV: number; sumU: number; count: number }
  >();
  for (const point of projected) {
    if (point.u < centralMin || point.u > centralMax) continue;
    const key = Math.floor((point.u - centralMin) / binSize);
    const bin = bins.get(key);
    if (bin) {
      bin.minV = Math.min(bin.minV, point.v);
      bin.maxV = Math.max(bin.maxV, point.v);
      bin.sumU += point.u;
      bin.count += 1;
    } else {
      bins.set(key, {
        minV: point.v,
        maxV: point.v,
        sumU: point.u,
        count: 1,
      });
    }
  }
  const chords = [...bins.values()]
    .filter((bin) => bin.count >= 2 && bin.maxV - bin.minV >= 3)
    .sort((left, right) => left.maxV - left.minV - (right.maxV - right.minV));
  if (chords.length === 0) return null;
  const targetWidth =
    chords[Math.floor((chords.length - 1) * 0.85)].maxV -
    chords[Math.floor((chords.length - 1) * 0.85)].minV;
  const chord = chords.reduce((best, current) =>
    Math.abs(current.maxV - current.minV - targetWidth) <
    Math.abs(best.maxV - best.minV - targetWidth)
      ? current
      : best,
  );
  const u = chord.sumU / chord.count;
  return {
    start: fromAxes(centroid, major, minor, u, chord.minV),
    end: fromAxes(centroid, major, minor, u, chord.maxV),
  };
}

function largestComponent(mask: CroppedSegmentationMask): PixelPoint[] {
  const visited = new Uint8Array(mask.binary.length);
  const queue = new Int32Array(mask.binary.length);
  let largest: number[] = [];
  for (let start = 0; start < mask.binary.length; start += 1) {
    if (mask.binary[start] === 0 || visited[start] === 1) continue;
    let head = 0;
    let tail = 0;
    queue[tail++] = start;
    visited[start] = 1;
    const component: number[] = [];
    while (head < tail) {
      const current = queue[head++];
      component.push(current);
      const x = current % mask.width;
      const y = Math.floor(current / mask.width);
      for (let offsetY = -1; offsetY <= 1; offsetY += 1) {
        for (let offsetX = -1; offsetX <= 1; offsetX += 1) {
          if (offsetX === 0 && offsetY === 0) continue;
          const nextX = x + offsetX;
          const nextY = y + offsetY;
          if (
            nextX < 0 ||
            nextY < 0 ||
            nextX >= mask.width ||
            nextY >= mask.height
          )
            continue;
          const next = nextY * mask.width + nextX;
          if (visited[next] === 0 && mask.binary[next] === 1) {
            visited[next] = 1;
            queue[tail++] = next;
          }
        }
      }
    }
    if (component.length > largest.length) largest = component;
  }
  return largest.map((index) => ({
    x: mask.x + (index % mask.width) + 0.5,
    y: mask.y + Math.floor(index / mask.width) + 0.5,
  }));
}

function axisVariance(
  points: readonly PixelPoint[],
  centroid: PixelPoint,
  axis: PixelPoint,
) {
  return points.reduce((sum, point) => {
    const projection =
      (point.x - centroid.x) * axis.x + (point.y - centroid.y) * axis.y;
    return sum + projection * projection;
  }, 0);
}

function fromAxes(
  centroid: PixelPoint,
  major: PixelPoint,
  minor: PixelPoint,
  u: number,
  v: number,
): PixelPoint {
  return {
    x: centroid.x + major.x * u + minor.x * v,
    y: centroid.y + major.y * u + minor.y * v,
  };
}

function isValidImageSize(image: ImageSize) {
  return (
    Number.isFinite(image.width) &&
    Number.isFinite(image.height) &&
    image.width > 0 &&
    image.height > 0
  );
}

function rejected(message: string): AutomaticHandSizingAssessment {
  return { status: "rejected", message };
}

function round(value: number, places: number) {
  const factor = 10 ** places;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}
