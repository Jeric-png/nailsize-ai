// @vitest-environment jsdom

import { render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SessionState } from "./session";

const { measureCaptureMock } = vi.hoisted(() => ({
  measureCaptureMock: vi.fn(),
}));

vi.mock("./api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./api")>()),
  measureCapture: measureCaptureMock,
}));

import { QualityPage } from "./App";

afterEach(() => {
  measureCaptureMock.mockReset();
});

describe("QualityPage", () => {
  it("aborts the transient upload when the quality screen unmounts", async () => {
    let requestSignal: AbortSignal | undefined;
    measureCaptureMock.mockImplementation(
      (_captureType, _file, signal: AbortSignal | undefined) => {
        requestSignal = signal;
        return new Promise(() => undefined);
      },
    );
    const file = new File(["image"], "capture.jpg", { type: "image/jpeg" });
    const state: SessionState = {
      activeCapture: "left_fingers",
      status: "submitting",
      captures: {
        left_fingers: { file, previewUrl: "blob:capture" },
      },
    };

    const view = render(
      <MemoryRouter initialEntries={["/quality/left_fingers"]}>
        <Routes>
          <Route
            path="/quality/:captureType"
            element={<QualityPage state={state} dispatch={vi.fn()} />}
          />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(requestSignal).toBeDefined());
    expect(requestSignal?.aborted).toBe(false);

    view.unmount();

    expect(requestSignal?.aborted).toBe(true);
  });
});
