export type CaptureType =
  "left_fingers" | "left_thumb" | "right_fingers" | "right_thumb";

export type Digit = "thumb" | "index" | "middle" | "ring" | "pinky";

export interface Point {
  x: number;
  y: number;
}

export interface ImageDimensions {
  width: number;
  height: number;
}

export type CoinMarkers = [
  Point,
  Point,
  Point,
  Point,
  Point,
  Point,
  Point,
  Point,
];
export type EdgePair = [Point, Point];

export interface SampleMeasurement {
  digit: Digit;
  widthMm: number;
  edges: EdgePair;
}

export interface FinalMeasurement {
  digit: Digit;
  projectedWidthMm: number;
  sizingWidthMm: number;
  firstWidthMm: number;
  verificationWidthMm: number;
  repeatDeltaMm: number;
  consistent: boolean;
  recommendedSize: string | null;
  alternateSize: string | null;
}

export interface CaptureResult {
  captureType: CaptureType;
  calibrationReference: typeof COIN_REFERENCE_ID;
  measurements: FinalMeasurement[];
  methodVersion: "guided-sg50-coin-v1";
  chartId: "platform-default";
  chartVersion: "1";
}

interface CoinCalibration {
  centerPx: Point;
  diameterPx: number;
  mmPerPixel: number;
}

export const captureOrder: CaptureType[] = [
  "left_fingers",
  "left_thumb",
  "right_fingers",
  "right_thumb",
];

export const captureDigits: Record<CaptureType, readonly Digit[]> = {
  left_fingers: ["index", "middle", "ring", "pinky"],
  left_thumb: ["thumb"],
  right_fingers: ["index", "middle", "ring", "pinky"],
  right_thumb: ["thumb"],
};

export const COIN_REFERENCE_ID = "sg-50-cent-third-series-23mm" as const;
export const COIN_DIAMETER_MM = 23;
export const MIN_RENDERED_COIN_DIAMETER_PX = 120;
export const COIN_MARKER_LABELS = [
  "Top",
  "Upper right",
  "Right",
  "Lower right",
  "Bottom",
  "Lower left",
  "Left",
  "Upper left",
] as const;
export const REPEAT_TOLERANCE_MM = 0.6;

const MIN_SOURCE_COIN_DIAMETER_PX = 120;
const MAX_COIN_DIAMETER_SPREAD = 0.08;
const MAX_COIN_CENTER_SPREAD = 0.06;
const MIN_MARKER_ANGLE_RADIANS = (20 * Math.PI) / 180;
const MAX_MARKER_ANGLE_RADIANS = (70 * Math.PI) / 180;
const MAX_NAIL_DISTANCE_IN_COIN_DIAMETERS = 4.5;
const MIN_PLAUSIBLE_NAIL_MM = 5;
const MAX_PLAUSIBLE_NAIL_MM = 25;
const RATIO_COMPARISON_EPSILON = 1e-9;
const MILLIMETRE_COMPARISON_EPSILON = 1e-9;
const COIN_OPPOSITE_PAIRS = [
  [0, 4],
  [1, 5],
  [2, 6],
  [3, 7],
] as const;
const CHART = Array.from({ length: 10 }, (_, size) => ({
  size: String(size),
  widthMm: 18 - size,
}));

export function createDefaultCoinMarkers(
  dimensions: ImageDimensions,
): CoinMarkers {
  assertImageDimensions(dimensions);
  const radiusPx = Math.min(dimensions.width, dimensions.height) * 0.18;
  const centerPx = {
    x: dimensions.width * 0.23,
    y: dimensions.height * 0.22,
  };
  return COIN_MARKER_LABELS.map((_, index) => {
    const angle = -Math.PI / 2 + index * (Math.PI / 4);
    return {
      x: (centerPx.x + Math.cos(angle) * radiusPx) / dimensions.width,
      y: (centerPx.y + Math.sin(angle) * radiusPx) / dimensions.height,
    };
  }) as CoinMarkers;
}

export function createInitialCoinMarkers(
  dimensions: ImageDimensions,
): CoinMarkers {
  assertImageDimensions(dimensions);
  return [
    { x: 0.12, y: 0.78 },
    { x: 0.37, y: 0.78 },
    { x: 0.63, y: 0.78 },
    { x: 0.88, y: 0.78 },
    { x: 0.12, y: 0.9 },
    { x: 0.37, y: 0.9 },
    { x: 0.63, y: 0.9 },
    { x: 0.88, y: 0.9 },
  ];
}

export function validateCoinCalibration(
  markers: CoinMarkers,
  dimensions: ImageDimensions,
): string | null {
  try {
    assertImageDimensions(dimensions);
  } catch {
    return "This photo does not contain usable image dimensions.";
  }
  if (markers.some((point) => !isNormalized(point)))
    return "Keep every coin-rim marker inside the photo.";

  const points = markers.map((point) => toPixels(point, dimensions));
  if (
    points.some(
      (point) =>
        point.x < 2 ||
        point.y < 2 ||
        point.x > dimensions.width - 2 ||
        point.y > dimensions.height - 2,
    )
  )
    return "Keep the complete coin rim visible inside the photo.";

  const crossProducts = points.map((point, index) =>
    cross(
      point,
      points[(index + 1) % points.length],
      points[(index + 2) % points.length],
    ),
  );
  if (crossProducts.some((value) => value <= 1))
    return "Place markers 1–8 clockwise and spread them evenly around the complete coin rim.";

  const pairCenters = COIN_OPPOSITE_PAIRS.map(([first, second]) =>
    midpoint(points[first], points[second]),
  );
  const center = averagePoint(pairCenters);
  const diameters = COIN_OPPOSITE_PAIRS.map(([first, second]) =>
    distance(points[first], points[second]),
  );
  const diameter = median(diameters);

  const diameterSpread =
    (Math.max(...diameters) - Math.min(...diameters)) / diameter;
  if (diameterSpread > MAX_COIN_DIAMETER_SPREAD + RATIO_COMPARISON_EPSILON)
    return "The marked coin looks oval. Hold the phone directly overhead and place all eight markers on the rim.";

  if (diameter + 1e-6 < MIN_SOURCE_COIN_DIAMETER_PX)
    return "Move the phone closer. The marked coin must be at least 120 pixels wide for measurement.";

  const centerSpread =
    Math.max(...pairCenters.map((pairCenter) => distance(pairCenter, center))) /
    diameter;
  if (centerSpread > MAX_COIN_CENTER_SPREAD + RATIO_COMPARISON_EPSILON)
    return "Opposite coin markers do not meet at one centre. Reposition all eight markers on the rim.";

  const markerAngles = points.map((point) =>
    Math.atan2(point.y - center.y, point.x - center.x),
  );
  const angleGaps = markerAngles.map((angle, index) =>
    positiveAngle(markerAngles[(index + 1) % markerAngles.length] - angle),
  );
  if (
    angleGaps.some(
      (gap) => gap < MIN_MARKER_ANGLE_RADIANS || gap > MAX_MARKER_ANGLE_RADIANS,
    )
  )
    return "Place markers 1–8 clockwise and spread them evenly around the complete coin rim.";

  return null;
}

export function validateRenderedCoinSize(
  markers: CoinMarkers,
  renderedDimensions: ImageDimensions,
): string | null {
  try {
    assertImageDimensions(renderedDimensions);
  } catch {
    return "Wait for the complete photo to appear before confirming the coin rim.";
  }
  if (markers.some((point) => !isNormalized(point)))
    return "Keep every coin-rim marker inside the photo.";
  const points = markers.map((point) => toPixels(point, renderedDimensions));
  const diameter = median(
    COIN_OPPOSITE_PAIRS.map(([first, second]) =>
      distance(points[first], points[second]),
    ),
  );
  if (diameter + 1e-6 < MIN_RENDERED_COIN_DIAMETER_PX)
    return "Retake the photo closer. The marked coin must appear at least 120 screen pixels wide in the annotation view.";
  return null;
}

export function measureSample(
  dimensions: ImageDimensions,
  coinMarkers: CoinMarkers,
  edgesByDigit: Partial<Record<Digit, EdgePair>>,
  digits: readonly Digit[],
): SampleMeasurement[] {
  const calibration = createCoinCalibration(coinMarkers, dimensions);

  return digits.map((digit) => {
    const edges = edgesByDigit[digit];
    if (!edges) throw new RangeError(`Mark both edges of the ${digit} nail.`);
    if (edges.some((point) => !isNormalized(point)))
      throw new RangeError(`Keep both ${digit} markers inside the photo.`);

    const edgePixels = edges.map((point) => toPixels(point, dimensions)) as [
      Point,
      Point,
    ];
    const nailCenter = midpoint(edgePixels[0], edgePixels[1]);
    const distanceFromCoin =
      distance(nailCenter, calibration.centerPx) / calibration.diameterPx;
    if (
      distanceFromCoin >
      MAX_NAIL_DISTANCE_IN_COIN_DIAMETERS + RATIO_COMPARISON_EPSILON
    )
      throw new RangeError(
        `Keep the 50-cent coin beside the ${digit} nail, no more than about four coin widths away.`,
      );

    const widthMm =
      distance(edgePixels[0], edgePixels[1]) * calibration.mmPerPixel;
    if (
      widthMm < MIN_PLAUSIBLE_NAIL_MM - MILLIMETRE_COMPARISON_EPSILON ||
      widthMm > MAX_PLAUSIBLE_NAIL_MM + MILLIMETRE_COMPARISON_EPSILON
    )
      throw new RangeError(
        `The ${digit} markers are ${widthMm.toFixed(1)} mm apart. Mark the two sidewalls at the nail's widest point.`,
      );
    return { digit, widthMm, edges };
  });
}

export function compareSamples(
  captureType: CaptureType,
  first: SampleMeasurement[],
  verification: SampleMeasurement[],
): CaptureResult {
  const expected = captureDigits[captureType];
  if (
    first.length !== expected.length ||
    verification.length !== expected.length
  )
    throw new RangeError(
      "Both photos must contain every expected nail measurement.",
    );

  const measurements = expected.map((digit) => {
    const firstReading = first.find((item) => item.digit === digit);
    const verificationReading = verification.find(
      (item) => item.digit === digit,
    );
    if (!firstReading || !verificationReading)
      throw new RangeError(`Both photos must include the ${digit} nail.`);

    const delta = Math.abs(firstReading.widthMm - verificationReading.widthMm);
    const average = (firstReading.widthMm + verificationReading.widthMm) / 2;
    const sizingWidth = Math.max(
      firstReading.widthMm,
      verificationReading.widthMm,
    );
    const recommendation = recommendSize(sizingWidth);
    const averageRecommendation = recommendSize(average);
    return {
      digit,
      projectedWidthMm: round(average, 1),
      sizingWidthMm: round(sizingWidth, 1),
      firstWidthMm: round(firstReading.widthMm, 1),
      verificationWidthMm: round(verificationReading.widthMm, 1),
      repeatDeltaMm: delta,
      consistent: delta <= REPEAT_TOLERANCE_MM + MILLIMETRE_COMPARISON_EPSILON,
      recommendedSize: recommendation?.recommendedSize ?? null,
      alternateSize:
        recommendation &&
        averageRecommendation &&
        averageRecommendation.recommendedSize !== recommendation.recommendedSize
          ? averageRecommendation.recommendedSize
          : null,
    };
  });

  return {
    captureType,
    calibrationReference: COIN_REFERENCE_ID,
    measurements,
    methodVersion: "guided-sg50-coin-v1",
    chartId: "platform-default",
    chartVersion: "1",
  };
}

export function isCaptureConsistent(result: CaptureResult): boolean {
  return result.measurements.every((measurement) => measurement.consistent);
}

export function formatRepeatDeltaMm(
  deltaMm: number,
  consistent: boolean,
): string {
  if (
    !consistent &&
    deltaMm > REPEAT_TOLERANCE_MM &&
    Number(deltaMm.toFixed(2)) <= REPEAT_TOLERANCE_MM
  )
    return `> ${REPEAT_TOLERANCE_MM.toFixed(2)}`;
  return deltaMm.toFixed(2);
}

export function recommendSize(
  widthMm: number,
  halfSpreadMm = 0,
): { recommendedSize: string; alternateSize: string | null } | null {
  if (!Number.isFinite(widthMm) || !Number.isFinite(halfSpreadMm)) return null;
  if (widthMm > CHART[0].widthMm || widthMm < CHART.at(-1)!.widthMm)
    return null;

  const recommendedIndex = CHART.findIndex(
    (entry, index) =>
      entry.widthMm >= widthMm &&
      (index === CHART.length - 1 || CHART[index + 1].widthMm < widthMm),
  );
  if (recommendedIndex < 0) return null;

  const lower = widthMm - Math.max(0, halfSpreadMm);
  const upper = widthMm + Math.max(0, halfSpreadMm);
  const alternate = CHART.filter(
    (entry, index) =>
      index !== recommendedIndex &&
      entry.widthMm >= lower &&
      entry.widthMm <= upper,
  ).sort(
    (left, right) =>
      Math.abs(left.widthMm - widthMm) - Math.abs(right.widthMm - widthMm),
  )[0];

  return {
    recommendedSize: CHART[recommendedIndex].size,
    alternateSize: alternate?.size ?? null,
  };
}

function createCoinCalibration(
  markers: CoinMarkers,
  dimensions: ImageDimensions,
): CoinCalibration {
  const issue = validateCoinCalibration(markers, dimensions);
  if (issue) throw new RangeError(issue);
  const points = markers.map((point) => toPixels(point, dimensions));
  const pairCenters = COIN_OPPOSITE_PAIRS.map(([first, second]) =>
    midpoint(points[first], points[second]),
  );
  const diameterPx = median(
    COIN_OPPOSITE_PAIRS.map(([first, second]) =>
      distance(points[first], points[second]),
    ),
  );
  return {
    centerPx: averagePoint(pairCenters),
    diameterPx,
    mmPerPixel: COIN_DIAMETER_MM / diameterPx,
  };
}

function assertImageDimensions(dimensions: ImageDimensions): void {
  if (
    !Number.isFinite(dimensions.width) ||
    !Number.isFinite(dimensions.height) ||
    dimensions.width <= 0 ||
    dimensions.height <= 0
  )
    throw new RangeError("Image dimensions must be positive finite numbers.");
}

function toPixels(point: Point, dimensions: ImageDimensions): Point {
  return {
    x: point.x * dimensions.width,
    y: point.y * dimensions.height,
  };
}

function isNormalized(point: Point): boolean {
  return (
    Number.isFinite(point.x) &&
    Number.isFinite(point.y) &&
    point.x >= 0 &&
    point.x <= 1 &&
    point.y >= 0 &&
    point.y <= 1
  );
}

function midpoint(first: Point, second: Point): Point {
  return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
}

function averagePoint(points: Point[]): Point {
  return {
    x: points.reduce((sum, point) => sum + point.x, 0) / points.length,
    y: points.reduce((sum, point) => sum + point.y, 0) / points.length,
  };
}

function positiveAngle(value: number): number {
  const fullTurn = Math.PI * 2;
  return ((value % fullTurn) + fullTurn) % fullTurn;
}

function median(values: number[]): number {
  const sorted = [...values].sort((left, right) => left - right);
  const middle = sorted.length / 2;
  return (sorted[middle - 1] + sorted[middle]) / 2;
}

function distance(left: Point, right: Point): number {
  return Math.hypot(right.x - left.x, right.y - left.y);
}

function cross(first: Point, second: Point, third: Point): number {
  return (
    (second.x - first.x) * (third.y - second.y) -
    (second.y - first.y) * (third.x - second.x)
  );
}

function round(value: number, places: number): number {
  const factor = 10 ** places;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}
