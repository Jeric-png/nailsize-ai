// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  createDefaultCoinMarkers,
  type CoinMarkers,
  type Point,
} from "../guidedSizing";
import { AnnotationSurface } from "./AnnotationSurface";

const dimensions = { width: 600, height: 800 };
const defaultMarkers = createDefaultCoinMarkers(dimensions);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AnnotationSurface", () => {
  it("moves a high-resolution marker by one rendered pixel with the keyboard", () => {
    const highResolution = { width: 4096, height: 3000 };
    const highResolutionMarkers = createDefaultCoinMarkers(highResolution);
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
    const onCoinMarkersChange = vi.fn();
    const onCoinInteraction = vi.fn();
    render(
      <AnnotationSurface
        previewUrl="blob:test"
        imageDimensions={highResolution}
        mode="calibration"
        coinMarkers={highResolutionMarkers}
        onCoinMarkersChange={onCoinMarkersChange}
        onCoinInteraction={onCoinInteraction}
      />,
    );

    fireEvent.keyDown(
      screen.getByRole("button", { name: /Top coin rim marker/i }),
      { key: "ArrowRight" },
    );

    const updated = onCoinMarkersChange.mock.calls[0][0] as CoinMarkers;
    expect(updated[0].x).toBeCloseTo(highResolutionMarkers[0].x + 1 / 320);
    expect(updated[0].y).toBe(highResolutionMarkers[0].y);
    expect(onCoinInteraction).toHaveBeenCalledWith(0);
  });

  it("offers keyboard-operable creation and movement for nail markers", () => {
    function Harness() {
      const [points, setPoints] = useState<Point[]>([]);
      return (
        <AnnotationSurface
          previewUrl="blob:test"
          imageDimensions={dimensions}
          mode="nail"
          coinMarkers={defaultMarkers}
          onCoinMarkersChange={vi.fn()}
          edgePoints={points}
          onEdgePointsChange={setPoints}
          digitLabel="thumb"
        />
      );
    }
    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: /Add left marker/i }));
    const left = screen.getByRole("button", { name: /Left edge of thumb/i });
    fireEvent.keyDown(left, { key: "ArrowLeft", shiftKey: true });
    fireEvent.click(screen.getByRole("button", { name: /Add right marker/i }));

    expect(
      screen.getByRole("button", { name: /Left edge of thumb/i }),
    ).toBeVisible();
    expect(
      screen.getByRole("button", { name: /Right edge of thumb/i }),
    ).toBeVisible();
  });
});
