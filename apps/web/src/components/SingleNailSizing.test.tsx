// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as imagePreparation from "../imagePreparation";
import type {
  AutomaticHandAnalysis,
  AutomaticPhotoAnalyzer,
} from "../vision/automaticAnalysisTypes";
import { SingleNailSizing } from "./SingleNailSizing";

vi.mock("./AutomaticReviewSurface", () => ({
  AutomaticReviewSurface: () => <div aria-label="Detected nail overlay" />,
}));

function acceptedAnalysis(): AutomaticHandAnalysis {
  return {
    side: "right",
    image: { width: 640, height: 480, data: new Uint8ClampedArray(0) },
    calibration: {
      center: { x: 120, y: 300 },
      majorRadiusPx: 70,
      minorRadiusPx: 70,
      rotationRadians: 0,
      rimCoverage: 0.95,
      normalizedResidual: 0.01,
      referenceId: "sg-50-cent-third-series-23mm",
      relativeUncertainty: 0.02,
    },
    detections: [],
    measurements: [
      {
        digit: "thumb",
        source: "automatic",
        detectionIndex: 0,
        confidence: 0.9,
        widthLine: { start: { x: 200, y: 160 }, end: { x: 230, y: 160 } },
        projectedWidthMm: 14.2,
        uncertaintyMm: 0.3,
        recommendedSize: "4",
        requiresPhysicalConfirmation: false,
        needsReview: false,
        reviewReasons: [],
      },
    ],
  };
}

beforeEach(() => {
  vi.spyOn(imagePreparation, "prepareImage").mockImplementation(
    async (file) => ({ file, width: 640, height: 480 }),
  );
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:nail"),
    revokeObjectURL: vi.fn(),
  });
});

describe("single-nail sizing", () => {
  it("analyzes one photo with the selected digit and assumed reference", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: acceptedAnalysis(),
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);

    const button = screen.getByRole("button", { name: /find my nail size/i });
    expect(button).toBeDisabled();
    fireEvent.change(document.querySelector('input[type="file"]')!, {
      target: {
        files: [new File(["nail"], "nail.jpg", { type: "image/jpeg" })],
      },
    });
    await screen.findByAltText("Selected nail preview");
    fireEvent.click(
      screen.getByRole("checkbox", { name: /exactly 23\.00 mm/i }),
    );
    expect(button).toBeEnabled();
    fireEvent.click(button);

    await screen.findByRole("heading", { name: /best-fit size 4/i });
    expect(analyzePhoto).toHaveBeenCalledWith(
      "right",
      expect.any(File),
      expect.any(Function),
      "thumb",
    );
    expect(screen.getByLabelText("Detected nail overlay")).toBeVisible();
    expect(screen.getByText(/assumed reference: 23\.00 mm/i)).toBeVisible();
  });

  it("uses one centre tap instead of opening manual rim markers", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "coin-review",
      context: {
        side: "right",
        targetDigit: "thumb",
        image: { width: 640, height: 480, data: new Uint8ClampedArray(0) },
        detections: [],
        suggestedEllipse: null,
        message: "No round rim found.",
      },
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);
    fireEvent.change(document.querySelector('input[type="file"]')!, {
      target: {
        files: [new File(["nail"], "nail.jpg", { type: "image/jpeg" })],
      },
    });
    await screen.findByAltText("Selected nail preview");
    fireEvent.click(
      screen.getByRole("checkbox", { name: /exactly 23\.00 mm/i }),
    );
    fireEvent.click(screen.getByRole("button", { name: /find my nail size/i }));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /tap the round reference once/i }),
      ).toBeVisible(),
    );
    expect(
      screen.getByRole("button", { name: /tap the centre/i }),
    ).toBeVisible();
    expect(screen.queryByText(/place all eight markers/i)).not.toBeInTheDocument();
  });
});
