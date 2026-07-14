import type { AutomaticNailMeasurement, HandSide } from "./automaticSizing";
import type { Digit } from "../guidedSizing";
import type {
  CoinEllipseCalibration,
  CoinEllipseProposal,
} from "./coinCalibration";
import type { RgbaImage } from "./imagePixels";
import type { YoloV8SegDetection } from "./yoloV8SegPostprocess";

export type AutomaticAnalysisStage =
  | "preparing"
  | "loading-model"
  | "finding-nails"
  | "finding-coin"
  | "calculating";

export interface AutomaticHandAnalysis {
  readonly side: HandSide;
  readonly image: RgbaImage;
  readonly calibration: CoinEllipseCalibration;
  readonly detections: readonly YoloV8SegDetection[];
  readonly measurements: readonly AutomaticNailMeasurement[];
}

export interface CoinReviewContext {
  readonly side: HandSide;
  readonly image: RgbaImage;
  readonly detections: readonly YoloV8SegDetection[];
  readonly suggestedEllipse: CoinEllipseProposal | null;
  readonly message: string;
  readonly targetDigit?: Digit;
}

export type AutomaticPhotoAnalysisOutcome =
  | { readonly status: "accepted"; readonly analysis: AutomaticHandAnalysis }
  | { readonly status: "coin-review"; readonly context: CoinReviewContext }
  | { readonly status: "rejected"; readonly message: string };

export type AutomaticPhotoAnalyzer = (
  side: HandSide,
  file: Blob,
  onStage: (stage: AutomaticAnalysisStage) => void,
  targetDigit?: Digit,
) => Promise<AutomaticPhotoAnalysisOutcome>;

export type AutomaticCoinCompleter = (
  context: CoinReviewContext,
  proposal: CoinEllipseProposal,
) => AutomaticPhotoAnalysisOutcome;
