// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as imagePreparation from "../imagePreparation";
import type {
  AutomaticHandAnalysis,
  AutomaticPhotoAnalyzer,
} from "../vision/automaticAnalysisTypes";
import { SingleNailSizing } from "./SingleNailSizing";

vi.mock("./AutomaticReviewSurface", () => ({
  AutomaticReviewSurface: ({
    onWidthLineChange,
  }: {
    onWidthLineChange: (
      digit: "thumb",
      line: {
        start: { x: number; y: number };
        end: { x: number; y: number };
      },
    ) => void;
  }) => (
    <div aria-label="Detected nail overlay">
      <button
        type="button"
        onClick={() =>
          onWidthLineChange("thumb", {
            start: { x: 100, y: 100 },
            end: { x: 300, y: 100 },
          })
        }
      >
        Move outside supported width
      </button>
      <button
        type="button"
        onClick={() =>
          onWidthLineChange("thumb", {
            start: { x: 100, y: 100 },
            end: { x: 200, y: 100 },
          })
        }
      >
        Restore supported width
      </button>
    </div>
  ),
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

afterEach(cleanup);

describe("single-nail sizing", () => {
  it("analyzes one photo with the selected digit and assumed reference", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: acceptedAnalysis(),
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);

    const button = screen.getByRole("button", { name: /find my nail size/i });
    const fileInput = document.querySelector('input[type="file"]')!;
    expect(fileInput.getAttribute("accept")).toMatch(
      /\.heic.*\.avif.*\.gif.*\.bmp/i,
    );
    expect(button).toBeDisabled();
    fireEvent.change(fileInput, {
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
    expect(
      screen.queryByText(/place all eight markers/i),
    ).not.toBeInTheDocument();
  });

  it("keeps the review mounted when a sidewall edit is outside 5–25 mm", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: acceptedAnalysis(),
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
    await screen.findByRole("heading", { name: /best-fit size 4/i });
    fireEvent.click(
      screen.getByRole("button", { name: /accept this result/i }),
    );
    expect(
      screen.getByRole("button", { name: /copy text-only result/i }),
    ).toBeVisible();

    fireEvent.click(
      screen.getByRole("button", { name: /move outside supported width/i }),
    );

    expect(
      screen.getByText(/outside the supported 5–25 mm range/i),
    ).toBeVisible();
    expect(
      screen.getByRole("heading", { name: /best-fit size 4/i }),
    ).toBeVisible();
    expect(screen.getByLabelText("Detected nail overlay")).toBeVisible();
    expect(
      screen.getByRole("button", { name: /accept this result/i }),
    ).toBeDisabled();
    expect(
      screen.queryByRole("button", { name: /copy text-only result/i }),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /restore supported width/i }),
    );
    expect(
      screen.queryByText(/outside the supported 5–25 mm range/i),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /accept this result/i }),
    ).toBeEnabled();
  });
});
