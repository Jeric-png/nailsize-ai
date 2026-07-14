import { createHash } from "node:crypto";

export const forbiddenClientBindings = [
  "localhost:8000",
  "/v1/measure",
  "/instant",
  "InstantSizing",
  "onnxruntime",
  "nails_seg",
  "ort-wasm",
  "VITE_INFERENCE_API_URL",
  "api.openai.com",
  "huggingface.co",
  "/_vercel/insights",
  "/_vercel/speed-insights",
  "navigator.serviceWorker",
  "sourceMappingURL",
];

export function parseGuidedShell(html, rawOrigin) {
  const origin = new URL(rawOrigin);
  if (!html.includes("<title>NailSize Guide</title>"))
    throw new Error("Artifact did not return the guided web application.");
  if (html.includes("/_vercel/"))
    throw new Error("Artifact HTML contains an injected Vercel client script.");

  const scripts = [...html.matchAll(/<script[^>]+src=["']([^"']+)["']/gu)].map(
    (match) => new URL(match[1], origin),
  );
  if (scripts.length !== 1)
    throw new Error(
      "Artifact must load exactly one application module script.",
    );
  if (
    scripts[0].origin !== origin.origin ||
    !/\/assets\/index-[A-Za-z0-9_-]+\.js$/u.test(scripts[0].pathname)
  )
    throw new Error("Artifact application script has an unexpected path.");

  const styles = [
    ...html.matchAll(
      /<link[^>]+rel=["']stylesheet["'][^>]+href=["']([^"']+)["']/gu,
    ),
  ].map((match) => new URL(match[1], origin));
  if (styles.length !== 1)
    throw new Error("Artifact must load exactly one application stylesheet.");
  if (
    styles[0].origin !== origin.origin ||
    !/\/assets\/index-[A-Za-z0-9_-]+\.css$/u.test(styles[0].pathname)
  )
    throw new Error("Artifact application stylesheet has an unexpected path.");

  return { scripts, styles };
}

export function guidedArtifactDigest(html, scripts, styles) {
  const artifact = createHash("sha256");
  artifact.update(html);
  for (const asset of [...scripts, ...styles]) {
    artifact.update(asset.pathname);
    artifact.update(asset.content);
  }
  return artifact.digest("hex");
}
