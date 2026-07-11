import { afterEach, describe, expect, it, vi } from "vitest";
import { measureCapture, REQUEST_TIMEOUT_MS } from "./api";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("measureCapture", () => {
  it.each(["ok", "retake"] as const)(
    "returns a typed %s measurement response",
    async (status) => {
      const measurements =
        status === "ok"
          ? [
              {
                digit: "thumb",
                projected_width_mm: 15.2,
                uncertainty_mm: 0.3,
                recommended_size: "3",
                alternate_size: "4",
                confidence: "high",
                contour: [
                  [0.2, 0.3],
                  [0.8, 0.3],
                ],
              },
            ]
          : [];
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue(
          new Response(
            JSON.stringify({
              status,
              request_id: `request-${status}`,
              capture_type: "left_thumb",
              measurements,
              quality_issues:
                status === "retake"
                  ? [
                      {
                        code: "BLUR",
                        message: "The photo is blurry.",
                        correction: "Retake the photo.",
                      },
                    ]
                  : [],
              model_version: "test",
              chart_id: "platform-default",
              chart_version: "1",
              processing_ms: 12,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        ),
      );
      const file = new File(["image"], `${status}.jpg`, {
        type: "image/jpeg",
      });

      await expect(measureCapture("left_thumb", file)).resolves.toMatchObject({
        status,
        capture_type: "left_thumb",
        measurements,
      });
    },
  );

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
    [408, "timeout"],
    [504, "timeout"],
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

  it("aborts a stalled request at the client deadline and permits retry", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockImplementationOnce((_url: string, init: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init.signal?.addEventListener("abort", () => {
            reject(new DOMException("deadline", "AbortError"));
          });
        });
      })
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            status: "retake",
            request_id: "request-after-timeout",
            capture_type: "right_fingers",
            measurements: [],
            quality_issues: [],
            model_version: "test",
            chart_id: "platform-default",
            chart_version: "1",
            processing_ms: 1,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["image"], "timeout.jpg", { type: "image/jpeg" });

    const stalled = measureCapture("right_fingers", file);
    const timeoutExpectation = expect(stalled).rejects.toMatchObject({
      code: "timeout",
    });
    await vi.advanceTimersByTimeAsync(REQUEST_TIMEOUT_MS);
    await timeoutExpectation;
    await expect(measureCapture("right_fingers", file)).resolves.toMatchObject({
      status: "retake",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
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
