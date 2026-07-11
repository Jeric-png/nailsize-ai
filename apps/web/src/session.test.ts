import { describe, expect, it, vi } from "vitest";
import { initialSession, sessionReducer } from "./session";

vi.stubGlobal("URL", { revokeObjectURL: vi.fn() });

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
});
