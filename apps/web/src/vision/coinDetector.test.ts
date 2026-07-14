import { describe, expect, it } from "vitest";
import { assessCoinEllipse } from "./coinCalibration";
import {
  detectCoinEllipses,
  proposeCoinEllipseAtCenter,
  scoreCoinEllipse,
  type CoinEllipseGeometry,
  type RgbaImageDataLike,
} from "./coinDetector";

interface SyntheticEllipse extends CoinEllipseGeometry {
  value?: number;
}

function createImage(
  width: number,
  height: number,
  ellipses: SyntheticEllipse[] = [],
): RgbaImageDataLike {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      let value = 232;
      for (const ellipse of ellipses) {
        if (insideEllipse(x, y, ellipse)) value = ellipse.value ?? 78;
      }
      const index = (y * width + x) * 4;
      data[index] = value;
      data[index + 1] = value;
      data[index + 2] = value;
      data[index + 3] = 255;
    }
  }
  return { data, width, height };
}

function insideEllipse(
  x: number,
  y: number,
  ellipse: CoinEllipseGeometry,
): boolean {
  const deltaX = x - ellipse.center.x;
  const deltaY = y - ellipse.center.y;
  const cosine = Math.cos(ellipse.rotationRadians);
  const sine = Math.sin(ellipse.rotationRadians);
  const localX = cosine * deltaX + sine * deltaY;
  const localY = -sine * deltaX + cosine * deltaY;
  return (
    (localX * localX) / (ellipse.majorRadiusPx * ellipse.majorRadiusPx) +
      (localY * localY) / (ellipse.minorRadiusPx * ellipse.minorRadiusPx) <=
    1
  );
}

function addDistractors(image: RgbaImageDataLike): void {
  for (let y = 28; y < image.height - 28; y += 1) {
    setPixel(image, 38, y, 18);
    setPixel(image, 39, y, 18);
  }
  for (let x = 20; x < image.width - 18; x += 1) {
    setPixel(image, x, 42, 142);
    setPixel(image, x, 43, 142);
  }
  for (let offset = 0; offset < 95; offset += 1) {
    setPixel(image, 275 + offset, 190 + Math.floor(offset * 0.35), 25);
  }
}

function setPixel(
  image: RgbaImageDataLike,
  x: number,
  y: number,
  value: number,
): void {
  if (x < 0 || y < 0 || x >= image.width || y >= image.height) return;
  const index = (y * image.width + x) * 4;
  image.data[index] = value;
  image.data[index + 1] = value;
  image.data[index + 2] = value;
  image.data[index + 3] = 255;
}

function expectProposal(result: ReturnType<typeof detectCoinEllipses>) {
  expect(result.status).toBe("proposals");
  if (result.status !== "proposals")
    throw new Error(`Expected proposal, received ${result.reason}`);
  return result.proposals[0];
}

describe("automatic coin ellipse proposals", () => {
  it("detects a clear circular rim and returns calibration-compatible evidence", () => {
    const target: CoinEllipseGeometry = {
      center: { x: 178, y: 152 },
      majorRadiusPx: 78,
      minorRadiusPx: 78,
      rotationRadians: 0,
    };
    const image = createImage(420, 320, [target]);
    const detected = expectProposal(detectCoinEllipses(image));

    expect(detected).toBeDefined();
    expect(detected!.proposal.center.x).toBeCloseTo(target.center.x, -0.5);
    expect(detected!.proposal.center.y).toBeCloseTo(target.center.y, -0.5);
    expect(
      Math.abs(detected!.proposal.majorRadiusPx - target.majorRadiusPx),
    ).toBeLessThan(4);
    expect(detected!.proposal.rimCoverage).toBeGreaterThanOrEqual(0.78);
    expect(detected!.confidence).toBeGreaterThanOrEqual(0.68);
    expect(assessCoinEllipse(detected!.proposal, image)).toMatchObject({
      status: "accepted",
    });
  });

  it("finds a rotated ellipse despite strong straight-edge distractors", () => {
    const target: CoinEllipseGeometry = {
      center: { x: 218, y: 172 },
      majorRadiusPx: 92,
      minorRadiusPx: 72,
      rotationRadians: Math.PI / 5,
    };
    const image = createImage(460, 350, [target]);
    addDistractors(image);
    const detected = expectProposal(detectCoinEllipses(image));

    expect(detected!.proposal.center.x).toBeCloseTo(target.center.x, -1);
    expect(detected!.proposal.center.y).toBeCloseTo(target.center.y, -1);
    expect(detected!.proposal.majorRadiusPx).toBeCloseTo(
      target.majorRadiusPx,
      -1,
    );
    expect(detected!.proposal.minorRadiusPx).toBeCloseTo(
      target.minorRadiusPx,
      -1,
    );
    expect(detected!.proposal.rimCoverage).toBeGreaterThanOrEqual(0.78);
  });

  it("scores evidence for a user-adjusted ellipse instead of inventing quality", () => {
    const target: CoinEllipseGeometry = {
      center: { x: 170, y: 145 },
      majorRadiusPx: 80,
      minorRadiusPx: 72,
      rotationRadians: 0.22,
    };
    const image = createImage(360, 300, [target]);
    const aligned = scoreCoinEllipse(image, target);
    const misplaced = scoreCoinEllipse(image, {
      ...target,
      center: { x: 220, y: 110 },
    });

    expect(aligned.rimCoverage).toBeGreaterThan(0.85);
    expect(aligned.normalizedResidual).toBeLessThan(0.04);
    expect(misplaced.rimCoverage).toBeLessThan(0.5);
  });

  it("fits the rim after one centre selection despite distant distractors", () => {
    const target: CoinEllipseGeometry = {
      center: { x: 310, y: 215 },
      majorRadiusPx: 54,
      minorRadiusPx: 50,
      rotationRadians: 0.18,
    };
    const image = createImage(480, 340, [
      { ...target },
      {
        center: { x: 95, y: 95 },
        majorRadiusPx: 88,
        minorRadiusPx: 88,
        rotationRadians: 0,
        value: 20,
      },
    ]);
    const proposal = proposeCoinEllipseAtCenter(image, target.center);

    expect(proposal).not.toBeNull();
    expect(proposal!.center.x).toBeCloseTo(target.center.x, -1);
    expect(proposal!.center.y).toBeCloseTo(target.center.y, -1);
    expect(proposal!.majorRadiusPx).toBeCloseTo(target.majorRadiusPx, -1);
  });

  it("fails closed when the visible rim is cropped", () => {
    const image = createImage(360, 280, [
      {
        center: { x: 28, y: 135 },
        majorRadiusPx: 88,
        minorRadiusPx: 78,
        rotationRadians: 0.2,
      },
    ]);
    const result = detectCoinEllipses(image);

    expect(result.status).toBe("no_confident_proposal");
    if (result.status === "no_confident_proposal")
      expect(["rim_cropped", "no_round_rim"]).toContain(result.reason);
  });

  it("returns no proposal when the image has no edges", () => {
    expect(detectCoinEllipses(createImage(320, 240))).toEqual({
      status: "no_confident_proposal",
      reason: "no_edges",
    });
  });
});
