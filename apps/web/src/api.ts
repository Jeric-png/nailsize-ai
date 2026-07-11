import type { CaptureType, MeasureResponse } from "@nailsize/contracts";

const apiUrl =
  import.meta.env.VITE_INFERENCE_API_URL ?? "http://localhost:8000";

export async function measureCapture(
  captureType: CaptureType,
  file: File,
  signal?: AbortSignal,
): Promise<MeasureResponse> {
  const body = new FormData();
  body.set("image", file);
  body.set("capture_type", captureType);
  body.set("reference_type", "iso_id1");

  const response = await fetch(`${apiUrl}/v1/measure`, {
    method: "POST",
    body,
    signal,
    cache: "no-store",
  });

  if (!response.ok) {
    const detail =
      response.status === 413
        ? "The photo is too large."
        : "The sizing service could not process this photo.";
    throw new Error(detail);
  }

  return (await response.json()) as MeasureResponse;
}
