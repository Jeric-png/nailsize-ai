import {
  assertPinnedRuntimeAsset,
  forbiddenClientBindings,
  parseGuidedShell,
  parseReleaseManifest,
  pinnedRuntimeAssetPaths,
  releaseArtifactDigest,
  releaseManifestPath,
} from "./guided-artifact.mjs";
import { waitForPublicDeploymentConvergence } from "./public-deployment-convergence.mjs";
import { fetchProtectedVercelDeployment } from "./vercel-curl-fetch.mjs";

const [rawUrl, expectedDigest, ...unexpectedArguments] = process.argv.slice(2);
const allowedArguments = new Set(["--vercel-curl", "--wait-for-convergence"]);
if (
  unexpectedArguments.some((value) => !allowedArguments.has(value)) ||
  new Set(unexpectedArguments).size !== unexpectedArguments.length
)
  throw new Error("Deployment verifier received unexpected arguments.");
const useVercelCurl = unexpectedArguments.includes("--vercel-curl");
const waitForConvergence = unexpectedArguments.includes(
  "--wait-for-convergence",
);
if (useVercelCurl && waitForConvergence)
  throw new Error("Protected and public convergence modes cannot be combined.");
if (!rawUrl)
  throw new Error(
    "Usage: node scripts/verify-web-deployment.mjs <https-url> [expected-sha256] [--vercel-curl|--wait-for-convergence]",
  );
if (expectedDigest && !/^[a-f0-9]{64}$/u.test(expectedDigest))
  throw new Error(
    "Expected artifact digest must be a lowercase SHA-256 value.",
  );
if (waitForConvergence && !expectedDigest)
  throw new Error("Public convergence requires the expected artifact digest.");

const origin = new URL(rawUrl);
if (origin.protocol !== "https:")
  throw new Error("Deployment URL must use HTTPS.");
if (
  origin.username ||
  origin.password ||
  (origin.port && origin.port !== "443")
)
  throw new Error(
    "Deployment URL cannot contain credentials or a custom port.",
  );
if (!origin.hostname.endsWith(".vercel.app"))
  throw new Error("Deployment URL must be a generated *.vercel.app address.");
origin.pathname = "/";
origin.search = "";
origin.hash = "";

let convergenceDeadline;
const result =
  waitForConvergence || useVercelCurl
    ? await waitForPublicDeploymentConvergence({
      verify: async ({ deadline }) => {
        convergenceDeadline = deadline;
        return verifyDeployment();
      },
      ...(useVercelCurl
        ? { timeoutMilliseconds: 60_000, intervalMilliseconds: 2_000 }
        : {}),
    })
    : await verifyDeployment();
console.log(JSON.stringify(result));

async function verifyDeployment() {
  const root = await fetchChecked(origin, 512_000);
  assertSecurityHeaders(root);
  assertContentType(root, "text/html");
  const rootCsp = assertLocalRuntimeCsp(root);

  const html = await readText(root, 512_000);
  const { scripts, styles } = parseGuidedShell(html, origin);
  const manifestResponse = await fetchChecked(
    new URL(releaseManifestPath, origin),
    512_000,
  );
  assertContentType(manifestResponse, "application/json");
  const manifestContent = await readBytes(manifestResponse, 512_000);
  const releasePaths = new Set([
    releaseManifestPath,
    ...parseReleaseManifest(manifestContent),
    ...pinnedRuntimeAssetPaths,
    ...scripts.map(({ pathname }) => pathname),
    ...styles.map(({ pathname }) => pathname),
  ]);
  const releaseAssets = [];
  for (const pathname of releasePaths) {
    const response =
      pathname === releaseManifestPath
        ? manifestResponse
        : await fetchChecked(
            new URL(pathname, origin),
            maximumReleaseAssetBytes(pathname),
          );
    assertReleaseContentType(response, pathname);
    const content =
      pathname === releaseManifestPath
        ? manifestContent
        : await readBytes(response, maximumReleaseAssetBytes(pathname));
    if (/\.(?:css|js|json|mjs)$/u.test(pathname)) {
      const text = new TextDecoder().decode(content);
      for (const value of forbiddenClientBindings)
        if (text.includes(value))
          throw new Error(
            `Deployment asset ${pathname} contains forbidden dependency ${value}.`,
          );
    }
    if (pinnedRuntimeAssetPaths.includes(pathname))
      assertPinnedRuntimeAsset(pathname, content);
    releaseAssets.push({ pathname, content });
  }

  const artifactDigest = releaseArtifactDigest(html, releaseAssets);
  if (expectedDigest && artifactDigest !== expectedDigest)
    throw new Error(
      "Deployment does not serve the locally verified release artifact.",
    );

  const deepRoute = new URL("/instant", origin);
  const deepResponse = await fetchChecked(deepRoute, 512_000);
  assertSecurityHeaders(deepResponse);
  assertContentType(deepResponse, "text/html");
  const deepCsp = assertLocalRuntimeCsp(deepResponse);
  if (deepCsp !== rootCsp)
    throw new Error("SPA deep route does not use the root security policy.");
  if ((await readText(deepResponse, 512_000)) !== html)
    throw new Error(
      "SPA deep-route rewrite is not serving the exact application shell.",
    );

  return {
    status: "ok",
    origin: origin.origin,
    scripts: scripts.length,
    styles: styles.length,
    releaseAssets: releaseAssets.length,
    artifactDigest,
    clientOnly: true,
  };
}

function parseCsp(value) {
  const directives = new Map();
  for (const rawDirective of value.split(";")) {
    const parts = rawDirective.trim().split(/\s+/u).filter(Boolean);
    if (parts.length === 0) continue;
    const [name, ...sources] = parts;
    if (directives.has(name))
      throw new Error(`Deployment CSP repeats the ${name} directive.`);
    directives.set(name, sources);
  }
  return directives;
}

function assertLocalRuntimeCsp(response) {
  const value = response.headers.get("content-security-policy") ?? "";
  const policy = parseCsp(value);
  const connectSources = policy.get("connect-src");
  if (
    !connectSources ||
    connectSources.length !== 1 ||
    connectSources[0] !== "'self'"
  )
    throw new Error("Deployment CSP connect-src must contain only 'self'.");
  const scriptSources = policy.get("script-src") ?? [];
  if (
    scriptSources.length !== 2 ||
    !scriptSources.includes("'self'") ||
    !scriptSources.includes("'wasm-unsafe-eval'")
  )
    throw new Error(
      "Deployment CSP script-src must allow only same-origin scripts and WebAssembly compilation.",
    );
  const workerSources = policy.get("worker-src") ?? [];
  if (
    workerSources.length !== 2 ||
    !workerSources.includes("'self'") ||
    !workerSources.includes("blob:")
  )
    throw new Error(
      "Deployment CSP worker-src must allow only same-origin and local blob workers.",
    );
  return value;
}

function assertSecurityHeaders(response) {
  const required = new Map([
    ["cross-origin-opener-policy", "same-origin"],
    ["cross-origin-embedder-policy", "require-corp"],
    ["cross-origin-resource-policy", "same-origin"],
    ["referrer-policy", "no-referrer"],
    ["x-content-type-options", "nosniff"],
    ["x-frame-options", "DENY"],
  ]);
  for (const [name, expected] of required)
    if (response.headers.get(name) !== expected)
      throw new Error(`Deployment header ${name} must equal ${expected}.`);
  if (
    (response.headers.get("permissions-policy") ?? "") !==
    "camera=(self), geolocation=(), microphone=()"
  )
    throw new Error(
      "Deployment permissions policy does not match the client-only contract.",
    );
}

function maximumReleaseAssetBytes(pathname) {
  if (pathname.endsWith(".onnx")) return 55 * 1024 * 1024;
  if (pathname.endsWith(".wasm")) return 16 * 1024 * 1024;
  if (pathname.endsWith(".js")) return 4 * 1024 * 1024;
  return 1024 * 1024;
}

function assertReleaseContentType(response, pathname) {
  if (pathname.endsWith(".css")) return assertContentType(response, "text/css");
  if (pathname.endsWith(".js") || pathname.endsWith(".mjs"))
    return assertContentType(response, "javascript");
  if (pathname.endsWith(".json"))
    return assertContentType(response, "application/json");
  if (pathname.endsWith(".wasm"))
    return assertContentType(response, "application/wasm");
  if (pathname.endsWith(".onnx")) {
    const value = (response.headers.get("content-type") ?? "").toLowerCase();
    if (
      !value.includes("application/octet-stream") &&
      !value.includes("application/onnx")
    )
      throw new Error(`${response.url} did not return an ONNX binary type.`);
    return;
  }
  throw new Error(`Deployment manifest referenced unsupported asset ${pathname}.`);
}

function assertContentType(response, expected) {
  if (
    !(response.headers.get("content-type") ?? "")
      .toLowerCase()
      .includes(expected)
  )
    throw new Error(`${response.url} did not return ${expected} content.`);
}

async function fetchChecked(url, maximumBodyBytes) {
  const target = new URL(url);
  if (target.protocol !== "https:" || target.origin !== origin.origin)
    throw new Error("Deployment request escaped the expected HTTPS origin.");
  const response = useVercelCurl
    ? await fetchProtectedVercelDeployment(target, maximumBodyBytes)
    : await fetch(target, {
        redirect: "error",
        signal: AbortSignal.timeout(requestTimeoutMilliseconds()),
        headers: { "User-Agent": "nailsize-guided-deployment-smoke/1" },
      });
  if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}.`);
  const finalUrl = new URL(response.url);
  if (finalUrl.protocol !== "https:" || finalUrl.origin !== origin.origin)
    throw new Error("Deployment request escaped the expected HTTPS origin.");
  return response;
}

function requestTimeoutMilliseconds() {
  if (!convergenceDeadline) return 10_000;
  const remainingMilliseconds = Math.floor(
    convergenceDeadline - performance.now(),
  );
  if (remainingMilliseconds <= 0)
    throw new Error("Public deployment convergence timed out.");
  return Math.max(1, Math.min(10_000, remainingMilliseconds));
}

async function readText(response, maximumBytes) {
  return new TextDecoder().decode(await readBytes(response, maximumBytes));
}

async function readBytes(response, maximumBytes) {
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > maximumBytes)
    throw new Error(`Deployment response exceeds ${maximumBytes} bytes.`);
  if (!response.body) throw new Error("Deployment response has no body.");

  const reader = response.body.getReader();
  let length = 0;
  const chunks = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > maximumBytes) {
      await reader.cancel();
      throw new Error(`Deployment response exceeds ${maximumBytes} bytes.`);
    }
    chunks.push(value);
  }
  const content = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    content.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return content;
}
