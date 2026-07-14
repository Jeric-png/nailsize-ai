import { createHash } from "node:crypto";

export const forbiddenClientBindings = [
  "localhost:8000",
  "/v1/measure",
  "VITE_INFERENCE_API_URL",
  "api.openai.com",
  "api-inference.huggingface.co",
  "router.huggingface.co",
  "/_vercel/insights",
  "/_vercel/speed-insights",
  "navigator.serviceWorker",
  "sourceMappingURL",
];

export const releaseManifestPath = "/asset-manifest.json";
export const pinnedRuntimeAssetPaths = [
  "/models/nails_seg_s_yolov8_v1.onnx",
  "/ort/ort-wasm-simd-threaded.mjs",
  "/ort/ort-wasm-simd-threaded.wasm",
];
export const pinnedRuntimeAssetSha256 = new Map([
  [
    "/models/nails_seg_s_yolov8_v1.onnx",
    "6b0b806819748b0f3800982df8448e322d30b329090aedb3fa181bddbf6f17f5",
  ],
  [
    "/ort/ort-wasm-simd-threaded.mjs",
    "0a1e718d99c41b22c21f2520ff4f9e883a6b5533856e398d21816ee8eb8185d3",
  ],
  [
    "/ort/ort-wasm-simd-threaded.wasm",
    "d1ab1b94b16a65b29d710d0b587b29e7bed336827577623913479b8afe8113e6",
  ],
]);

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
  return releaseArtifactDigest(html, [...scripts, ...styles]);
}

export function releaseArtifactDigest(html, assets) {
  const artifact = createHash("sha256");
  const byPath = new Map();
  for (const asset of assets) {
    if (!asset || typeof asset.pathname !== "string")
      throw new Error("Release artifact contains an invalid asset.");
    if (byPath.has(asset.pathname))
      throw new Error(`Release artifact repeats ${asset.pathname}.`);
    byPath.set(asset.pathname, asset.content);
  }
  artifact.update("/index.html\0");
  artifact.update(html);
  for (const [pathname, content] of [...byPath].sort(([left], [right]) =>
    left.localeCompare(right),
  )) {
    artifact.update(`\0${pathname}\0`);
    artifact.update(content);
  }
  return artifact.digest("hex");
}

export function parseReleaseManifest(rawManifest) {
  const manifestBytes = Buffer.isBuffer(rawManifest)
    ? rawManifest
    : Buffer.from(String(rawManifest));
  let manifest;
  try {
    manifest = JSON.parse(manifestBytes.toString("utf8"));
  } catch {
    const digest = createHash("sha256").update(manifestBytes).digest("hex");
    const signature = manifestBytes.subarray(0, 4).toString("hex");
    throw new Error(
      `Release asset manifest must contain valid JSON (bytes=${manifestBytes.byteLength}, signature=${signature}, sha256=${digest}).`,
    );
  }
  if (
    !manifest ||
    typeof manifest !== "object" ||
    Array.isArray(manifest) ||
    Object.keys(manifest).length === 0 ||
    Object.keys(manifest).length > 100
  )
    throw new Error("Release asset manifest has an invalid shape.");

  const paths = new Set();
  for (const entry of Object.values(manifest)) {
    if (!entry || typeof entry !== "object" || Array.isArray(entry))
      throw new Error("Release asset manifest contains an invalid entry.");
    addManifestPath(paths, entry.file);
    for (const field of ["css", "assets"]) {
      const values = entry[field];
      if (values === undefined) continue;
      if (!Array.isArray(values) || values.length > 100)
        throw new Error(`Release manifest ${field} must be a bounded array.`);
      for (const value of values) addManifestPath(paths, value);
    }
  }
  return [...paths].sort();
}

export function assertPinnedRuntimeAsset(pathname, content) {
  const expected = pinnedRuntimeAssetSha256.get(pathname);
  if (!expected)
    throw new Error(`Runtime asset ${pathname} is not pinned.`);
  const actual = createHash("sha256").update(content).digest("hex");
  if (actual !== expected)
    throw new Error(`Runtime asset ${pathname} failed its pinned SHA-256.`);
}

function addManifestPath(paths, value) {
  if (typeof value !== "string" || value.length === 0)
    throw new Error("Release manifest contains an invalid asset path.");
  if (
    value.startsWith("/") ||
    value.includes("..") ||
    !/^[A-Za-z0-9._/-]+\.(?:css|js|wasm)$/u.test(value)
  )
    throw new Error(`Release manifest contains unsafe asset path ${value}.`);
  paths.add(`/${value}`);
}
