import { describe, expect, it } from "vitest";
import {
  COIN_REFERENCE_ID,
  compareSamples,
  createDefaultCoinMarkers,
  createInitialCoinMarkers,
  formatRepeatDeltaMm,
  isCaptureConsistent,
  measureSample,
  recommendSize,
  validateCoinCalibration,
  validateRenderedCoinSize,
  type EdgePair,
  type ImageDimensions,
  type SampleMeasurement,
} from "./guidedSizing";

const portrait: ImageDimensions = { width: 600, height: 800 };
const landscape: ImageDimensions = { width: 800, height: 600 };

function defaultCoinGeometry(dimensions: ImageDimensions) {
  const markers = createDefaultCoinMarkers(dimensions);
  const right = {
    x: markers[2].x * dimensions.width,
    y: markers[2].y * dimensions.height,
  };
  const left = {
    x: markers[6].x * dimensions.width,
    y: markers[6].y * dimensions.height,
  };
  return {
    markers,
    center: { x: (right.x + left.x) / 2, y: (right.y + left.y) / 2 },
    diameterPx: Math.hypot(right.x - left.x, right.y - left.y),
  };
}

function circularCoinMarkers(dimensions: ImageDimensions, diameterPx: number) {
  const centerPx = {
    x: dimensions.width * 0.23,
    y: dimensions.height * 0.22,
  };
  return Array.from({ length: 8 }, (_, index) => {
    const angle = -Math.PI / 2 + index * (Math.PI / 4);
    return {
      x: (centerPx.x + Math.cos(angle) * (diameterPx / 2)) / dimensions.width,
      y: (centerPx.y + Math.sin(angle) * (diameterPx / 2)) / dimensions.height,
    };
  }) as ReturnType<typeof createDefaultCoinMarkers>;
}

function horizontalEdges(
  widthMm: number,
  dimensions: ImageDimensions,
  start = { x: 0.43, y: 0.4 },
  coinDiameterPx = defaultCoinGeometry(dimensions).diameterPx,
): EdgePair {
  const widthPx = (widthMm / 23) * coinDiameterPx;
  return [start, { x: start.x + widthPx / dimensions.width, y: start.y }];
}

function readings(widths: number[]): SampleMeasurement[] {
  const digits = ["index", "middle", "ring", "pinky"] as const;
  return digits.map((digit, index) => ({
    digit,
    widthMm: widths[index],
    edges: [
      { x: 0.2, y: 0.2 },
      { x: 0.3, y: 0.2 },
    ],
  }));
}

describe("Singapore 50-cent coin calibration", () => {
  it("converts portrait and landscape image coordinates through source pixels", () => {
    for (const dimensions of [portrait, landscape]) {
      const [measurement] = measureSample(
        dimensions,
        createDefaultCoinMarkers(dimensions),
        { thumb: horizontalEdges(14, dimensions) },
        ["thumb"],
      );
      expect(measurement.widthMm).toBeCloseTo(14, 2);
    }
  });

  it("accepts an evenly marked circular reference at the minimum scale", () => {
    expect(
      validateCoinCalibration(createDefaultCoinMarkers(portrait), portrait),
    ).toBeNull();
    expect(
      validateCoinCalibration(createDefaultCoinMarkers(landscape), landscape),
    ).toBeNull();
  });

  it("starts from an invalid holding layout that cannot become a scale by nudging", () => {
    const staged = createInitialCoinMarkers(portrait);
    expect(validateCoinCalibration(staged, portrait)).not.toBeNull();
    staged.forEach((point) => {
      point.x += 1 / portrait.width;
    });
    expect(validateCoinCalibration(staged, portrait)).not.toBeNull();
  });

  it("requires enough rendered coin size for usable manual annotation", () => {
    expect(
      validateRenderedCoinSize(createDefaultCoinMarkers(portrait), {
        width: 338,
        height: 451,
      }),
    ).toBeNull();

    const highResolutionWide = { width: 4096, height: 1000 };
    const markers = createDefaultCoinMarkers(highResolutionWide);
    expect(validateCoinCalibration(markers, highResolutionWide)).toBeNull();
    expect(
      validateRenderedCoinSize(markers, { width: 350, height: 85.45 }),
    ).toMatch(/120 screen pixels/);
  });

  it("rejects a small, cropped, uneven, or oval-looking reference", () => {
    const small = { width: 300, height: 300 };
    expect(
      validateCoinCalibration(createDefaultCoinMarkers(small), small),
    ).toMatch(/120 pixels/);

    const cropped = createDefaultCoinMarkers(portrait);
    cropped[0] = { x: 0, y: 0 };
    expect(validateCoinCalibration(cropped, portrait)).toMatch(/complete coin/);

    const oval = createDefaultCoinMarkers(portrait);
    oval.forEach((point) => {
      point.y = 0.22 + (point.y - 0.22) * 0.7;
    });
    expect(validateCoinCalibration(oval, portrait)).toMatch(/oval/);

    const misordered = createDefaultCoinMarkers(portrait);
    [misordered[1], misordered[2]] = [misordered[2], misordered[1]];
    expect(validateCoinCalibration(misordered, portrait)).toMatch(
      /clockwise|evenly/,
    );
  });

  it("accepts exactly 8% diameter spread and rejects a value above it", () => {
    function withHorizontalDiameterFactor(factor: number) {
      const { markers, center, diameterPx } = defaultCoinGeometry(portrait);
      const radiusPx = (diameterPx / 2) * factor;
      markers[2].x = (center.x + radiusPx) / portrait.width;
      markers[6].x = (center.x - radiusPx) / portrait.width;
      return markers;
    }

    expect(
      validateCoinCalibration(withHorizontalDiameterFactor(1.08), portrait),
    ).toBeNull();
    expect(
      validateCoinCalibration(withHorizontalDiameterFactor(1.081), portrait),
    ).toMatch(/oval/);
  });

  it("accepts exactly 6% opposite-centre spread and rejects above it", () => {
    function withHorizontalPairOffset(centerSpread: number) {
      const { markers, diameterPx } = defaultCoinGeometry(portrait);
      const pairOffsetPx = (centerSpread * diameterPx * 4) / 3;
      markers[2].x += pairOffsetPx / portrait.width;
      markers[6].x += pairOffsetPx / portrait.width;
      return markers;
    }

    expect(
      validateCoinCalibration(withHorizontalPairOffset(0.06), portrait),
    ).toBeNull();
    expect(
      validateCoinCalibration(withHorizontalPairOffset(0.061), portrait),
    ).toMatch(/one centre/);
  });

  it("rejects implausible nail markers and a reference too far away", () => {
    const markers = createDefaultCoinMarkers(portrait);
    expect(() =>
      measureSample(
        portrait,
        markers,
        { thumb: horizontalEdges(2, portrait) },
        ["thumb"],
      ),
    ).toThrow(/sidewalls/);

    expect(() =>
      measureSample(
        portrait,
        circularCoinMarkers(portrait, 120),
        {
          thumb: horizontalEdges(14, portrait, { x: 0.82, y: 0.9 }, 120),
        },
        ["thumb"],
      ),
    ).toThrow(/beside/);
  });

  it("accepts 5–25 mm inclusive and rejects values outside that span", () => {
    const markers = createDefaultCoinMarkers(portrait);
    for (const widthMm of [5, 25])
      expect(
        measureSample(
          portrait,
          markers,
          { thumb: horizontalEdges(widthMm, portrait) },
          ["thumb"],
        )[0].widthMm,
      ).toBeCloseTo(widthMm, 6);

    for (const widthMm of [4.999, 25.001])
      expect(() =>
        measureSample(
          portrait,
          markers,
          { thumb: horizontalEdges(widthMm, portrait) },
          ["thumb"],
        ),
      ).toThrow(/sidewalls/);
  });

  it("accepts a nail at 4.5 coin diameters and rejects one beyond it", () => {
    const markers = circularCoinMarkers(portrait, 120);
    const coinCenter = {
      x: portrait.width * 0.23,
      y: portrait.height * 0.22,
    };
    const coinDiameterPx = 120;
    function edgesAtDistance(distanceInCoinDiameters: number): EdgePair {
      const nailCenter = {
        x: coinCenter.x,
        y: coinCenter.y + coinDiameterPx * distanceInCoinDiameters,
      };
      const nailWidthPx = (14 / 23) * coinDiameterPx;
      return [
        {
          x: (nailCenter.x - nailWidthPx / 2) / portrait.width,
          y: nailCenter.y / portrait.height,
        },
        {
          x: (nailCenter.x + nailWidthPx / 2) / portrait.width,
          y: nailCenter.y / portrait.height,
        },
      ];
    }

    expect(
      measureSample(portrait, markers, { thumb: edgesAtDistance(4.5) }, [
        "thumb",
      ])[0].widthMm,
    ).toBeCloseTo(14, 2);
    expect(() =>
      measureSample(portrait, markers, { thumb: edgesAtDistance(4.501) }, [
        "thumb",
      ]),
    ).toThrow(/beside/);
  });
});

describe("repeatability and size mapping", () => {
  it("uses raw measured widths for repeat and chart decisions", () => {
    const markers = createDefaultCoinMarkers(portrait);
    const first = measureSample(
      portrait,
      markers,
      { thumb: horizontalEdges(10.0051, portrait) },
      ["thumb"],
    );
    const verification = measureSample(
      portrait,
      markers,
      { thumb: horizontalEdges(10.6141, portrait) },
      ["thumb"],
    );
    expect(first[0].widthMm).toBeCloseTo(10.0051, 6);
    expect(
      compareSamples("left_thumb", first, verification).measurements[0]
        .consistent,
    ).toBe(false);

    const justAboveBoundary = measureSample(
      portrait,
      markers,
      { thumb: horizontalEdges(15.0001, portrait) },
      ["thumb"],
    );
    expect(
      compareSamples("left_thumb", justAboveBoundary, justAboveBoundary)
        .measurements[0].recommendedSize,
    ).toBe("2");
  });

  it("averages two consistent observations and records their spread", () => {
    const result = compareSamples(
      "left_fingers",
      readings([14, 13, 12, 10]),
      readings([14.4, 13.2, 11.5, 10.6]),
    );

    expect(isCaptureConsistent(result)).toBe(true);
    expect(result).toMatchObject({
      calibrationReference: COIN_REFERENCE_ID,
      methodVersion: "guided-sg50-coin-v1",
    });
    expect(result.measurements[0]).toMatchObject({
      digit: "index",
      projectedWidthMm: 14.2,
      sizingWidthMm: 14.4,
      recommendedSize: "3",
      consistent: true,
    });
    expect(result.measurements[0].repeatDeltaMm).toBeCloseTo(0.4, 10);
    expect(result.measurements[3].repeatDeltaMm).toBeCloseTo(0.6, 10);
  });

  it("fails the capture group when one nail exceeds the repeat tolerance", () => {
    const result = compareSamples(
      "right_fingers",
      readings([14, 13, 12, 10]),
      readings([14.7, 13, 12, 10]),
    );

    expect(isCaptureConsistent(result)).toBe(false);
    expect(result.measurements[0].repeatDeltaMm).toBeCloseTo(0.7, 10);
    expect(result.measurements[0].consistent).toBe(false);
  });

  it("does not display a just-over-limit failure as the allowed boundary", () => {
    const result = compareSamples(
      "right_fingers",
      readings([14, 13, 12, 10]),
      readings([14.61, 13, 12, 10]),
    );

    expect(result.measurements[0].repeatDeltaMm).toBeCloseTo(0.61, 10);
    expect(result.measurements[0].consistent).toBe(false);
  });

  it("accepts an exact 0.60 mm repeat delta despite floating-point noise", () => {
    const result = compareSamples(
      "right_fingers",
      readings([10.01, 13, 12, 10]),
      readings([10.61, 13, 12, 10]),
    );

    expect(result.measurements[0].repeatDeltaMm).toBeCloseTo(0.6, 10);
    expect(result.measurements[0].consistent).toBe(true);
  });

  it("does not format a just-over-limit failure as exactly 0.60 mm", () => {
    const result = compareSamples(
      "right_fingers",
      readings([10, 13, 12, 10]),
      readings([10.6001, 13, 12, 10]),
    );
    const measurement = result.measurements[0];

    expect(measurement.consistent).toBe(false);
    expect(
      formatRepeatDeltaMm(measurement.repeatDeltaMm, measurement.consistent),
    ).toBe("> 0.60");
    expect(formatRepeatDeltaMm(0.6, true)).toBe("0.60");
  });

  it("chooses the narrowest tip that is not narrower than the reading", () => {
    expect(recommendSize(18)).toBe("0");
    expect(recommendSize(14.2)).toBe("3");
    expect(recommendSize(15.2)).toBe("2");
    expect(recommendSize(8.9)).toBeNull();
    expect(recommendSize(18.1)).toBeNull();
  });

  it("uses the wider repeat for the press-on recommendation", () => {
    const result = compareSamples(
      "left_thumb",
      [
        {
          digit: "thumb",
          widthMm: 14.8,
          edges: horizontalEdges(14.8, portrait),
        },
      ],
      [
        {
          digit: "thumb",
          widthMm: 15.2,
          edges: horizontalEdges(15.2, portrait),
        },
      ],
    );

    expect(result.measurements[0]).toMatchObject({
      projectedWidthMm: 15,
      sizingWidthMm: 15.2,
      recommendedSize: "2",
      requiresPhysicalConfirmation: true,
    });
    expect(result.measurements[0]).not.toHaveProperty("alternateSize");
  });

  it("fails closed instead of inventing a size outside the provisional chart", () => {
    for (const [firstWidthMm, verificationWidthMm] of [
      [18.4, 18.6],
      [8.6, 8.8],
    ]) {
      const result = compareSamples(
        "left_thumb",
        [
          {
            digit: "thumb",
            widthMm: firstWidthMm,
            edges: horizontalEdges(firstWidthMm, portrait),
          },
        ],
        [
          {
            digit: "thumb",
            widthMm: verificationWidthMm,
            edges: horizontalEdges(verificationWidthMm, portrait),
          },
        ],
      );

      expect(result.measurements[0]).toMatchObject({
        consistent: true,
        recommendedSize: null,
        requiresPhysicalConfirmation: false,
      });
    }
  });
});
