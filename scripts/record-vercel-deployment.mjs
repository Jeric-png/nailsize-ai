import { appendFile, readFile } from "node:fs/promises";

const source = process.argv[2];
const targetEnvironment = process.env.TARGET_ENVIRONMENT;
if (!source || !targetEnvironment)
  throw new Error(
    "Usage: TARGET_ENVIRONMENT=<staging|production> node record-vercel-deployment.mjs <json-file>",
  );

const payload = JSON.parse(await readFile(source, "utf8"));
if (payload.status && payload.status !== "ok")
  throw new Error(`Vercel deployment returned status ${payload.status}.`);
const deployment = payload.deployment ?? payload;
if (!/^dpl_[A-Za-z0-9]+$/u.test(deployment.id ?? ""))
  throw new Error("Vercel deployment did not return a valid deployment ID.");
if (deployment.readyState !== "READY")
  throw new Error(
    `Vercel deployment is ${deployment.readyState ?? "missing a ready state"}.`,
  );

const url = new URL(deployment.url);
if (
  url.protocol !== "https:" ||
  !url.hostname.endsWith(".vercel.app") ||
  url.pathname !== "/" ||
  url.search ||
  url.hash
)
  throw new Error("Vercel deployment did not return a generated HTTPS URL.");

const expectedTarget = targetEnvironment === "production" ? "production" : null;
if (deployment.target !== expectedTarget)
  throw new Error(
    `Vercel deployment target ${JSON.stringify(deployment.target)} does not match ${targetEnvironment}.`,
  );

if (!process.env.GITHUB_OUTPUT)
  throw new Error("GITHUB_OUTPUT is required to record deployment identity.");
await appendFile(
  process.env.GITHUB_OUTPUT,
  `id=${deployment.id}\nurl=${url.origin}\n`,
  "utf8",
);
console.log(
  JSON.stringify({
    status: "ok",
    id: deployment.id,
    url: url.origin,
    target: deployment.target,
  }),
);
