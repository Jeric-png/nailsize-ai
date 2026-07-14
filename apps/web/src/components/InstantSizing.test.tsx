// @vitest-environment jsdom

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Digit } from "../guidedSizing";
import * as imagePreparation from "../imagePreparation";
import type {
  AutomaticCoinCompleter,
  AutomaticHandAnalysis,
  AutomaticPhotoAnalyzer,
  AutomaticPhotoAnalysisOutcome,
  CoinReviewContext,
} from "../vision/automaticAnalysisTypes";
import type { HandSide } from "../vision/automaticSizing";
import type { YoloV8SegDetection } from "../vision/yoloV8SegPostprocess";
import { InstantSizing } from "./InstantSizing";

vi.mock("./AutomaticReviewSurface", () => ({
  AutomaticReviewSurface: ({
    measurements,
  }: {
    measurements: readonly { digit: Digit }[];
  }) => (
    <div aria-label="Automatic review test surface">
      {measurements.map(({ digit }) => (
        <span key={digit}>{digit}</span>
      ))}
    </div>
  ),
}));

const DIGITS: readonly Digit[] = ["thumb", "index", "middle", "ring", "pinky"];

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function accepted(side: HandSide): AutomaticPhotoAnalysisOutcome {
  return { status: "accepted", analysis: analysis(side) };
}

function analysis(side: HandSide): AutomaticHandAnalysis {
  return {
    side,
    image: {
      width: 640,
      height: 480,
      data: new Uint8ClampedArray(0),
    },
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
    measurements: DIGITS.map((digit, detectionIndex) => ({
      digit,
      source: "automatic" as const,
      detectionIndex,
      confidence: 0.9,
      widthLine: {
        start: { x: 200 + detectionIndex * 60, y: 160 },
        end: { x: 230 + detectionIndex * 60, y: 160 },
      },
      projectedWidthMm: 13,
      uncertaintyMm: 0.3,
      recommendedSize: "5",
      requiresPhysicalConfirmation: detectionIndex === 0,
      needsReview: false,
      reviewReasons: [],
    })),
  };
}

function coinReview(side: HandSide): CoinReviewContext {
  return {
    side,
    image: {
      width: 640,
      height: 480,
      data: new Uint8ClampedArray(0),
    },
    detections: [],
    suggestedEllipse: null,
    message: "Select the 50-cent coin.",
  };
}

function releasableOutcome() {
  const pixels = new Uint8ClampedArray([255, 128, 64, 32]);
  const binary = new Uint8Array([1, 1]);
  const probabilities = new Float32Array([0.8, 0.9]);
  const detection: YoloV8SegDetection = {
    candidateIndex: 0,
    classId: 0,
    confidence: 0.9,
    box: { x: 0, y: 0, width: 2, height: 1 },
    mask: {
      x: 0,
      y: 0,
      width: 2,
      height: 1,
      binary,
      probabilities,
    },
    quality: {
      foregroundPixelCount: 2,
      foregroundRatio: 1,
      meanProbability: 0.85,
      meanForegroundProbability: 0.85,
      components: {
        count: 1,
        largestPixelCount: 2,
        largestForegroundRatio: 1,
        largestBounds: { x: 0, y: 0, width: 2, height: 1 },
        touchesCropEdge: true,
        largestTouchesCropEdge: true,
      },
    },
  };
  const base = analysis("left");
  const outcome: AutomaticPhotoAnalysisOutcome = {
    status: "accepted",
    analysis: {
      ...base,
      image: { ...base.image, data: pixels },
      detections: [detection],
    },
  };
  return { outcome, pixels, binary, probabilities };
}

async function chooseBothPhotos() {
  const inputs =
    document.querySelectorAll<HTMLInputElement>('input[type="file"]');
  expect(inputs).toHaveLength(2);
  fireEvent.change(inputs[0], {
    target: {
      files: [new File(["left"], "left.jpg", { type: "image/jpeg" })],
    },
  });
  await screen.findByAltText("Left hand selected preview");
  fireEvent.change(inputs[1], {
    target: {
      files: [new File(["right"], "right.jpg", { type: "image/jpeg" })],
    },
  });
  await screen.findByAltText("Right hand selected preview");
  fireEvent.click(
    screen.getByRole("checkbox", { name: /current Third Series/i }),
  );
}

beforeEach(() => {
  vi.spyOn(imagePreparation, "prepareImage").mockImplementation(
    async (file) => ({ file, width: 640, height: 480 }),
  );
  vi.stubGlobal("URL", {
    createObjectURL: vi.fn((blob: File) => `blob:${blob.name}`),
    revokeObjectURL: vi.fn(),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("instant two-photo sizing", () => {
  it("processes both hands in order, requires review, and erases previews on reset", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async (side) =>
      accepted(side),
    );
    render(<InstantSizing analyzePhoto={analyzePhoto} />);

    const start = screen.getByRole("button", {
      name: /find my best-fit sizes/i,
    });
    expect(start).toBeDisabled();
    await chooseBothPhotos();
    expect(start).toBeEnabled();

    fireEvent.click(start);
    await screen.findByRole("heading", {
      name: /check the coin and five width lines/i,
    });
    expect(analyzePhoto.mock.calls.map(([side]) => side)).toEqual([
      "left",
      "right",
    ]);

    fireEvent.click(
      screen.getByRole("button", { name: /approve and review right hand/i }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /approve and show best fits/i }),
    );

    expect(
      screen.getByRole("heading", { name: /suggested best-fit nail set/i }),
    ).toBeVisible();
    expect(screen.getAllByText("Best-fit size 5")).toHaveLength(10);
    expect(screen.queryByText("Best-fit size 6")).not.toBeInTheDocument();
    expect(screen.queryByText(/centre estimate/i)).not.toBeInTheDocument();
    expect(
      screen.getAllByText(/borderline measurement.*confirm/i),
    ).toHaveLength(2);

    fireEvent.click(
      screen.getByRole("button", { name: /start over and erase photos/i }),
    );
    expect(
      screen.getByRole("heading", { name: /upload two hand photos/i }),
    ).toBeVisible();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:left.jpg");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:right.jpg");
  });

  it("fails closed on the first rejected hand without analyzing the second", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async () => ({
      status: "rejected",
      message: "Only four clear nails were found.",
    }));
    render(<InstantSizing analyzePhoto={analyzePhoto} />);
    await chooseBothPhotos();

    fireEvent.click(
      screen.getByRole("button", { name: /find my best-fit sizes/i }),
    );

    expect(
      await screen.findByText(/left hand: only four clear nails were found/i),
    ).toHaveAttribute("role", "alert");
    expect(analyzePhoto).toHaveBeenCalledTimes(1);
    expect(analyzePhoto).toHaveBeenCalledWith(
      "left",
      expect.any(File),
      expect.any(Function),
    );
  });

  it("keeps an accepted left hand when only the right hand needs another pass", async () => {
    let rightAttempts = 0;
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async (side) => {
      if (side === "right" && rightAttempts++ === 0)
        return {
          status: "rejected",
          message: "The thumb is cropped.",
        };
      return accepted(side);
    });
    render(<InstantSizing analyzePhoto={analyzePhoto} />);
    await chooseBothPhotos();

    fireEvent.click(
      screen.getByRole("button", { name: /find my best-fit sizes/i }),
    );
    expect(await screen.findByText(/left hand result is kept/i)).toBeVisible();
    expect(analyzePhoto.mock.calls.map(([side]) => side)).toEqual([
      "left",
      "right",
    ]);

    fireEvent.click(screen.getByRole("button", { name: /retry right hand/i }));
    await screen.findByRole("heading", {
      name: /check the coin and five width lines/i,
    });
    expect(analyzePhoto.mock.calls.map(([side]) => side)).toEqual([
      "left",
      "right",
      "right",
    ]);
  });

  it("uses one coin-outline correction and then resumes with the right hand", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(
      async (side): Promise<AutomaticPhotoAnalysisOutcome> =>
        side === "left"
          ? { status: "coin-review", context: coinReview(side) }
          : accepted(side),
    );
    const completeCoin = vi.fn<AutomaticCoinCompleter>(() => accepted("left"));
    render(
      <InstantSizing analyzePhoto={analyzePhoto} completeCoin={completeCoin} />,
    );
    await chooseBothPhotos();

    fireEvent.click(
      screen.getByRole("button", { name: /find my best-fit sizes/i }),
    );

    expect(
      await screen.findByRole("heading", { name: /tap the coin once/i }),
    ).toBeVisible();
    expect(screen.getByText(/no eight-point marking/i)).toBeVisible();
    fireEvent.click(
      screen.getByRole("button", { name: /use this coin outline/i }),
    );

    await waitFor(() => expect(analyzePhoto).toHaveBeenCalledTimes(2));
    expect(analyzePhoto.mock.calls.map(([side]) => side)).toEqual([
      "left",
      "right",
    ]);
    expect(completeCoin).toHaveBeenCalledTimes(1);
    expect(
      await screen.findByRole("heading", {
        name: /check the coin and five width lines/i,
      }),
    ).toBeVisible();
  });

  it("returns to capture when coin correction exposes a terminal nail rejection", async () => {
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(async (side) => ({
      status: "coin-review",
      context: coinReview(side),
    }));
    const completeCoin = vi.fn<AutomaticCoinCompleter>(() => ({
      status: "rejected",
      message: "Only four clear nails were found.",
    }));
    render(
      <InstantSizing analyzePhoto={analyzePhoto} completeCoin={completeCoin} />,
    );
    await chooseBothPhotos();
    fireEvent.click(
      screen.getByRole("button", { name: /find my best-fit sizes/i }),
    );
    await screen.findByRole("heading", { name: /tap the coin once/i });

    fireEvent.click(
      screen.getByRole("button", { name: /use this coin outline/i }),
    );

    expect(
      await screen.findByRole("heading", { name: /upload two hand photos/i }),
    ).toBeVisible();
    expect(
      screen.getByText(
        /left hand: only four clear nails were found.*choose a clearer photo/i,
      ),
    ).toHaveAttribute("role", "alert");
    expect(analyzePhoto).toHaveBeenCalledTimes(1);
  });

  it("keeps the newest photo when overlapping preparation resolves out of order", async () => {
    const older = deferred<imagePreparation.PreparedImage>();
    const newer = deferred<imagePreparation.PreparedImage>();
    vi.mocked(imagePreparation.prepareImage)
      .mockReset()
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise);
    render(<InstantSizing />);
    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    const olderFile = new File(["older"], "older.jpg", {
      type: "image/jpeg",
    });
    const newerFile = new File(["newer"], "newer.jpg", {
      type: "image/jpeg",
    });

    fireEvent.change(input, { target: { files: [olderFile] } });
    await waitFor(() =>
      expect(imagePreparation.prepareImage).toHaveBeenCalledTimes(1),
    );
    input.disabled = false;
    fireEvent.change(input, { target: { files: [newerFile] } });
    await waitFor(() =>
      expect(imagePreparation.prepareImage).toHaveBeenCalledTimes(2),
    );

    await act(async () => {
      newer.resolve({ file: newerFile, width: 640, height: 480 });
      await newer.promise;
    });
    expect(
      await screen.findByAltText("Left hand selected preview"),
    ).toHaveAttribute("src", "blob:newer.jpg");

    await act(async () => {
      older.resolve({ file: olderFile, width: 640, height: 480 });
      await older.promise;
    });
    expect(screen.getByAltText("Left hand selected preview")).toHaveAttribute(
      "src",
      "blob:newer.jpg",
    );
    expect(URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(URL.createObjectURL).toHaveBeenCalledWith(newerFile);
  });

  it("drops a prepared photo that resolves after unmount without creating a preview URL", async () => {
    const prepared = deferred<imagePreparation.PreparedImage>();
    vi.mocked(imagePreparation.prepareImage).mockReturnValue(prepared.promise);
    const selected = new File(["left"], "left.jpg", {
      type: "image/jpeg",
    });
    const view = render(<InstantSizing />);

    const input =
      document.querySelector<HTMLInputElement>('input[type="file"]')!;
    fireEvent.change(input, { target: { files: [selected] } });
    await waitFor(() =>
      expect(imagePreparation.prepareImage).toHaveBeenCalledWith(selected),
    );
    view.unmount();

    await act(async () => {
      prepared.resolve({ file: selected, width: 640, height: 480 });
      await prepared.promise;
    });

    expect(URL.createObjectURL).not.toHaveBeenCalled();
  });

  it("zeroes a late analysis outcome that resolves after unmount", async () => {
    const pending = deferred<AutomaticPhotoAnalysisOutcome>();
    const analyzePhoto = vi.fn<AutomaticPhotoAnalyzer>(() => pending.promise);
    const view = render(<InstantSizing analyzePhoto={analyzePhoto} />);
    await chooseBothPhotos();
    fireEvent.click(
      screen.getByRole("button", { name: /find my best-fit sizes/i }),
    );
    await waitFor(() => expect(analyzePhoto).toHaveBeenCalledTimes(1));

    view.unmount();
    const { outcome, pixels, binary, probabilities } = releasableOutcome();
    await act(async () => {
      pending.resolve(outcome);
      await pending.promise;
    });

    expect([...pixels]).toEqual([0, 0, 0, 0]);
    expect([...binary]).toEqual([0, 0]);
    expect([...probabilities]).toEqual([0, 0]);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:left.jpg");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:right.jpg");
  });
});
