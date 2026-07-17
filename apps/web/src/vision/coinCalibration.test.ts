import { describe, expect, it } from "vitest";
import {
  acceptBestEffortCoinEllipse,
  assessCoinEllipse,
  estimateWidthWithCoinEllipse,
  measureWidthWithCoinEllipse,
  type CoinEllipseCalibration,
  type CoinEllipseProposal,
} from "./coinCalibration";

const image = { width: 1200, height: 900 };

function proposal(
  overrides: Partial<CoinEllipseProposal> = {},
): CoinEllipseProposal {
  return {
    center: { x: 250, y: 250 },
    majorRadiusPx: 115,
    minorRadiusPx: 110,
    rotationRadians: 0,
    rimCoverage: 0.95,
    normalizedResidual: 0.015,
    ...overrides,
  };
}

function accepted(
  value: CoinEllipseProposal = proposal(),
): CoinEllipseCalibration {
  const assessment = assessCoinEllipse(value, image);
  if (assessment.status !== "accepted")
    throw new Error(`Expected accepted calibration: ${assessment.code}`);
  return assessment.calibration;
}

describe("automatic 50-cent ellipse calibration", () => {
  it("measures a circular reference in millimetres", () => {
    const calibration = accepted(
      proposal({ majorRadiusPx: 115, minorRadiusPx: 115 }),
    );
    const result = measureWidthWithCoinEllipse(
      { x: 300, y: 350 },
      { x: 370, y: 350 },
      calibration,
    );
    expect(result.widthMm).toBeCloseTo(7, 6);
    expect(result.uncertaintyMm).toBeGreaterThan(0);
  });

  it("uses the rotated ellipse as an affine scale in every direction", () => {
    const angle = Math.PI / 6;
    const calibration = accepted(
      proposal({
        center: { x: 300, y: 300 },
        majorRadiusPx: 150,
        minorRadiusPx: 110,
        rotationRadians: angle,
      }),
    );
    const expectedWidthMm = 12;
    const radiusUnits = expectedWidthMm / 11.5;
    const majorVector = {
      x: Math.cos(angle) * calibration.majorRadiusPx * radiusUnits,
      y: Math.sin(angle) * calibration.majorRadiusPx * radiusUnits,
    };
    const minorVector = {
      x: -Math.sin(angle) * calibration.minorRadiusPx * radiusUnits,
      y: Math.cos(angle) * calibration.minorRadiusPx * radiusUnits,
    };

    for (const vector of [majorVector, minorVector]) {
      const result = measureWidthWithCoinEllipse(
        { x: 400, y: 350 },
        { x: 400 + vector.x, y: 350 + vector.y },
        calibration,
      );
      expect(result.widthMm).toBeCloseTo(expectedWidthMm, 6);
    }
  });

  it("fails closed for a cropped, small, steep, incomplete, or uncertain fit", () => {
    expect(
      assessCoinEllipse(proposal({ center: { x: 20, y: 20 } }), image),
    ).toMatchObject({ status: "rejected", code: "rim_cropped" });
    expect(
      assessCoinEllipse(
        proposal({ majorRadiusPx: 70, minorRadiusPx: 59 }),
        image,
      ),
    ).toMatchObject({ status: "rejected", code: "coin_too_small" });
    expect(
      assessCoinEllipse(
        proposal({ majorRadiusPx: 160, minorRadiusPx: 100 }),
        image,
      ),
    ).toMatchObject({ status: "rejected", code: "angle_too_steep" });
    expect(
      assessCoinEllipse(proposal({ rimCoverage: 0.74 }), image),
    ).toMatchObject({ status: "rejected", code: "rim_incomplete" });
    expect(
      assessCoinEllipse(proposal({ normalizedResidual: 0.081 }), image),
    ).toMatchObject({ status: "rejected", code: "fit_uncertain" });
  });

  it("accepts a detected coin for best-effort sizing without quality questions", () => {
    const result = acceptBestEffortCoinEllipse(
      proposal({
        majorRadiusPx: 55,
        minorRadiusPx: 30,
        rimCoverage: 0.5,
        normalizedResidual: 0.1,
      }),
      image,
    );

    expect(result.status).toBe("accepted");
  });

  it("rejects implausible widths and a reference too far from the nail", () => {
    const calibration = accepted(
      proposal({ majorRadiusPx: 115, minorRadiusPx: 115 }),
    );
    expect(() =>
      measureWidthWithCoinEllipse(
        { x: 300, y: 350 },
        { x: 330, y: 350 },
        calibration,
      ),
    ).toThrow(/5–25 mm/);
    expect(() =>
      measureWidthWithCoinEllipse(
        { x: 1190, y: 800 },
        { x: 1260, y: 800 },
        calibration,
      ),
    ).toThrow(/beside/);
    expect(
      estimateWidthWithCoinEllipse(
        { x: 300, y: 350 },
        { x: 330, y: 350 },
        calibration,
      ).widthMm,
    ).toBeLessThan(5);
  });

  it("includes the larger fit, resolution, or coin-tolerance uncertainty", () => {
    const fitLimited = accepted(proposal({ normalizedResidual: 0.03 }));
    expect(fitLimited.relativeUncertainty).toBeCloseTo(0.03, 8);

    const resolutionLimited = accepted(
      proposal({
        majorRadiusPx: 62,
        minorRadiusPx: 60,
        normalizedResidual: 0.001,
      }),
    );
    expect(resolutionLimited.relativeUncertainty).toBeCloseTo(1 / 60, 8);
  });
});
