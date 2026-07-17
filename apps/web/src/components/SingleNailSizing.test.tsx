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
    editable,
    showDetails,
  }: {
    editable?: boolean;
    showDetails?: boolean;
  }) => (
    <div
      aria-label="Detected nail overlay"
      data-editable={String(editable)}
      data-show-details={String(showDetails)}
    />
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
        digit: "index",
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

function uploadPhoto() {
  fireEvent.change(document.querySelector('input[type="file"]')!, {
    target: {
      files: [new File(["nail"], "nail.jpg", { type: "image/jpeg" })],
    },
  });
}

async function uploadAndAnalyze() {
  uploadPhoto();
  await screen.findByAltText("Selected nail preview");
  fireEvent.click(screen.getByRole("button", { name: /get my nail size/i }));
}

beforeEach(() => {
  vi.spyOn(imagePreparation, "prepareImage").mockImplementation(
    async (file) => ({ file, width: 640, height: 480 }),
  );
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn(() => "blob:nail"),
    revokeObjectURL: vi.fn(),
  });
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

afterEach(cleanup);

describe("single-nail sizing", () => {
  it("needs only one photo and one action to show a recommended size", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: acceptedAnalysis(),
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);

    expect(
      screen.getByRole("heading", { name: /upload one photo/i }),
    ).toBeVisible();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /get my nail size/i }),
    ).toBeDisabled();
    const input = document.querySelector('input[type="file"]')!;
    expect(input.getAttribute("accept")).toMatch(
      /\.heic.*\.avif.*\.gif.*\.bmp/i,
    );

    await uploadAndAnalyze();

    await screen.findByRole("heading", {
      name: /recommended press-on size: 4/i,
    });
    expect(screen.getByText(/reference width:/i)).toHaveTextContent(
      "Reference width: 14 mm",
    );
    expect(analyzePhoto).toHaveBeenCalledWith(
      "right",
      expect.any(File),
      expect.any(Function),
      "index",
    );
    const preview = screen.getByLabelText("Detected nail overlay");
    expect(preview).toHaveAttribute("data-editable", "false");
    expect(preview).toHaveAttribute("data-show-details", "false");
    expect(
      screen.queryByRole("button", { name: /adjust|save|keep detected/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/millimet|uncertain|check width/i),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /copy size/i }));
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        "Recommended press-on nail size: 4\nReference width: 14 mm",
      ),
    );
    expect(screen.getByText("Size copied.")).toBeVisible();
  });

  it("turns an automatic coin miss into one plain retry action", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "coin-review",
      context: {
        side: "right",
        targetDigit: "index",
        image: { width: 640, height: 480, data: new Uint8ClampedArray(0) },
        detections: [],
        suggestedEllipse: null,
        message: "No round rim found.",
      },
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);

    await uploadAndAnalyze();

    expect(
      await screen.findByText(
        /could not clearly find both the nail and 50-cent coin/i,
      ),
    ).toBeVisible();
    expect(screen.getByText("Try another photo")).toBeVisible();
    expect(screen.queryByText(/tap the|marker|rim/i)).not.toBeInTheDocument();
  });

  it("shows a lower-confidence detection without asking for confirmation", async () => {
    const accepted = acceptedAnalysis();
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: {
        ...accepted,
        measurements: [
          {
            ...accepted.measurements[0],
            needsReview: true,
            reviewReasons: ["low outline confidence"],
          },
        ],
      },
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);

    await uploadAndAnalyze();

    await screen.findByRole("heading", {
      name: /recommended press-on size: 4/i,
    });
    expect(
      screen.queryByText(/less certain|confirm|adjust/i),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /copy size/i })).toBeVisible();
  });

  it("derives the nearest best-fit size if a legacy result has no recommendation", async () => {
    const accepted = acceptedAnalysis();
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: {
        ...accepted,
        measurements: [{ ...accepted.measurements[0], recommendedSize: null }],
      },
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);

    await uploadAndAnalyze();

    expect(
      await screen.findByRole("heading", {
        name: /recommended press-on size: 4/i,
      }),
    ).toBeVisible();
  });

  it("clears the old photo if a replacement cannot be prepared", async () => {
    render(<SingleNailSizing />);
    uploadPhoto();
    await screen.findByAltText("Selected nail preview");

    vi.mocked(imagePreparation.prepareImage).mockRejectedValueOnce(
      new Error("decode failed"),
    );
    uploadPhoto();

    expect(
      await screen.findByText(/could not read that photo/i),
    ).toBeVisible();
    expect(screen.queryByAltText("Selected nail preview")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /get my nail size/i }),
    ).toBeDisabled();
  });

  it("returns to the upload screen with one button", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "accepted",
      analysis: acceptedAnalysis(),
    }));
    render(<SingleNailSizing analyzePhoto={analyzePhoto} />);
    await uploadAndAnalyze();
    await screen.findByRole("heading", {
      name: /recommended press-on size: 4/i,
    });

    fireEvent.click(screen.getByRole("button", { name: /size another nail/i }));

    expect(
      screen.getByRole("heading", { name: /upload one photo/i }),
    ).toBeVisible();
  });
});
