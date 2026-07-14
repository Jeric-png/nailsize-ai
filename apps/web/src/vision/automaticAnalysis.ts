import type {
  AutomaticCoinCompleter,
  AutomaticPhotoAnalyzer,
  AutomaticPhotoAnalysisOutcome,
  CoinReviewContext,
} from "./automaticAnalysisTypes";
import type { Digit } from "../guidedSizing";
import {
  deriveAutomaticHandSizing,
  deriveAutomaticSingleNailSizing,
  type HandSide,
} from "./automaticSizing";
import {
  assessCoinEllipse,
  type CoinEllipseCalibration,
  type CoinEllipseProposal,
} from "./coinCalibration";
import { detectCoinEllipses, scoreCoinEllipse } from "./coinDetector";
import { decodeImageForAnalysis, type RgbaImage } from "./imagePixels";
import {
  getOnnxNailSegmenter,
  NailSegmentationRuntimeError,
} from "./onnxNailSegmenter";
import { releaseAutomaticPixels } from "./automaticMemory";
import type { YoloV8SegDetection } from "./yoloV8SegPostprocess";

export const analyzeAutomaticPhoto: AutomaticPhotoAnalyzer = async (
  side,
  file,
  onStage,
  targetDigit,
) => {
  onStage("preparing");
  const image = await decodeImageForAnalysis(file);

  onStage("finding-coin");
  const coinDetection = detectCoinEllipses(image);
  const suggestedEllipse =
    coinDetection.status === "proposals"
      ? (coinDetection.proposals[0]?.proposal ?? null)
      : null;

  const segmenter = getOnnxNailSegmenter();
  let detections: readonly YoloV8SegDetection[] = [];
  try {
    onStage("loading-model");
    await segmenter.warmup();
    onStage("finding-nails");
    detections = await segmenter.segment(image, {
      confidenceThreshold: 0.25,
      maxDetections: 10,
    });

    if (!suggestedEllipse)
      return coinReviewOutcome(
        side,
        image,
        detections,
        null,
        targetDigit,
        coinFailureMessage(
          coinDetection.status === "no_confident_proposal"
            ? coinDetection.reason
            : "no_round_rim",
        ),
      );

    const assessed = assessCoinEllipse(suggestedEllipse, image);
    if (assessed.status === "rejected")
      return coinReviewOutcome(
        side,
        image,
        detections,
        suggestedEllipse,
        targetDigit,
        assessed.message,
      );

    onStage("calculating");
    return finishSizing(
      side,
      image,
      detections,
      assessed.calibration,
      targetDigit,
      suggestedEllipse,
    );
  } catch (cause) {
    releaseAutomaticPixels(image, detections);
    if (cause instanceof NailSegmentationRuntimeError)
      return {
        status: "rejected",
        message: `${cause.message} ${cause.recovery}`,
      };
    return {
      status: "rejected",
      message:
        cause instanceof Error
          ? cause.message
          : "Local nail detection stopped unexpectedly.",
    };
  }
};

export const completeAutomaticPhotoWithCoin: AutomaticCoinCompleter = (
  context,
  proposal,
) => {
  const scored = scoreCoinEllipse(context.image, proposal);
  const assessed = assessCoinEllipse(scored, context.image);
  if (assessed.status === "rejected")
    return coinReviewOutcome(
      context.side,
      context.image,
      context.detections,
      scored,
      context.targetDigit,
      assessed.message,
    );
  return finishSizing(
    context.side,
    context.image,
    context.detections,
    assessed.calibration,
    context.targetDigit,
    scored,
  );
};

function finishSizing(
  side: HandSide,
  image: RgbaImage,
  detections: readonly YoloV8SegDetection[],
  calibration: CoinEllipseCalibration,
  targetDigit?: Digit,
  suggestedEllipse: CoinEllipseProposal | null = null,
): AutomaticPhotoAnalysisOutcome {
  const sizing = targetDigit
    ? deriveAutomaticSingleNailSizing({
        digit: targetDigit,
        image,
        detections,
        calibration,
      })
    : deriveAutomaticHandSizing({ side, image, detections, calibration });
  if (sizing.status === "rejected") {
    if (targetDigit)
      return coinReviewOutcome(
        side,
        image,
        detections,
        suggestedEllipse,
        targetDigit,
        `${sizing.message} Tap the centre of the intended round reference once.`,
      );
    releaseAutomaticPixels(image, detections);
    return sizing;
  }
  return {
    status: "accepted",
    analysis: {
      side,
      image,
      calibration,
      detections,
      measurements: sizing.measurements,
    },
  };
}

function coinReviewOutcome(
  side: HandSide,
  image: RgbaImage,
  detections: readonly YoloV8SegDetection[],
  suggestedEllipse: CoinEllipseProposal | null,
  targetDigit: Digit | undefined,
  message: string,
): AutomaticPhotoAnalysisOutcome {
  const context: CoinReviewContext = {
    side,
    image,
    detections,
    suggestedEllipse,
    targetDigit,
    message,
  };
  return { status: "coin-review", context };
}

function coinFailureMessage(reason: string) {
  switch (reason) {
    case "rim_cropped":
      return "The coin rim is cropped. Retake the photo or select a complete rim.";
    case "ambiguous":
      return "More than one round object looks like the coin. Select the 50-cent coin.";
    case "no_edges":
      return "The coin rim has too little contrast. Tap the coin or retake in even light.";
    default:
      return "The 50-cent coin was not clear enough to select automatically.";
  }
}
