import type {
  AutomaticHandAnalysis,
  AutomaticPhotoAnalysisOutcome,
  CoinReviewContext,
} from "./automaticAnalysisTypes";
import type { RgbaImage } from "./imagePixels";
import type { YoloV8SegDetection } from "./yoloV8SegPostprocess";

export function releaseAutomaticAnalysis(
  analysis: AutomaticHandAnalysis,
): void {
  releaseAutomaticPixels(analysis.image, analysis.detections);
}

export function releaseCoinReviewContext(context: CoinReviewContext): void {
  releaseAutomaticPixels(context.image, context.detections);
}

export function releaseAutomaticOutcome(
  outcome: AutomaticPhotoAnalysisOutcome,
): void {
  if (outcome.status === "accepted") releaseAutomaticAnalysis(outcome.analysis);
  if (outcome.status === "coin-review")
    releaseCoinReviewContext(outcome.context);
}

export function releaseAutomaticPixels(
  image: RgbaImage,
  detections: readonly YoloV8SegDetection[],
): void {
  image.data.fill(0);
  for (const detection of detections) {
    detection.mask.probabilities.fill(0);
    detection.mask.binary.fill(0);
  }
}
