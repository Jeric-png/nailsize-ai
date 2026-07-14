import { spawn } from "node:child_process";
import { mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

const maximumHeaderBytes = 65_536;
const commandTimeoutMilliseconds = 20_000;

export async function fetchProtectedVercelDeployment(
  target,
  maximumBodyBytes,
  options = {},
) {
  const url = target instanceof URL ? new URL(target) : new URL(target);
  assertRequest(url, maximumBodyBytes);
  if (!(options.environment ?? process.env).VERCEL_TOKEN)
    throw new Error("Protected deployment verification requires VERCEL_TOKEN.");

  const directory = await mkdtemp(path.join(tmpdir(), "nailsize-vercel-curl-"));
  const headerPath = path.join(directory, "headers");
  const bodyPath = path.join(directory, "body");

  try {
    await Promise.all([
      writeFile(headerPath, "", { encoding: "utf8", flag: "wx", mode: 0o600 }),
      writeFile(bodyPath, "", { encoding: "utf8", flag: "wx", mode: 0o600 }),
    ]);
    const arguments_ = buildVercelCurlArguments(
      url,
      maximumBodyBytes,
      headerPath,
      bodyPath,
    );
    await runVercelCurl(arguments_, {
      ...options,
      environment: {
        ...(options.environment ?? process.env),
        CI: "1",
        CURL_HOME: directory,
        FORCE_COLOR: "0",
        NO_COLOR: "1",
        VERCEL_TELEMETRY_DISABLED: "1",
      },
    });

    const [headerMetadata, bodyMetadata] = await Promise.all([
      stat(headerPath),
      stat(bodyPath),
    ]);
    if (headerMetadata.size > maximumHeaderBytes)
      throw new Error("Protected deployment response headers are too large.");
    if (bodyMetadata.size > maximumBodyBytes)
      throw new Error(`Deployment response exceeds ${maximumBodyBytes} bytes.`);

    const [headerDump, body] = await Promise.all([
      readFile(headerPath),
      readFile(bodyPath),
    ]);
    const { status, headers } = parseVercelCurlHeaders(headerDump);
    const bodyStream = new Response(body).body;
    if (!bodyStream)
      throw new Error("Protected deployment response has no body.");

    return {
      body: bodyStream,
      headers,
      ok: status >= 200 && status < 300,
      status,
      url: url.href,
    };
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

export function buildVercelCurlArguments(
  target,
  maximumBodyBytes,
  headerPath,
  bodyPath,
) {
  const url = target instanceof URL ? target : new URL(target);
  assertRequest(url, maximumBodyBytes);
  if (!path.isAbsolute(headerPath) || !path.isAbsolute(bodyPath))
    throw new Error("Protected deployment output paths must be absolute.");

  return [
    "curl",
    `${url.pathname}${url.search}`,
    "--deployment",
    url.origin,
    "--",
    "--silent",
    "--show-error",
    "--compressed",
    "--request",
    "GET",
    "--proto",
    "=https",
    "--connect-timeout",
    "5",
    "--max-time",
    "15",
    "--max-filesize",
    String(maximumBodyBytes),
    "--header",
    "Accept-Encoding: identity",
    "--user-agent",
    "nailsize-guided-deployment-smoke/1",
    "--dump-header",
    headerPath,
    "--output",
    bodyPath,
  ];
}

export function parseVercelCurlHeaders(value) {
  const buffer = Buffer.isBuffer(value) ? value : Buffer.from(value);
  if (buffer.byteLength === 0)
    throw new Error("Protected deployment response has no headers.");
  if (buffer.byteLength > maximumHeaderBytes)
    throw new Error("Protected deployment response headers are too large.");

  const rawBlocks = buffer.toString("latin1").split("\r\n\r\n");
  if (rawBlocks.at(-1) === "") rawBlocks.pop();
  if (rawBlocks.length === 0)
    throw new Error("Protected deployment response headers are malformed.");

  const parsedBlocks = rawBlocks.map(parseHeaderBlock);
  const finalBlock = parsedBlocks.at(-1);
  if (finalBlock.status < 200)
    throw new Error("Protected deployment returned only an interim response.");
  return finalBlock;
}

function parseHeaderBlock(block) {
  const lines = block.split("\r\n");
  const statusLine = lines.shift() ?? "";
  const statusMatch = /^HTTP\/(?:1\.[01]|2|3) ([1-5][0-9]{2})(?: .*)?$/u.exec(
    statusLine,
  );
  if (!statusMatch)
    throw new Error("Protected deployment response status is malformed.");

  const status = Number(statusMatch[1]);
  const headers = new Headers();
  for (const line of lines) {
    if (/^[ \t]/u.test(line))
      throw new Error("Protected deployment response uses folded headers.");
    const match = /^([!#$%&'*+\-.^_`|~0-9A-Za-z]+):[ \t]*([^\0\r\n]*)$/u.exec(
      line,
    );
    if (!match)
      throw new Error("Protected deployment response header is malformed.");
    headers.append(match[1], match[2].trim());
  }
  return { status, headers };
}

async function runVercelCurl(arguments_, options) {
  const spawnImplementation = options.spawnImplementation ?? spawn;
  const signal = AbortSignal.timeout(commandTimeoutMilliseconds);
  await new Promise((resolve, reject) => {
    let settled = false;
    const finish = (callback) => {
      if (settled) return;
      settled = true;
      callback();
    };
    const child = spawnImplementation("vercel", arguments_, {
      cwd: options.cwd ?? process.cwd(),
      env: options.environment,
      shell: false,
      signal,
      stdio: "ignore",
    });
    child.once("error", (error) =>
      finish(() => {
        if (error && typeof error === "object" && error.code === "ENOENT")
          reject(new Error("Pinned Vercel CLI is unavailable."));
        else reject(new Error("Protected deployment request could not start."));
      }),
    );
    child.once("close", (code) =>
      finish(() => {
        if (code === 0) resolve();
        else reject(new Error("Protected deployment request failed."));
      }),
    );
  });
}

function assertRequest(url, maximumBodyBytes) {
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    (url.port && url.port !== "443")
  )
    throw new Error("Protected deployment request must use plain HTTPS.");
  if (!url.hostname.endsWith(".vercel.app"))
    throw new Error("Protected deployment request must target Vercel.");
  if (!Number.isSafeInteger(maximumBodyBytes) || maximumBodyBytes <= 0)
    throw new Error("Protected deployment body limit is invalid.");
}
