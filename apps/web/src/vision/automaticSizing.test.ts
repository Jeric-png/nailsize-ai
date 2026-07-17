import { describe, expect, it } from "vitest";
import type { CoinEllipseCalibration } from "./coinCalibration";
import {
  deriveAutomaticHandSizing,
  deriveAutomaticSingleNailSizing,
  recalculateAutomaticMeasurement,
} from "./automaticSizing";
import type { YoloV8SegDetection } from "./yoloV8SegPostprocess";

const calibration: CoinEllipseCalibration = {
  center: { x: 400, y: 400 },
  majorRadiusPx: 80,
  minorRadiusPx: 80,
  rotationRadians: 0,
  rimCoverage: 0.95,
  normalizedResidual: 0.01,
  referenceId: "sg-50-cent-third-series-23mm",
  relativeUncertainty: 0.02,
};

function nailDetection(x: number, confidence = 0.9): YoloV8SegDetection {
  const width = 70;
  const height = 120;
  const binary = new Uint8Array(width * height);
  for (let y = 8; y < height - 8; y += 1) {
    const halfWidth = 25 - Math.abs(y - height / 2) / 18;
    for (
      let localX = Math.ceil(width / 2 - halfWidth);
      localX <= Math.floor(width / 2 + halfWidth);
      localX += 1
    )
      binary[y * width + localX] = 1;
  }
  const count = binary.reduce((sum, value) => sum + value, 0);
  return {
    candidateIndex: x,
    classId: 0,
    confidence,
    box: { x, y: 100, width, height },
    mask: {
      x,
      y: 100,
      width,
      height,
      binary,
      probabilities: Float32Array.from(binary),
    },
    quality: {
      foregroundPixelCount: count,
      foregroundRatio: count / binary.length,
      meanProbability: 0.7,
      meanForegroundProbability: 0.95,
      components: {
        count: 1,
        largestPixelCount: count,
        largestForegroundRatio: 1,
        largestBounds: { x, y: 108, width: 51, height: 104 },
        touchesCropEdge: false,
        largestTouchesCropEdge: false,
      },
    },
  };
}

describe("automatic hand sizing", () => {
  it("sizes one selected nail from the strongest usable proposal", () => {
    const result = deriveAutomaticSingleNailSizing({
      digit: "thumb",
      image: { width: 700, height: 600 },
      detections: [nailDetection(80, 0.4), nailDetection(280, 0.9)],
      calibration,
    });

    expect(result.status).toBe("accepted");
    if (result.status !== "accepted") return;
    expect(result.measurements).toHaveLength(1);
    expect(result.measurements[0].digit).toBe("thumb");
    expect(result.measurements[0].detectionIndex).toBe(1);
    expect(result.measurements[0]).not.toHaveProperty("alternateSize");
  });

  it("returns the closest available size for an out-of-chart photo estimate", () => {
    const result = deriveAutomaticSingleNailSizing({
      digit: "index",
      image: { width: 700, height: 600 },
      detections: [nailDetection(280)],
      calibration: {
        ...calibration,
        majorRadiusPx: 400,
        minorRadiusPx: 400,
      },
    });

    expect(result.status).toBe("accepted");
    if (result.status !== "accepted") return;
    expect(result.measurements[0].projectedWidthMm).toBeLessThan(5);
    expect(result.measurements[0].recommendedSize).toBe("9");
  });

  it("labels five left-hand nails by the required capture orientation", () => {
    const result = deriveAutomaticHandSizing({
      side: "left",
      image: { width: 700, height: 600 },
      detections: [80, 180, 280, 380, 520].map((x) => nailDetection(x)),
      calibration,
    });

    expect(result.status).toBe("accepted");
    if (result.status !== "accepted") return;
    expect(result.measurements.map(({ digit }) => digit)).toEqual([
      "pinky",
      "ring",
      "middle",
      "index",
      "thumb",
    ]);
    expect(result.measurements).toHaveLength(5);
    expect(
      result.measurements.every(({ projectedWidthMm }) =>
        Number.isFinite(projectedWidthMm),
      ),
    ).toBe(true);
  });

  it("labels a right hand in the opposite x order", () => {
    const result = deriveAutomaticHandSizing({
      side: "right",
      image: { width: 700, height: 600 },
      detections: [80, 180, 280, 380, 520].map((x) => nailDetection(x)),
      calibration,
    });
    expect(result.status).toBe("accepted");
    if (result.status !== "accepted") return;
    expect(result.measurements.map(({ digit }) => digit)).toEqual([
      "thumb",
      "index",
      "middle",
      "ring",
      "pinky",
    ]);
  });

  it("preserves original detection indexes after rejecting an unusable proposal", () => {
    const detections = [
      nailDetection(20, 0.1),
      ...[80, 180, 280, 380, 520].map((x) => nailDetection(x)),
    ];
    const result = deriveAutomaticHandSizing({
      side: "left",
      image: { width: 700, height: 600 },
      detections,
      calibration,
    });

    expect(result.status).toBe("accepted");
    if (result.status !== "accepted") return;
    expect(
      result.measurements.map(({ detectionIndex }) => detectionIndex),
    ).toEqual([1, 2, 3, 4, 5]);
  });

  it("fails closed when fewer than five clear nails are found", () => {
    const result = deriveAutomaticHandSizing({
      side: "left",
      image: { width: 700, height: 600 },
      detections: [80, 180, 280, 380].map((x) => nailDetection(x)),
      calibration,
    });
    expect(result).toEqual({
      status: "rejected",
      message:
        "Only 4 clear nails were found. Retake the photo with all five bare nails separated and visible.",
    });
  });

  it("marks low-confidence proposals for review and clears review after correction", () => {
    const result = deriveAutomaticHandSizing({
      side: "left",
      image: { width: 700, height: 600 },
      detections: [80, 180, 280, 380, 520].map((x, index) =>
        nailDetection(x, index === 2 ? 0.4 : 0.9),
      ),
      calibration,
    });
    expect(result.status).toBe("accepted");
    if (result.status !== "accepted") return;
    expect(result.needsReview).toBe(true);
    const uncertain = result.measurements.find(
      ({ needsReview }) => needsReview,
    )!;
    const corrected = recalculateAutomaticMeasurement(
      uncertain,
      uncertain.widthLine,
      calibration,
    );
    expect(corrected.needsReview).toBe(false);
    expect(corrected.source).toBe("user-corrected");
    expect(corrected.reviewReasons).toEqual([]);
  });
});
