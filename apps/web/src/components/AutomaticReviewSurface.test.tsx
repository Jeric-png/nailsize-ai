// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AutomaticNailMeasurement } from "../vision/automaticSizing";
import type { CoinEllipseCalibration } from "../vision/coinCalibration";
import { AutomaticReviewSurface } from "./AutomaticReviewSurface";

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

const measurement: AutomaticNailMeasurement = {
  digit: "index",
  source: "automatic",
  detectionIndex: 0,
  confidence: 0.8,
  widthLine: {
    start: { x: 100, y: 200 },
    end: { x: 220, y: 200 },
  },
  projectedWidthMm: 13,
  uncertaintyMm: 0.3,
  recommendedSize: "5",
  requiresPhysicalConfirmation: false,
  needsReview: true,
  reviewReasons: ["low outline confidence"],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("AutomaticReviewSurface", () => {
  it("moves sidewall handles in rendered pixels on a downscaled image", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({
      width: 320,
      height: 240,
      top: 0,
      right: 320,
      bottom: 240,
      left: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
    });
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      createImageData: (width: number, height: number) => ({
        data: new Uint8ClampedArray(width * height * 4),
      }),
      putImageData: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    const onWidthLineChange = vi.fn();

    render(
      <AutomaticReviewSurface
        previewUrl="blob:test"
        image={{ width: 4096, height: 3000 }}
        calibration={calibration}
        detections={[]}
        measurements={[measurement]}
        activeDigit="index"
        onSelectDigit={vi.fn()}
        onWidthLineChange={onWidthLineChange}
      />,
    );

    const first = screen.getByRole("button", {
      name: /first width marker for index nail/i,
    });
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(onWidthLineChange).toHaveBeenLastCalledWith("index", {
      start: { x: 100 + 4096 / 320, y: 200 },
      end: measurement.widthLine.end,
    });

    fireEvent.keyDown(first, { key: "ArrowDown", shiftKey: true });
    expect(onWidthLineChange).toHaveBeenLastCalledWith("index", {
      start: { x: 100, y: 200 + (3000 / 240) * 8 },
      end: measurement.widthLine.end,
    });
  });

  it("shows the detected result without editing controls when adjustment is closed", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      createImageData: (width: number, height: number) => ({
        data: new Uint8ClampedArray(width * height * 4),
      }),
      putImageData: vi.fn(),
    } as unknown as CanvasRenderingContext2D);

    render(
      <AutomaticReviewSurface
        previewUrl="blob:test"
        image={{ width: 800, height: 800 }}
        calibration={calibration}
        detections={[]}
        measurements={[measurement]}
        activeDigit="index"
        editable={false}
        onSelectDigit={vi.fn()}
        onWidthLineChange={vi.fn()}
      />,
    );

    expect(
      screen.getByAltText(/detected nail width and round reference/i),
    ).toBeVisible();
    expect(screen.getByText("Estimate")).toBeVisible();
    expect(screen.getByText("Estimate").closest("button")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /width marker/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/drag markers/i)).not.toBeInTheDocument();
  });

  it("can show only the automatic detection overlay for the simple result", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      createImageData: (width: number, height: number) => ({
        data: new Uint8ClampedArray(width * height * 4),
      }),
      putImageData: vi.fn(),
    } as unknown as CanvasRenderingContext2D);

    render(
      <AutomaticReviewSurface
        previewUrl="blob:test"
        image={{ width: 800, height: 800 }}
        calibration={calibration}
        detections={[]}
        measurements={[measurement]}
        activeDigit={null}
        editable={false}
        showDetails={false}
        onSelectDigit={vi.fn()}
        onWidthLineChange={vi.fn()}
      />,
    );

    expect(
      screen.getByAltText(/detected nail width and round reference/i),
    ).toBeVisible();
    expect(screen.queryByLabelText("Detected nails")).not.toBeInTheDocument();
    expect(screen.queryByText("Estimate")).not.toBeInTheDocument();
  });
});
