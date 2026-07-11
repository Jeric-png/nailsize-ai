import { beforeEach, describe, expect, it, vi } from "vitest";
import { initialSession, sessionReducer } from "./session";

vi.stubGlobal("URL", { revokeObjectURL: vi.fn() });

beforeEach(() => {
  vi.clearAllMocks();
});

describe("sessionReducer", () => {
  it("preserves accepted captures while advancing", () => {
    const file = new File(["image"], "test.jpg", { type: "image/jpeg" });
    const selected = sessionReducer(initialSession, {
      type: "select",
      captureType: "left_fingers",
      record: { file, previewUrl: "blob:test" },
    });
    const accepted = sessionReducer(selected, {
      type: "accepted",
      captureType: "left_fingers",
      result: {
        status: "ok",
        request_id: "1",
        capture_type: "left_fingers",
        measurements: [],
        quality_issues: [],
        model_version: "test",
        chart_id: "platform-default",
        chart_version: "1",
        processing_ms: 1,
      },
    });
    expect(accepted.activeCapture).toBe("left_thumb");
    expect(accepted.captures.left_fingers?.result?.status).toBe("ok");
  });

  it("releases object URLs when resetting", () => {
    const file = new File(["image"], "test.jpg", { type: "image/jpeg" });
    const selected = sessionReducer(initialSession, {
      type: "select",
      captureType: "left_fingers",
      record: { file, previewUrl: "blob:test" },
    });
    sessionReducer(selected, { type: "reset" });
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:test");
  });

  it("keeps the selected photo but clears only the requested result for correction", () => {
    const file = new File(["image"], "test.jpg", { type: "image/jpeg" });
    const selected = sessionReducer(initialSession, {
      type: "select",
      captureType: "left_thumb",
      record: { file, previewUrl: "blob:left-thumb" },
    });
    const accepted = sessionReducer(selected, {
      type: "accepted",
      captureType: "left_thumb",
      result: {
        status: "ok",
        request_id: "2",
        capture_type: "left_thumb",
        measurements: [],
        quality_issues: [],
        model_version: "test",
        chart_id: "platform-default",
        chart_version: "1",
        processing_ms: 1,
      },
    });

    const reopened = sessionReducer(accepted, {
      type: "reopen",
      captureType: "left_thumb",
    });

    expect(reopened.captures.left_thumb).toMatchObject({
      file,
      previewUrl: "blob:left-thumb",
      result: undefined,
      issues: undefined,
    });
    expect(reopened.correctionCapture).toBe("left_thumb");
    expect(URL.revokeObjectURL).not.toHaveBeenCalled();

    const finished = sessionReducer(reopened, { type: "finishCorrection" });
    expect(finished.correctionCapture).toBeUndefined();
  });

  it("retains a typed infrastructure error for actionable recovery", () => {
    const failed = sessionReducer(initialSession, {
      type: "error",
      code: "rate_limited",
      message: "Wait and retry.",
    });

    expect(failed).toMatchObject({
      status: "error",
      error: { code: "rate_limited", message: "Wait and retry." },
    });
  });
});
