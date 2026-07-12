import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createDefaultCoinMarkers,
  type SampleMeasurement,
} from "./guidedSizing";
import { initialSession, sessionReducer, type SessionAction } from "./session";

vi.stubGlobal("URL", { revokeObjectURL: vi.fn() });

beforeEach(() => {
  vi.clearAllMocks();
});

const dimensions = { width: 600, height: 800 };
const confirmedSession = { ...initialSession, coinConfirmed: true };

const coinMarkers = createDefaultCoinMarkers(dimensions);

function measurements(widthMm: number): SampleMeasurement[] {
  return ["index", "middle", "ring", "pinky"].map((digit) => ({
    digit: digit as "index" | "middle" | "ring" | "pinky",
    widthMm,
    edges: [
      { x: 0.4, y: 0.4 },
      { x: 0.5, y: 0.4 },
    ],
  }));
}

function photoAction(
  captureType: "left_fingers" | "left_thumb" | "right_fingers" | "right_thumb",
  sample: 1 | 2,
  name: string,
): Extract<SessionAction, { type: "selectPhoto" }> {
  return {
    type: "selectPhoto",
    captureType,
    sample,
    previewUrl: `blob:${name}`,
    fingerprint: name,
    dimensions,
  };
}

function completedTwoPhotoSession(verificationWidthMm = 12.2) {
  const firstPhoto = sessionReducer(
    confirmedSession,
    photoAction("left_fingers", 1, "first"),
  );
  const secondPhoto = sessionReducer(
    firstPhoto,
    photoAction("left_fingers", 2, "second"),
  );
  const firstMeasured = sessionReducer(secondPhoto, {
    type: "completeSample",
    captureType: "left_fingers",
    sample: 1,
    coinMarkers,
    measurements: measurements(12),
  });
  return sessionReducer(firstMeasured, {
    type: "completeSample",
    captureType: "left_fingers",
    sample: 2,
    coinMarkers,
    measurements: measurements(verificationWidthMm),
  });
}

describe("guided sizing session", () => {
  it("requires explicit confirmation of the supported coin", () => {
    expect(initialSession.coinConfirmed).toBe(false);
    const confirmed = sessionReducer(initialSession, {
      type: "confirmCoin",
      confirmed: true,
    });
    expect(confirmed.coinConfirmed).toBe(true);
  });

  it("retains the first local photo and image dimensions for verification", () => {
    const first = sessionReducer(
      confirmedSession,
      photoAction("left_fingers", 1, "first"),
    );
    const second = sessionReducer(
      first,
      photoAction("left_fingers", 2, "second"),
    );

    expect(second.captures.left_fingers?.samples).toEqual({
      1: {
        previewUrl: "blob:first",
        fingerprint: "first",
        dimensions,
      },
      2: {
        previewUrl: "blob:second",
        fingerprint: "second",
        dimensions,
      },
    });
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
  });

  it("rejects and releases a duplicate or orphaned verification photo", () => {
    const orphan = sessionReducer(
      confirmedSession,
      photoAction("left_thumb", 2, "orphan"),
    );
    expect(orphan).toBe(confirmedSession);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:orphan");

    vi.clearAllMocks();
    const first = sessionReducer(
      confirmedSession,
      photoAction("left_thumb", 1, "first"),
    );
    const duplicate = sessionReducer(first, {
      ...photoAction("left_thumb", 2, "duplicate"),
      fingerprint: "first",
    });
    expect(duplicate).toBe(first);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:duplicate");
  });

  it("recomputes a consistent result from both stored samples and advances", () => {
    const ready = completedTwoPhotoSession();
    const accepted = sessionReducer(ready, {
      type: "accept",
      captureType: "left_fingers",
    });

    expect(accepted.activeCapture).toBe("left_thumb");
    expect(accepted.captures.left_fingers?.result).toMatchObject({
      captureType: "left_fingers",
      methodVersion: "guided-sg50-coin-v1",
    });
    expect(accepted.captures.left_fingers?.result?.measurements).toHaveLength(
      4,
    );

    const inconsistent = completedTwoPhotoSession(12.7);
    const rejected = sessionReducer(inconsistent, {
      type: "accept",
      captureType: "left_fingers",
    });
    expect(rejected).toBe(inconsistent);
  });

  it("cannot accept a capture without both stored sample measurements", () => {
    const rejected = sessionReducer(confirmedSession, {
      type: "accept",
      captureType: "left_fingers",
    });

    expect(rejected).toBe(confirmedSession);
  });

  it("rechecks verification-image provenance before accepting", () => {
    const ready = completedTwoPhotoSession();
    const current = ready.captures.left_fingers!;
    const duplicateState = {
      ...ready,
      captures: {
        ...ready.captures,
        left_fingers: {
          ...current,
          samples: {
            ...current.samples,
            2: {
              ...current.samples[2]!,
              fingerprint: current.samples[1]!.fingerprint,
            },
          },
        },
      },
    };

    const rejected = sessionReducer(duplicateState, {
      type: "accept",
      captureType: "left_fingers",
    });
    expect(rejected).toBe(duplicateState);
    expect(rejected.captures.left_fingers?.result).toBeUndefined();
  });

  it("releases both photos as soon as their consistent result is accepted", () => {
    const ready = completedTwoPhotoSession();
    const accepted = sessionReducer(ready, {
      type: "accept",
      captureType: "left_fingers",
    });

    expect(accepted.captures.left_fingers?.samples).toEqual({});
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:first");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:second");
  });

  it("releases both local photos when a capture is reopened", () => {
    const first = sessionReducer(
      confirmedSession,
      photoAction("left_thumb", 1, "first"),
    );
    const second = sessionReducer(
      first,
      photoAction("left_thumb", 2, "second"),
    );
    const reopened = sessionReducer(second, {
      type: "reopen",
      captureType: "left_thumb",
    });

    expect(reopened.captures.left_thumb?.samples).toEqual({});
    expect(reopened.correctionCapture).toBe("left_thumb");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:first");
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:second");
  });

  it("clears incompatible work when coin confirmation is withdrawn", () => {
    const selected = sessionReducer(
      { ...initialSession, coinConfirmed: true },
      photoAction("right_thumb", 1, "coin"),
    );
    const changed = sessionReducer(selected, {
      type: "confirmCoin",
      confirmed: false,
    });

    expect(changed.coinConfirmed).toBe(false);
    expect(changed.captures).toEqual({});
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:coin");
  });

  it("releases every local photo when the session resets", () => {
    const first = sessionReducer(
      confirmedSession,
      photoAction("right_fingers", 1, "first"),
    );
    const second = sessionReducer(
      first,
      photoAction("right_fingers", 2, "second"),
    );
    const reset = sessionReducer(second, { type: "reset" });

    expect(reset).toBe(initialSession);
    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
  });

  it("rejects and releases a photo that finishes after confirmation is withdrawn", () => {
    const latePhoto = photoAction("left_fingers", 1, "late");
    const unchanged = sessionReducer(initialSession, latePhoto);

    expect(unchanged).toBe(initialSession);
    expect(unchanged.captures).toEqual({});
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:late");
  });
});
