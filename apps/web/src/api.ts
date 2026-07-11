import type { CaptureType, MeasureResponse } from "@nailsize/contracts";

const apiUrl =
  import.meta.env.VITE_INFERENCE_API_URL ?? "http://localhost:8000";

export type MeasureErrorCode =
  | "offline"
  | "timeout"
  | "too_large"
  | "unsupported"
  | "rate_limited"
  | "service";

export const REQUEST_TIMEOUT_MS = 16_000;

export class MeasureRequestError extends Error {
  constructor(
    readonly code: MeasureErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "MeasureRequestError";
  }
}

const requests = new WeakMap<
  File,
  Map<CaptureType, Promise<MeasureResponse>>
>();

export async function measureCapture(
  captureType: CaptureType,
  file: File,
  signal?: AbortSignal,
): Promise<MeasureResponse> {
  const existing = requests.get(file)?.get(captureType);
  if (existing) return existing;

  const request = sendCapture(captureType, file, signal);
  const fileRequests = requests.get(file) ?? new Map();
  fileRequests.set(captureType, request);
  requests.set(file, fileRequests);
  void request.then(
    () => fileRequests.delete(captureType),
    () => fileRequests.delete(captureType),
  );
  return request;
}

async function sendCapture(
  captureType: CaptureType,
  file: File,
  signal?: AbortSignal,
): Promise<MeasureResponse> {
  const body = new FormData();
  body.set("image", file);
  body.set("capture_type", captureType);
  body.set("reference_type", "iso_id1");

  const controller = new AbortController();
  let timedOut = false;
  const cancelFromCaller = () => controller.abort(signal?.reason);
  if (signal?.aborted) cancelFromCaller();
  else signal?.addEventListener("abort", cancelFromCaller, { once: true });
  const timeout = globalThis.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(`${apiUrl}/v1/measure`, {
      method: "POST",
      body,
      signal: controller.signal,
      cache: "no-store",
    });
  } catch (error) {
    if (signal?.aborted)
      throw new DOMException("The upload was cancelled.", "AbortError");
    if (timedOut)
      throw new MeasureRequestError(
        "timeout",
        "The sizing check took too long. Retry the same photo.",
      );
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    throw new MeasureRequestError(
      "offline",
      "The sizing service could not be reached. Check your connection and retry.",
    );
  } finally {
    globalThis.clearTimeout(timeout);
    signal?.removeEventListener("abort", cancelFromCaller);
  }

  if (!response.ok) {
    if (response.status === 413)
      throw new MeasureRequestError(
        "too_large",
        "The photo is larger than 12 MB.",
      );
    if (response.status === 415)
      throw new MeasureRequestError(
        "unsupported",
        "This file is not a supported JPEG, PNG, WebP, HEIC, or HEIF image.",
      );
    if (response.status === 429)
      throw new MeasureRequestError(
        "rate_limited",
        "The sizing service is busy. Wait a moment, then retry.",
      );
    if (response.status === 408 || response.status === 504)
      throw new MeasureRequestError(
        "timeout",
        "The sizing check took too long. Retry the same photo.",
      );
    throw new MeasureRequestError(
      "service",
      "The sizing service could not process this photo. Your accepted captures are still here.",
    );
  }

  return (await response.json()) as MeasureResponse;
}
