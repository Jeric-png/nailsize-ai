export const captureTypes = [
  "left_fingers",
  "left_thumb",
  "right_fingers",
  "right_thumb",
] as const;

export type CaptureType = (typeof captureTypes)[number];
export type Digit = "thumb" | "index" | "middle" | "ring" | "pinky";
export type Confidence = "high" | "medium" | "low";

export const qualityIssueCodes = [
  "REFERENCE_MISSING",
  "REFERENCE_INVALID",
  "BLUR",
  "GLARE",
  "ANGLE_TOO_STEEP",
  "NAIL_CROPPED",
  "NAIL_OCCLUDED",
  "WRONG_NAIL_COUNT",
  "UNSUPPORTED_NAIL_CONDITION",
  "LOW_CONFIDENCE",
  "OUTSIDE_DEFAULT_CHART",
] as const;

export type QualityIssueCode = (typeof qualityIssueCodes)[number];

export interface QualityIssue {
  code: QualityIssueCode;
  message: string;
  correction: string;
}

export interface NailMeasurement {
  digit: Digit;
  projected_width_mm: number;
  uncertainty_mm: number;
  recommended_size: string;
  alternate_size: string | null;
  confidence: Confidence;
  contour: [number, number][];
}

export interface MeasureOkResponse {
  status: "ok";
  request_id: string;
  capture_type: CaptureType;
  measurements: NailMeasurement[];
  quality_issues: [];
  model_version: string;
  chart_id: "platform-default";
  chart_version: "1";
  processing_ms: number;
}

export interface MeasureRetakeResponse {
  status: "retake";
  request_id: string;
  capture_type: CaptureType;
  measurements: [];
  quality_issues: QualityIssue[];
  model_version: string;
  chart_id: "platform-default";
  chart_version: "1";
  processing_ms: number;
}

export type MeasureResponse = MeasureOkResponse | MeasureRetakeResponse;
