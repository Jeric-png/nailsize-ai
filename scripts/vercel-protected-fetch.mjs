import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const MAXIMUM_BODY_BYTES = 2_000_000;
const MAXIMUM_HEADER_BYTES = 65_536;

export async function fetchProtectedDeployment(
  url,
  origin,
  token,
  execute = executeVercelCurl,
) {
  if (!token)
    throw new Error(
      "VERCEL_TOKEN is required to verify a protected deployment.",
    );
  if (url.protocol !== "https:" || url.origin !== origin.origin)
    throw new Error("Protected deployment request escaped its HTTPS origin.");

  const directory = await mkdtemp(path.join(tmpdir(), "nailsize-vercel-curl-"));
  const headersPath = path.join(directory, "headers.txt");
  const bodyPath = path.join(directory, "body.bin");
  try {
    await execute({ url, origin, token, headersPath, bodyPath });
    const [headerStat, bodyStat] = await Promise.all([
      stat(headersPath),
      stat(bodyPath),
    ]);
    if (headerStat.size > MAXIMUM_HEADER_BYTES)
      throw new Error("Protected deployment response headers are too large.");
    if (bodyStat.size > MAXIMUM_BODY_BYTES)
      throw new Error("Protected deployment response body is too large.");

    const [rawHeaders, body] = await Promise.all([
      readFile(headersPath, "utf8"),
      readFile(bodyPath),
    ]);
    const { status, headers } = parseCurlHeaders(rawHeaders);
    const response = new Response(body, { status, headers });
    return {
      ok: response.ok,
      status: response.status,
      url: url.href,
      headers: response.headers,
      body: response.body,
    };
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

export function parseCurlHeaders(rawHeaders) {
  const blocks = rawHeaders
    .trim()
    .split(/\r?\n\r?\n/u)
    .filter((block) => /^HTTP\/\S+\s+\d{3}(?:\s|$)/u.test(block));
  const block = blocks.at(-1);
  if (!block)
    throw new Error("Protected deployment returned malformed HTTP headers.");

  const [statusLine, ...lines] = block.split(/\r?\n/u);
  const statusMatch = statusLine.match(/^HTTP\/\S+\s+(\d{3})(?:\s|$)/u);
  const status = Number(statusMatch?.[1]);
  if (!Number.isInteger(status) || status < 200 || status > 599)
    throw new Error("Protected deployment returned an invalid HTTP status.");

  const headers = new Headers();
  for (const line of lines) {
    const separator = line.indexOf(":");
    if (separator <= 0)
      throw new Error("Protected deployment returned a malformed HTTP header.");
    headers.append(
      line.slice(0, separator).trim(),
      line.slice(separator + 1).trim(),
    );
  }
  return { status, headers };
}

async function executeVercelCurl({
  url,
  origin,
  token,
  headersPath,
  bodyPath,
}) {
  const requestTarget = `${url.pathname}${url.search}`;
  try {
    await execFileAsync(
      "vercel",
      [
        "curl",
        requestTarget,
        "--deployment",
        origin.origin,
        "--yes",
        "--non-interactive",
        "--token",
        token,
        "--no-color",
        "--",
        "--silent",
        "--show-error",
        "--max-time",
        "10",
        "--max-filesize",
        String(MAXIMUM_BODY_BYTES),
        "--dump-header",
        headersPath,
        "--output",
        bodyPath,
        "--user-agent",
        "nailsize-guided-deployment-smoke/1",
      ],
      { timeout: 20_000, maxBuffer: MAXIMUM_HEADER_BYTES },
    );
  } catch {
    throw new Error(
      `Authenticated deployment request failed for ${requestTarget}.`,
    );
  }
}
