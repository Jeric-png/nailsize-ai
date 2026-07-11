import { afterEach, describe, expect, it, vi } from "vitest";
import { measureCapture } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("measureCapture", () => {
  it("deduplicates concurrent submissions of the same capture file", async () => {
    let resolveFetch!: (response: Response) => void;
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["image"], "nails.jpg", { type: "image/jpeg" });

    const first = measureCapture("left_thumb", file);
    const second = measureCapture("left_thumb", file);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    resolveFetch(
      new Response(
        JSON.stringify({
          status: "retake",
          request_id: "request-1",
          capture_type: "left_thumb",
          quality_issues: [],
          measurements: [],
          model_version: "test",
          chart_id: "platform-default",
          chart_version: "1",
          processing_ms: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await expect(Promise.all([first, second])).resolves.toHaveLength(2);
  });

  it.each([
    [413, "too_large"],
    [415, "unsupported"],
    [429, "rate_limited"],
    [503, "service"],
  ] as const)("maps HTTP %s to the %s recovery code", async (status, code) => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(null, { status })),
    );
    const file = new File(["image"], `${status}.jpg`, {
      type: "image/jpeg",
    });

    await expect(measureCapture("right_thumb", file)).rejects.toMatchObject({
      code,
    });
  });

  it("maps a network failure to an offline recovery error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    const file = new File(["image"], "offline.jpg", {
      type: "image/jpeg",
    });

    await expect(measureCapture("right_fingers", file)).rejects.toMatchObject({
      code: "offline",
    });
  });

  it("preserves AbortError and removes the cancelled request from deduplication", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce((_url: string, init: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("cancelled", "AbortError"));
          });
        });
      })
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "retake",
            request_id: "request-after-cancel",
            capture_type: "left_fingers",
            quality_issues: [],
            measurements: [],
            model_version: "test",
            chart_id: "platform-default",
            chart_version: "1",
            processing_ms: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["image"], "cancel.jpg", { type: "image/jpeg" });
    const controller = new AbortController();

    const cancelled = measureCapture("left_fingers", file, controller.signal);
    controller.abort();

    await expect(cancelled).rejects.toMatchObject({ name: "AbortError" });
    await expect(measureCapture("left_fingers", file)).resolves.toMatchObject({
      status: "retake",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
