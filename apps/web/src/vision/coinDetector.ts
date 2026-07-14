import type { CoinEllipseProposal, PixelPoint } from "./coinCalibration";

const MAX_WORKING_DIMENSION = 640;
const CENTER_GRID_SIZE = 4;
const PERIMETER_SAMPLES = 96;
const MIN_WORKING_RADIUS_PX = 12;
const MAX_CENTER_CANDIDATES = 8;
const MAX_PROPOSALS = 3;
const MIN_DETECTION_COVERAGE = 0.78;
const MAX_DETECTION_RESIDUAL = 0.065;
const MIN_DETECTION_CONFIDENCE = 0.68;

export interface RgbaImageDataLike {
  data: Uint8Array | Uint8ClampedArray;
  width: number;
  height: number;
}

export interface CoinEllipseGeometry {
  center: PixelPoint;
  majorRadiusPx: number;
  minorRadiusPx: number;
  rotationRadians: number;
}

export interface RankedCoinEllipseProposal {
  proposal: CoinEllipseProposal;
  confidence: number;
}

export type CoinDetectionFailureReason =
  "invalid_image" | "no_edges" | "no_round_rim" | "rim_cropped" | "ambiguous";

export type CoinEllipseDetectionResult =
  | {
      status: "proposals";
      proposals: RankedCoinEllipseProposal[];
    }
  | {
      status: "no_confident_proposal";
      reason: CoinDetectionFailureReason;
    };

interface PreparedImage {
  width: number;
  height: number;
  scale: number;
  magnitude: Float32Array;
  gradientX: Float32Array;
  gradientY: Float32Array;
  edgeThreshold: number;
}

interface EdgePoint {
  x: number;
  y: number;
  unitX: number;
  unitY: number;
  weight: number;
}

interface WorkingGeometry {
  centerX: number;
  centerY: number;
  majorRadius: number;
  minorRadius: number;
  rotation: number;
}

interface RimScore {
  coverage: number;
  normalizedResidual: number;
  meanAlignment: number;
  score: number;
  cropped: boolean;
}

interface WorkingCandidate {
  geometry: WorkingGeometry;
  rim: RimScore;
}

/**
 * Finds coin-like closed rims without uploading pixels or requiring a model.
 * A weak or partial match deliberately returns no proposal.
 */
export function detectCoinEllipses(
  image: RgbaImageDataLike,
): CoinEllipseDetectionResult {
  const prepared = prepareImage(image);
  if (!prepared)
    return { status: "no_confident_proposal", reason: "invalid_image" };
  if (prepared.edgeThreshold <= 0)
    return { status: "no_confident_proposal", reason: "no_edges" };

  const edgePoints = collectEdgePoints(prepared);
  if (edgePoints.length < 48)
    return { status: "no_confident_proposal", reason: "no_edges" };

  const centerCandidates = voteForCenters(prepared, edgePoints);
  if (centerCandidates.length === 0)
    return { status: "no_confident_proposal", reason: "no_round_rim" };

  const candidates: WorkingCandidate[] = [];
  for (const center of centerCandidates) {
    const candidate = searchAtCenter(prepared, center);
    if (candidate) candidates.push(refineCandidate(prepared, candidate));
  }

  const distinct = deduplicateCandidates(candidates)
    .filter(
      ({ rim }) =>
        !rim.cropped &&
        rim.coverage >= MIN_DETECTION_COVERAGE &&
        rim.normalizedResidual <= MAX_DETECTION_RESIDUAL,
    )
    .map((candidate) => ({
      candidate,
      confidence: confidenceFor(candidate.rim),
    }))
    .filter(({ confidence }) => confidence >= MIN_DETECTION_CONFIDENCE)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, MAX_PROPOSALS);

  if (distinct.length === 0) {
    const cropped = candidates.some(
      ({ rim }) => rim.cropped && rim.coverage >= MIN_DETECTION_COVERAGE * 0.65,
    );
    return {
      status: "no_confident_proposal",
      reason: cropped ? "rim_cropped" : "no_round_rim",
    };
  }

  const first = distinct[0];
  const second = distinct[1];
  if (
    first &&
    second &&
    first.confidence < 0.78 &&
    first.confidence - second.confidence < 0.025
  )
    return { status: "no_confident_proposal", reason: "ambiguous" };

  return {
    status: "proposals",
    proposals: distinct.map(({ candidate, confidence }) => ({
      proposal: toOriginalProposal(candidate, prepared.scale),
      confidence,
    })),
  };
}

/**
 * Measures image evidence around an ellipse supplied by the UI. The returned
 * quality fields come from Sobel edges around that exact ellipse; callers must
 * still pass the proposal through `assessCoinEllipse` before calibration.
 */
export function scoreCoinEllipse(
  image: RgbaImageDataLike,
  geometry: CoinEllipseGeometry,
): CoinEllipseProposal {
  if (!isValidGeometry(geometry))
    return {
      ...geometry,
      rimCoverage: 0,
      normalizedResidual: 1,
    };

  const prepared = prepareImage(image);
  if (!prepared || prepared.edgeThreshold <= 0)
    return {
      ...geometry,
      rimCoverage: 0,
      normalizedResidual: 1,
    };

  const working = toWorkingGeometry(geometry, prepared.scale);
  const rim = scoreWorkingEllipse(prepared, working);
  return {
    ...geometry,
    rimCoverage: rim.coverage,
    normalizedResidual: rim.normalizedResidual,
  };
}

/**
 * Fits a round/elliptical rim around a user-selected centre. This is the
 * low-friction fallback when the full-frame detector is distracted by other
 * circular objects; the user identifies the object, not its edge points.
 */
export function proposeCoinEllipseAtCenter(
  image: RgbaImageDataLike,
  center: PixelPoint,
): CoinEllipseProposal | null {
  if (!Number.isFinite(center.x) || !Number.isFinite(center.y)) return null;
  const prepared = prepareImage(image);
  if (!prepared || prepared.edgeThreshold <= 0) return null;
  const workingCenter = {
    x: center.x * prepared.scale,
    y: center.y * prepared.scale,
  };
  if (
    workingCenter.x < 2 ||
    workingCenter.y < 2 ||
    workingCenter.x > prepared.width - 3 ||
    workingCenter.y > prepared.height - 3
  )
    return null;
  const candidate = searchStrongestRimAtCenter(prepared, workingCenter);
  if (!candidate) return null;
  const refined = refineCandidate(prepared, candidate);
  return toOriginalProposal(refined, prepared.scale);
}

function searchStrongestRimAtCenter(
  prepared: PreparedImage,
  center: PixelPoint,
): WorkingCandidate | null {
  const minRadius = Math.max(
    MIN_WORKING_RADIUS_PX,
    Math.ceil(40 * prepared.scale),
  );
  const maxRadius = Math.floor(
    Math.min(prepared.width, prepared.height) * 0.18,
  );
  const radiusStep = Math.max(2, Math.floor((maxRadius - minRadius) / 60));
  const ratios = [1, 0.94, 0.88, 0.82, 0.76];
  const candidates: WorkingCandidate[] = [];

  for (
    let majorRadius = minRadius;
    majorRadius <= maxRadius;
    majorRadius += radiusStep
  ) {
    let bestAtRadius: WorkingCandidate | null = null;
    for (const ratio of ratios) {
      const rotations =
        ratio === 1
          ? [0]
          : [
              0,
              Math.PI / 6,
              Math.PI / 3,
              Math.PI / 2,
              (2 * Math.PI) / 3,
              (5 * Math.PI) / 6,
            ];
      for (const rotation of rotations) {
        const geometry = {
          centerX: center.x,
          centerY: center.y,
          majorRadius,
          minorRadius: majorRadius * ratio,
          rotation,
        };
        const rim = scoreWorkingEllipse(prepared, geometry, 64);
        if (!bestAtRadius || rim.score > bestAtRadius.rim.score)
          bestAtRadius = { geometry, rim };
      }
    }
    if (
      bestAtRadius &&
      !bestAtRadius.rim.cropped &&
      bestAtRadius.rim.coverage >= 0.72 &&
      bestAtRadius.rim.normalizedResidual <= 0.08 &&
      bestAtRadius.rim.score >= 0.78
    )
      candidates.push(bestAtRadius);
  }

  if (candidates.length === 0) return null;
  return candidates.sort((left, right) => right.rim.score - left.rim.score)[0];
}

function prepareImage(image: RgbaImageDataLike): PreparedImage | null {
  if (
    !Number.isInteger(image.width) ||
    !Number.isInteger(image.height) ||
    image.width < 3 ||
    image.height < 3 ||
    image.data.length !== image.width * image.height * 4
  )
    return null;

  const scale = Math.min(
    1,
    MAX_WORKING_DIMENSION / Math.max(image.width, image.height),
  );
  const width = Math.max(3, Math.round(image.width * scale));
  const height = Math.max(3, Math.round(image.height * scale));
  const grayscale = resampleGrayscale(image, width, height);
  const magnitude = new Float32Array(width * height);
  const gradientX = new Float32Array(width * height);
  const gradientY = new Float32Array(width * height);
  const nonzeroMagnitudes: number[] = [];

  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const top = (y - 1) * width + x;
      const middle = y * width + x;
      const bottom = (y + 1) * width + x;
      const gx =
        -grayscale[top - 1] +
        grayscale[top + 1] -
        2 * grayscale[middle - 1] +
        2 * grayscale[middle + 1] -
        grayscale[bottom - 1] +
        grayscale[bottom + 1];
      const gy =
        -grayscale[top - 1] -
        2 * grayscale[top] -
        grayscale[top + 1] +
        grayscale[bottom - 1] +
        2 * grayscale[bottom] +
        grayscale[bottom + 1];
      const index = middle;
      const value = Math.hypot(gx, gy);
      gradientX[index] = gx;
      gradientY[index] = gy;
      magnitude[index] = value;
      if (value >= 12) nonzeroMagnitudes.push(value);
    }
  }

  const edgeThreshold = robustEdgeThreshold(nonzeroMagnitudes);
  return {
    width,
    height,
    scale,
    magnitude,
    gradientX,
    gradientY,
    edgeThreshold,
  };
}

function resampleGrayscale(
  image: RgbaImageDataLike,
  targetWidth: number,
  targetHeight: number,
): Float32Array {
  const output = new Float32Array(targetWidth * targetHeight);
  for (let y = 0; y < targetHeight; y += 1) {
    const sourceY = Math.min(
      image.height - 1,
      Math.floor(((y + 0.5) * image.height) / targetHeight),
    );
    for (let x = 0; x < targetWidth; x += 1) {
      const sourceX = Math.min(
        image.width - 1,
        Math.floor(((x + 0.5) * image.width) / targetWidth),
      );
      const sourceIndex = (sourceY * image.width + sourceX) * 4;
      const alpha = image.data[sourceIndex + 3] / 255;
      const luminance =
        image.data[sourceIndex] * 0.2126 +
        image.data[sourceIndex + 1] * 0.7152 +
        image.data[sourceIndex + 2] * 0.0722;
      output[y * targetWidth + x] = luminance * alpha + 255 * (1 - alpha);
    }
  }
  return output;
}

function robustEdgeThreshold(values: number[]): number {
  if (values.length < 32) return 0;
  values.sort((a, b) => a - b);
  const percentile = values[Math.floor(values.length * 0.72)] ?? 0;
  return Math.max(24, percentile * 0.78);
}

function collectEdgePoints(prepared: PreparedImage): EdgePoint[] {
  const points: EdgePoint[] = [];
  const { width, height, magnitude, gradientX, gradientY, edgeThreshold } =
    prepared;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const index = y * width + x;
      const value = magnitude[index];
      if (value < edgeThreshold || !isLocalGradientMaximum(prepared, x, y))
        continue;
      points.push({
        x,
        y,
        unitX: gradientX[index] / value,
        unitY: gradientY[index] / value,
        weight: Math.min(2, value / edgeThreshold),
      });
    }
  }

  if (points.length <= 14_000) return points;
  const stride = Math.ceil(points.length / 14_000);
  return points.filter((_, index) => index % stride === 0);
}

function isLocalGradientMaximum(
  prepared: PreparedImage,
  x: number,
  y: number,
): boolean {
  const index = y * prepared.width + x;
  const gx = prepared.gradientX[index];
  const gy = prepared.gradientY[index];
  const horizontal = Math.abs(gx) >= Math.abs(gy);
  const offset = horizontal ? 1 : prepared.width;
  return (
    prepared.magnitude[index] >= prepared.magnitude[index - offset] &&
    prepared.magnitude[index] >= prepared.magnitude[index + offset]
  );
}

function voteForCenters(
  prepared: PreparedImage,
  edges: EdgePoint[],
): PixelPoint[] {
  const gridWidth = Math.ceil(prepared.width / CENTER_GRID_SIZE);
  const gridHeight = Math.ceil(prepared.height / CENTER_GRID_SIZE);
  const votes = new Float32Array(gridWidth * gridHeight);
  const minRadius = Math.max(
    MIN_WORKING_RADIUS_PX,
    Math.ceil(60 * prepared.scale),
  );
  const maxRadius = Math.floor(
    Math.min(prepared.width, prepared.height) * 0.38,
  );
  if (maxRadius <= minRadius) return [];
  const radiusStep = Math.max(3, Math.floor((maxRadius - minRadius) / 42));

  for (const edge of edges) {
    for (let radius = minRadius; radius <= maxRadius; radius += radiusStep) {
      for (const sign of [-1, 1]) {
        const centerX = edge.x + sign * edge.unitX * radius;
        const centerY = edge.y + sign * edge.unitY * radius;
        const gridX = Math.round(centerX / CENTER_GRID_SIZE);
        const gridY = Math.round(centerY / CENTER_GRID_SIZE);
        if (
          gridX < 1 ||
          gridY < 1 ||
          gridX >= gridWidth - 1 ||
          gridY >= gridHeight - 1
        )
          continue;
        votes[gridY * gridWidth + gridX] += edge.weight;
      }
    }
  }

  const ranked: Array<{ point: PixelPoint; votes: number }> = [];
  for (let gridY = 1; gridY < gridHeight - 1; gridY += 1) {
    for (let gridX = 1; gridX < gridWidth - 1; gridX += 1) {
      const index = gridY * gridWidth + gridX;
      const value = votes[index];
      if (value <= 0 || !isLocalVoteMaximum(votes, gridWidth, index)) continue;
      ranked.push({
        point: {
          x: gridX * CENTER_GRID_SIZE,
          y: gridY * CENTER_GRID_SIZE,
        },
        votes: value,
      });
    }
  }
  ranked.sort((a, b) => b.votes - a.votes);

  const selected: PixelPoint[] = [];
  for (const entry of ranked) {
    if (
      selected.some(
        (point) =>
          Math.hypot(point.x - entry.point.x, point.y - entry.point.y) < 12,
      )
    )
      continue;
    selected.push(entry.point);
    if (selected.length >= MAX_CENTER_CANDIDATES) break;
  }
  return selected;
}

function isLocalVoteMaximum(
  votes: Float32Array,
  width: number,
  index: number,
): boolean {
  const value = votes[index];
  for (const offset of [
    -width - 1,
    -width,
    -width + 1,
    -1,
    1,
    width - 1,
    width,
    width + 1,
  ]) {
    if (votes[index + offset] > value) return false;
  }
  return true;
}

function searchAtCenter(
  prepared: PreparedImage,
  center: PixelPoint,
): WorkingCandidate | null {
  const minRadius = Math.max(
    MIN_WORKING_RADIUS_PX,
    Math.ceil(60 * prepared.scale),
  );
  const maxRadius = Math.floor(
    Math.min(prepared.width, prepared.height) * 0.38,
  );
  const radiusStep = Math.max(3, Math.floor((maxRadius - minRadius) / 38));
  const ratios = [1, 0.94, 0.88, 0.82, 0.76];
  let best: WorkingCandidate | null = null;

  for (
    let majorRadius = minRadius;
    majorRadius <= maxRadius;
    majorRadius += radiusStep
  ) {
    for (const ratio of ratios) {
      const rotations =
        ratio === 1
          ? [0]
          : [
              0,
              Math.PI / 6,
              Math.PI / 3,
              Math.PI / 2,
              (2 * Math.PI) / 3,
              (5 * Math.PI) / 6,
            ];
      for (const rotation of rotations) {
        const geometry = {
          centerX: center.x,
          centerY: center.y,
          majorRadius,
          minorRadius: majorRadius * ratio,
          rotation,
        };
        const rim = scoreWorkingEllipse(prepared, geometry, 64);
        if (!best || rim.score > best.rim.score) best = { geometry, rim };
      }
    }
  }
  return best;
}

function refineCandidate(
  prepared: PreparedImage,
  initial: WorkingCandidate,
): WorkingCandidate {
  let best = initial;
  let centerStep = 3;
  let radiusStep = Math.max(2, initial.geometry.majorRadius * 0.04);
  let angleStep = Math.PI / 24;

  for (let pass = 0; pass < 3; pass += 1) {
    const ratio = best.geometry.minorRadius / best.geometry.majorRadius;
    const variants: WorkingGeometry[] = [];
    for (const dx of [-centerStep, 0, centerStep]) {
      for (const dy of [-centerStep, 0, centerStep]) {
        for (const majorDelta of [-radiusStep, 0, radiusStep]) {
          for (const ratioDelta of [-0.025, 0, 0.025]) {
            for (const rotationDelta of [-angleStep, 0, angleStep]) {
              const majorRadius = best.geometry.majorRadius + majorDelta;
              const nextRatio = clamp(ratio + ratioDelta, 0.72, 1);
              variants.push({
                centerX: best.geometry.centerX + dx,
                centerY: best.geometry.centerY + dy,
                majorRadius,
                minorRadius: majorRadius * nextRatio,
                rotation: normalizeRotation(
                  best.geometry.rotation + rotationDelta,
                ),
              });
            }
          }
        }
      }
    }
    for (const geometry of variants) {
      const rim = scoreWorkingEllipse(prepared, geometry);
      if (rim.score > best.rim.score) best = { geometry, rim };
    }
    centerStep /= 2;
    radiusStep /= 2;
    angleStep /= 2;
  }
  return best;
}

function scoreWorkingEllipse(
  prepared: PreparedImage,
  geometry: WorkingGeometry,
  sampleCount = PERIMETER_SAMPLES,
): RimScore {
  if (
    geometry.majorRadius <= 0 ||
    geometry.minorRadius <= 0 ||
    geometry.majorRadius < geometry.minorRadius
  )
    return failedRimScore(false);

  const cosine = Math.cos(geometry.rotation);
  const sine = Math.sin(geometry.rotation);
  const searchDistance = clamp(Math.round(geometry.minorRadius * 0.055), 2, 6);
  let supported = 0;
  let residualSquared = 0;
  let alignmentSum = 0;
  let croppedSamples = 0;

  for (let sample = 0; sample < sampleCount; sample += 1) {
    const angle = (sample / sampleCount) * Math.PI * 2;
    const localCosine = Math.cos(angle);
    const localSine = Math.sin(angle);
    const pointX =
      geometry.centerX +
      cosine * geometry.majorRadius * localCosine -
      sine * geometry.minorRadius * localSine;
    const pointY =
      geometry.centerY +
      sine * geometry.majorRadius * localCosine +
      cosine * geometry.minorRadius * localSine;
    const localNormalX = localCosine / geometry.majorRadius;
    const localNormalY = localSine / geometry.minorRadius;
    const normalLength = Math.hypot(localNormalX, localNormalY);
    const normalX =
      (cosine * localNormalX - sine * localNormalY) / normalLength;
    const normalY =
      (sine * localNormalX + cosine * localNormalY) / normalLength;

    if (
      pointX < 1 ||
      pointY < 1 ||
      pointX > prepared.width - 2 ||
      pointY > prepared.height - 2
    ) {
      croppedSamples += 1;
      continue;
    }

    let bestStrength = 0;
    let bestAlignment = 0;
    let bestOffset = 0;
    for (let offset = -searchDistance; offset <= searchDistance; offset += 1) {
      const x = Math.round(pointX + normalX * offset);
      const y = Math.round(pointY + normalY * offset);
      if (x < 1 || y < 1 || x >= prepared.width - 1 || y >= prepared.height - 1)
        continue;
      const index = y * prepared.width + x;
      const magnitude = prepared.magnitude[index];
      if (magnitude <= 0) continue;
      const alignment = Math.abs(
        (prepared.gradientX[index] * normalX +
          prepared.gradientY[index] * normalY) /
          magnitude,
      );
      const strength =
        Math.min(1.25, magnitude / prepared.edgeThreshold) * alignment;
      if (strength > bestStrength) {
        bestStrength = strength;
        bestAlignment = alignment;
        bestOffset = offset;
      }
    }

    if (bestStrength >= 0.58 && bestAlignment >= 0.52) {
      supported += 1;
      residualSquared += bestOffset * bestOffset;
      alignmentSum += bestAlignment;
    }
  }

  const coverage = supported / sampleCount;
  const meanAlignment = supported === 0 ? 0 : alignmentSum / supported;
  const missingPenalty = Math.max(0, 0.75 - coverage) * 0.12;
  const normalizedResidual =
    supported === 0
      ? 1
      : Math.sqrt(residualSquared / supported) / geometry.minorRadius +
        missingPenalty;
  const cropped = croppedSamples > 0;
  const score =
    coverage * 0.67 +
    meanAlignment * 0.23 +
    Math.max(0, 1 - normalizedResidual / 0.08) * 0.1 -
    (cropped ? 0.2 : 0);
  return {
    coverage,
    normalizedResidual,
    meanAlignment,
    score,
    cropped,
  };
}

function failedRimScore(cropped: boolean): RimScore {
  return {
    coverage: 0,
    normalizedResidual: 1,
    meanAlignment: 0,
    score: 0,
    cropped,
  };
}

function deduplicateCandidates(
  candidates: WorkingCandidate[],
): WorkingCandidate[] {
  const ranked = [...candidates].sort((a, b) => b.rim.score - a.rim.score);
  const selected: WorkingCandidate[] = [];
  for (const candidate of ranked) {
    const duplicate = selected.some((existing) => {
      const centerDistance = Math.hypot(
        existing.geometry.centerX - candidate.geometry.centerX,
        existing.geometry.centerY - candidate.geometry.centerY,
      );
      const radiusDifference = Math.abs(
        existing.geometry.majorRadius - candidate.geometry.majorRadius,
      );
      return (
        centerDistance < candidate.geometry.minorRadius * 0.35 &&
        radiusDifference < candidate.geometry.majorRadius * 0.25
      );
    });
    if (!duplicate) selected.push(candidate);
  }
  return selected;
}

function confidenceFor(rim: RimScore): number {
  return clamp(
    0.58 * rim.coverage +
      0.27 * rim.meanAlignment +
      0.15 * Math.max(0, 1 - rim.normalizedResidual / 0.08),
    0,
    1,
  );
}

function toOriginalProposal(
  candidate: WorkingCandidate,
  scale: number,
): CoinEllipseProposal {
  return {
    center: {
      x: candidate.geometry.centerX / scale,
      y: candidate.geometry.centerY / scale,
    },
    majorRadiusPx: candidate.geometry.majorRadius / scale,
    minorRadiusPx: candidate.geometry.minorRadius / scale,
    rotationRadians: normalizeRotation(candidate.geometry.rotation),
    rimCoverage: candidate.rim.coverage,
    normalizedResidual: candidate.rim.normalizedResidual,
  };
}

function toWorkingGeometry(
  geometry: CoinEllipseGeometry,
  scale: number,
): WorkingGeometry {
  return {
    centerX: geometry.center.x * scale,
    centerY: geometry.center.y * scale,
    majorRadius: geometry.majorRadiusPx * scale,
    minorRadius: geometry.minorRadiusPx * scale,
    rotation: geometry.rotationRadians,
  };
}

function isValidGeometry(geometry: CoinEllipseGeometry): boolean {
  return (
    Number.isFinite(geometry.center.x) &&
    Number.isFinite(geometry.center.y) &&
    Number.isFinite(geometry.majorRadiusPx) &&
    Number.isFinite(geometry.minorRadiusPx) &&
    Number.isFinite(geometry.rotationRadians) &&
    geometry.majorRadiusPx > 0 &&
    geometry.minorRadiusPx > 0 &&
    geometry.majorRadiusPx >= geometry.minorRadiusPx
  );
}

function normalizeRotation(rotation: number): number {
  const halfTurn = Math.PI;
  return ((rotation % halfTurn) + halfTurn) % halfTurn;
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}
