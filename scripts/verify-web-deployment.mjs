import {
  forbiddenClientBindings,
  guidedArtifactDigest,
  parseGuidedShell,
} from "./guided-artifact.mjs";

const [rawUrl, expectedDigest, ...unexpectedArguments] = process.argv.slice(2);
if (unexpectedArguments.length > 0)
  throw new Error("Deployment verifier received unexpected arguments.");
if (!rawUrl)
  throw new Error(
    "Usage: node scripts/verify-web-deployment.mjs <https-url> [expected-sha256]",
  );
if (expectedDigest && !/^[a-f0-9]{64}$/u.test(expectedDigest))
  throw new Error(
    "Expected artifact digest must be a lowercase SHA-256 value.",
  );

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

const root = await fetchChecked(origin);
assertSecurityHeaders(root);
assertContentType(root, "text/html");
const rootCsp = assertNoConnectionCsp(root);

const html = await readText(root, 512_000);
const { scripts, styles } = parseGuidedShell(html, origin);
const scriptArtifacts = [];
for (const script of scripts) {
  const response = await fetchChecked(script);
  assertContentType(response, "javascript");
  const content = await readText(response, 2_000_000);
  scriptArtifacts.push({ pathname: script.pathname, content });
  for (const value of forbiddenClientBindings)
    if (content.includes(value))
      throw new Error(
        `Deployment bundle contains forbidden dependency ${value}.`,
      );
}
const styleArtifacts = [];
for (const style of styles) {
  const response = await fetchChecked(style);
  assertContentType(response, "text/css");
  const content = await readText(response, 512_000);
  styleArtifacts.push({ pathname: style.pathname, content });
  for (const value of forbiddenClientBindings)
    if (content.includes(value))
      throw new Error(
        `Deployment stylesheet contains forbidden dependency ${value}.`,
      );
}

const artifactDigest = guidedArtifactDigest(
  html,
  scriptArtifacts,
  styleArtifacts,
);
if (expectedDigest && artifactDigest !== expectedDigest)
  throw new Error(
    "Deployment does not serve the locally verified release artifact.",
  );

const deepRoute = new URL("/guide/left_fingers/1", origin);
const deepResponse = await fetchChecked(deepRoute);
assertSecurityHeaders(deepResponse);
assertContentType(deepResponse, "text/html");
const deepCsp = assertNoConnectionCsp(deepResponse);
if (deepCsp !== rootCsp)
  throw new Error("SPA deep route does not use the root security policy.");
if ((await readText(deepResponse, 512_000)) !== html)
  throw new Error(
    "SPA deep-route rewrite is not serving the exact application shell.",
  );

console.log(
  JSON.stringify({
    status: "ok",
    origin: origin.origin,
    scripts: scripts.length,
    styles: styles.length,
    artifactDigest,
    clientOnly: true,
  }),
);

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

function assertNoConnectionCsp(response) {
  const value = response.headers.get("content-security-policy") ?? "";
  const connectSources = parseCsp(value).get("connect-src");
  if (
    !connectSources ||
    connectSources.length !== 1 ||
    connectSources[0] !== "'none'"
  )
    throw new Error("Deployment CSP connect-src must contain only 'none'.");
  return value;
}

function assertSecurityHeaders(response) {
  const required = new Map([
    ["cross-origin-opener-policy", "same-origin"],
    ["cross-origin-resource-policy", "same-site"],
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

function assertContentType(response, expected) {
  if (
    !(response.headers.get("content-type") ?? "")
      .toLowerCase()
      .includes(expected)
  )
    throw new Error(`${response.url} did not return ${expected} content.`);
}

async function fetchChecked(url) {
  const response = await fetch(url, {
    redirect: "error",
    signal: AbortSignal.timeout(10_000),
    headers: { "User-Agent": "nailsize-guided-deployment-smoke/1" },
  });
  if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}.`);
  const finalUrl = new URL(response.url);
  if (finalUrl.protocol !== "https:" || finalUrl.origin !== origin.origin)
    throw new Error("Deployment request escaped the expected HTTPS origin.");
  return response;
}

async function readText(response, maximumBytes) {
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > maximumBytes)
    throw new Error(`Deployment response exceeds ${maximumBytes} bytes.`);
  if (!response.body) throw new Error("Deployment response has no body.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let length = 0;
  let content = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > maximumBytes) {
      await reader.cancel();
      throw new Error(`Deployment response exceeds ${maximumBytes} bytes.`);
    }
    content += decoder.decode(value, { stream: true });
  }
  return content + decoder.decode();
}
