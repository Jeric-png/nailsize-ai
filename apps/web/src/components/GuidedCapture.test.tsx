// @vitest-environment jsdom

import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import "@testing-library/jest-dom/vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as imagePreparation from "../imagePreparation";
import { initialSession } from "../session";
import { CaptureRoute } from "./GuidedCapture";

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("local capture preparation", () => {
  it("drops deferred preparation when the capture page unmounts", async () => {
    const prepared = deferred<imagePreparation.PreparedImage>();
    vi.spyOn(imagePreparation, "prepareImage").mockReturnValue(
      prepared.promise,
    );
    const fingerprint = vi.spyOn(imagePreparation, "fingerprintImage");
    const createObjectURL = vi.fn(() => "blob:late");
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL: vi.fn() });
    const dispatch = vi.fn();
    const selected = new File(["pixels"], "capture.png", {
      type: "image/png",
    });

    const view = render(
      <MemoryRouter initialEntries={["/capture/left_fingers/1"]}>
        <Routes>
          <Route
            path="/capture/:captureType/:sample"
            element={
              <CaptureRoute
                state={{ ...initialSession, coinConfirmed: true }}
                dispatch={dispatch}
              />
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(
      screen.getByLabelText(/choose measurement 1 photo for left fingers/i),
      { target: { files: [selected] } },
    );
    await waitFor(() =>
      expect(imagePreparation.prepareImage).toHaveBeenCalled(),
    );
    view.unmount();

    await act(async () => {
      prepared.resolve({ file: selected, width: 600, height: 800 });
      await prepared.promise;
    });

    expect(fingerprint).not.toHaveBeenCalled();
    expect(createObjectURL).not.toHaveBeenCalled();
    expect(dispatch).not.toHaveBeenCalled();
  });
});
