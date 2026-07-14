export const SG50_DIAMETER_MM = 23;
export const SG50_DIAMETER_TOLERANCE_MM = 0.1;

const MIN_PROJECTED_DIAMETER_PX = 120;
const MIN_AXIS_RATIO = 0.72;
const MAX_AXIS_RATIO = 1.02;
const MIN_RIM_COVERAGE = 0.75;
const MAX_NORMALIZED_RESIDUAL = 0.08;
const MAX_NAIL_DISTANCE_DIAMETERS = 4.5;
const MIN_PLAUSIBLE_WIDTH_MM = 5;
const MAX_PLAUSIBLE_WIDTH_MM = 25;

export interface PixelPoint {
  x: number;
  y: number;
}

export interface ImageSize {
  width: number;
  height: number;
}

export interface CoinEllipseProposal {
  center: PixelPoint;
  majorRadiusPx: number;
  minorRadiusPx: number;
  rotationRadians: number;
  rimCoverage: number;
  normalizedResidual: number;
}

export interface CoinEllipseCalibration extends CoinEllipseProposal {
  referenceId: "sg-50-cent-third-series-23mm";
  relativeUncertainty: number;
}

export type CoinCalibrationIssueCode =
  | "invalid_geometry"
  | "rim_cropped"
  | "coin_too_small"
  | "angle_too_steep"
  | "rim_incomplete"
  | "fit_uncertain";

export type CoinCalibrationAssessment =
  | { status: "accepted"; calibration: CoinEllipseCalibration }
  | {
      status: "rejected";
      code: CoinCalibrationIssueCode;
      message: string;
    };

export interface CalibratedWidth {
  widthMm: number;
  uncertaintyMm: number;
  distanceFromCoinDiameters: number;
}

export function assessCoinEllipse(
  proposal: CoinEllipseProposal,
  image: ImageSize,
): CoinCalibrationAssessment {
  if (!isValidImageSize(image) || !isValidProposal(proposal))
    return rejected(
      "invalid_geometry",
      "The detected coin outline is not usable. Select the coin again.",
    );

  const horizontalExtent = Math.hypot(
    proposal.majorRadiusPx * Math.cos(proposal.rotationRadians),
    proposal.minorRadiusPx * Math.sin(proposal.rotationRadians),
  );
  const verticalExtent = Math.hypot(
    proposal.majorRadiusPx * Math.sin(proposal.rotationRadians),
    proposal.minorRadiusPx * Math.cos(proposal.rotationRadians),
  );
  if (
    proposal.center.x - horizontalExtent < 2 ||
    proposal.center.y - verticalExtent < 2 ||
    proposal.center.x + horizontalExtent > image.width - 2 ||
    proposal.center.y + verticalExtent > image.height - 2
  )
    return rejected(
      "rim_cropped",
      "Keep the complete 50-cent coin inside the photo.",
    );

  if (proposal.minorRadiusPx * 2 < MIN_PROJECTED_DIAMETER_PX)
    return rejected(
      "coin_too_small",
      "Move closer so the coin is at least 120 pixels across.",
    );

  const axisRatio = proposal.minorRadiusPx / proposal.majorRadiusPx;
  if (axisRatio < MIN_AXIS_RATIO || axisRatio > MAX_AXIS_RATIO)
    return rejected(
      "angle_too_steep",
      "Hold the phone more directly above the flat coin and nails.",
    );

  if (proposal.rimCoverage < MIN_RIM_COVERAGE)
    return rejected(
      "rim_incomplete",
      "The complete coin rim must be clear and unobstructed.",
    );

  if (proposal.normalizedResidual > MAX_NORMALIZED_RESIDUAL)
    return rejected(
      "fit_uncertain",
      "The detected outline does not match the coin clearly. Adjust it or retake the photo.",
    );

  const manufacturingUncertainty =
    SG50_DIAMETER_TOLERANCE_MM / SG50_DIAMETER_MM;
  const resolutionUncertainty = 2 / (proposal.minorRadiusPx * 2);
  return {
    status: "accepted",
    calibration: {
      ...proposal,
      referenceId: "sg-50-cent-third-series-23mm",
      relativeUncertainty: Math.max(
        manufacturingUncertainty,
        proposal.normalizedResidual,
        resolutionUncertainty,
      ),
    },
  };
}

export function measureWidthWithCoinEllipse(
  start: PixelPoint,
  end: PixelPoint,
  calibration: CoinEllipseCalibration,
): CalibratedWidth {
  if (!isFinitePoint(start) || !isFinitePoint(end))
    throw new RangeError("Nail sidewall points must be finite image coordinates.");

  const widthMm = physicalLengthMm(
    end.x - start.x,
    end.y - start.y,
    calibration,
  );
  if (widthMm < MIN_PLAUSIBLE_WIDTH_MM || widthMm > MAX_PLAUSIBLE_WIDTH_MM)
    throw new RangeError(
      "The suggested nail width is outside the supported 5–25 mm range.",
    );

  const midpoint = {
    x: (start.x + end.x) / 2,
    y: (start.y + end.y) / 2,
  };
  const distanceMm = physicalLengthMm(
    midpoint.x - calibration.center.x,
    midpoint.y - calibration.center.y,
    calibration,
  );
  const distanceFromCoinDiameters = distanceMm / SG50_DIAMETER_MM;
  if (distanceFromCoinDiameters > MAX_NAIL_DISTANCE_DIAMETERS)
    throw new RangeError(
      "Keep the 50-cent coin beside the nails on the same flat surface.",
    );

  return {
    widthMm,
    uncertaintyMm: widthMm * calibration.relativeUncertainty,
    distanceFromCoinDiameters,
  };
}

function physicalLengthMm(
  deltaX: number,
  deltaY: number,
  calibration: CoinEllipseCalibration,
): number {
  const cosine = Math.cos(calibration.rotationRadians);
  const sine = Math.sin(calibration.rotationRadians);
  const majorComponent = cosine * deltaX + sine * deltaY;
  const minorComponent = -sine * deltaX + cosine * deltaY;
  const lengthInCoinRadii = Math.hypot(
    majorComponent / calibration.majorRadiusPx,
    minorComponent / calibration.minorRadiusPx,
  );
  return (SG50_DIAMETER_MM / 2) * lengthInCoinRadii;
}

function rejected(
  code: CoinCalibrationIssueCode,
  message: string,
): CoinCalibrationAssessment {
  return { status: "rejected", code, message };
}

function isValidImageSize(image: ImageSize): boolean {
  return (
    Number.isFinite(image.width) &&
    Number.isFinite(image.height) &&
    image.width > 0 &&
    image.height > 0
  );
}

function isValidProposal(proposal: CoinEllipseProposal): boolean {
  return (
    isFinitePoint(proposal.center) &&
    Number.isFinite(proposal.majorRadiusPx) &&
    Number.isFinite(proposal.minorRadiusPx) &&
    Number.isFinite(proposal.rotationRadians) &&
    Number.isFinite(proposal.rimCoverage) &&
    Number.isFinite(proposal.normalizedResidual) &&
    proposal.majorRadiusPx > 0 &&
    proposal.minorRadiusPx > 0 &&
    proposal.majorRadiusPx >= proposal.minorRadiusPx &&
    proposal.rimCoverage >= 0 &&
    proposal.rimCoverage <= 1 &&
    proposal.normalizedResidual >= 0
  );
}

function isFinitePoint(point: PixelPoint): boolean {
  return Number.isFinite(point.x) && Number.isFinite(point.y);
}
