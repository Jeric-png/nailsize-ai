import type { CaptureType, MeasureResponse } from "@nailsize/contracts";

const apiUrl =
  import.meta.env.VITE_INFERENCE_API_URL ?? "http://localhost:8000";

export type MeasureErrorCode =
  "offline" | "too_large" | "unsupported" | "rate_limited" | "service";

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

  let response: Response;
  try {
    response = await fetch(`${apiUrl}/v1/measure`, {
      method: "POST",
      body,
      signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new MeasureRequestError(
      "offline",
      "The sizing service could not be reached. Check your connection and retry.",
    );
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
    throw new MeasureRequestError(
      "service",
      "The sizing service could not process this photo. Your accepted captures are still here.",
    );
  }

  return (await response.json()) as MeasureResponse;
}
