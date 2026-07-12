import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const OIDC_TOKEN_PATTERN = /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/u;

export async function loadVercelOidcToken(
  vercelDirectory = path.resolve(".vercel"),
) {
  const entries = await readdir(vercelDirectory, { withFileTypes: true });
  const environmentFiles = entries.filter(
    (entry) => entry.isFile() && /^\.env(?:\..+)?\.local$/u.test(entry.name),
  );
  const tokens = [];
  for (const entry of environmentFiles) {
    const content = await readFile(
      path.join(vercelDirectory, entry.name),
      "utf8",
    );
    for (const line of content.replace(/^\uFEFF/u, "").split(/\r?\n/u)) {
      const match = line.match(/^(?:export\s+)?VERCEL_OIDC_TOKEN=(.*)$/u);
      if (match) tokens.push(parseEnvironmentValue(match[1]));
    }
  }
  if (tokens.length !== 1)
    throw new Error(
      "Protected deployment verification requires exactly one Vercel OIDC token.",
    );
  assertOidcToken(tokens[0]);
  return tokens[0];
}

export async function fetchProtectedDeployment(
  url,
  origin,
  token,
  fetchImplementation = fetch,
) {
  assertOidcToken(token);
  if (url.protocol !== "https:" || url.origin !== origin.origin)
    throw new Error("Protected deployment request escaped its HTTPS origin.");

  try {
    return await fetchImplementation(url, {
      redirect: "error",
      signal: AbortSignal.timeout(10_000),
      headers: {
        "User-Agent": "nailsize-guided-deployment-smoke/1",
        "x-vercel-trusted-oidc-idp-token": token,
      },
    });
  } catch {
    throw new Error(
      `Authenticated deployment request failed for ${url.pathname}.`,
    );
  }
}

function parseEnvironmentValue(rawValue) {
  const value = rawValue.trim();
  if (value.startsWith('"') && value.endsWith('"')) {
    try {
      return JSON.parse(value);
    } catch {
      throw new Error("Vercel OIDC token uses invalid quoted syntax.");
    }
  }
  if (value.startsWith("'") && value.endsWith("'")) return value.slice(1, -1);
  return value;
}

function assertOidcToken(token) {
  if (
    typeof token !== "string" ||
    token.length > 8192 ||
    !OIDC_TOKEN_PATTERN.test(token)
  )
    throw new Error("Vercel OIDC token is missing or malformed.");
}
