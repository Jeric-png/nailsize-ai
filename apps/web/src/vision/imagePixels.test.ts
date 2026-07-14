import { describe, expect, it } from "vitest";
import {
  MAX_ANALYSIS_EDGE,
  MAX_ANALYSIS_PIXELS,
  calculateAnalysisSize,
} from "./imagePixels";

describe("analysis image sizing", () => {
  it("keeps a small image unchanged", () => {
    expect(calculateAnalysisSize(800, 600)).toEqual({
      width: 800,
      height: 600,
    });
  });

  it("bounds both edge length and pixel count", () => {
    const result = calculateAnalysisSize(8000, 6000);
    expect(Math.max(result.width, result.height)).toBeLessThanOrEqual(
      MAX_ANALYSIS_EDGE,
    );
    expect(result.width * result.height).toBeLessThanOrEqual(
      MAX_ANALYSIS_PIXELS,
    );
    expect(result.width / result.height).toBeCloseTo(4 / 3, 2);
  });

  it("rejects invalid dimensions", () => {
    expect(() => calculateAnalysisSize(0, 100)).toThrow(RangeError);
  });
});
