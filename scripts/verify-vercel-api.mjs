import { appendFile, readFile } from "node:fs/promises";
import {
  assertDeploymentApiContract,
  assertProjectDomainContract,
} from "./vercel-api-contract.mjs";

const mode = process.argv[2];
if (!new Set(["domain", "candidate", "promoted"]).has(mode))
  throw new Error(
    "Usage: node scripts/verify-vercel-api.mjs <domain|candidate|promoted>",
  );

const token = required("VERCEL_TOKEN");
const orgId = required("VERCEL_ORG_ID");
const projectId = required("VERCEL_PROJECT_ID");
const targetEnvironment = required("TARGET_ENVIRONMENT");
if (!new Set(["staging", "production"]).has(targetEnvironment))
  throw new Error("TARGET_ENVIRONMENT must be staging or production.");

const project = JSON.parse(await readFile(".vercel/project.json", "utf8"));
if (project.orgId !== orgId || project.projectId !== projectId)
  throw new Error(
    "Local Vercel link does not match the protected environment.",
  );

const productionUrl =
  targetEnvironment === "production"
    ? parseProductionUrl(required("VERCEL_PRODUCTION_URL"))
    : undefined;

if (mode === "domain") {
  if (!productionUrl)
    throw new Error("Only production can preflight a production domain.");
  const payload = await getVercelJson(
    `/v9/projects/${encodeURIComponent(projectId)}/domains/${encodeURIComponent(productionUrl.hostname)}`,
    token,
    orgId,
  );
  assertProjectDomainContract(payload, {
    productionHost: productionUrl.hostname,
    projectId,
  });
  console.log(JSON.stringify({ status: "ok", mode, projectBound: true }));
} else {
  const deploymentId = required("DEPLOYMENT_ID");
  const deploymentUrl = new URL(required("DEPLOYMENT_URL"));
  const commitSha = required("GITHUB_SHA");
  if (!/^dpl_[A-Za-z0-9]+$/u.test(deploymentId))
    throw new Error("DEPLOYMENT_ID is invalid.");
  if (
    deploymentUrl.protocol !== "https:" ||
    !deploymentUrl.hostname.endsWith(".vercel.app") ||
    deploymentUrl.pathname !== "/" ||
    deploymentUrl.search ||
    deploymentUrl.hash
  )
    throw new Error("DEPLOYMENT_URL must be a generated Vercel HTTPS origin.");
  if (!/^[a-f0-9]{40,64}$/u.test(commitSha))
    throw new Error("GITHUB_SHA is invalid.");

  const lookup = mode === "promoted" ? productionUrl?.hostname : deploymentId;
  if (!lookup)
    throw new Error("Promoted verification requires production URL.");
  const payload = await getVercelJson(
    `/v13/deployments/${encodeURIComponent(lookup)}`,
    token,
    orgId,
  );
  assertDeploymentApiContract(
    payload,
    {
      deploymentId,
      deploymentHost: deploymentUrl.hostname,
      projectId,
      projectName: project.projectName,
      orgId,
      commitSha,
      targetEnvironment,
      productionHost: productionUrl?.hostname,
    },
    mode,
  );

  if (mode === "promoted") {
    if (!process.env.GITHUB_OUTPUT)
      throw new Error(
        "GITHUB_OUTPUT is required to record the production URL.",
      );
    await appendFile(
      process.env.GITHUB_OUTPUT,
      `production_url=${productionUrl.origin}\n`,
      "utf8",
    );
  }
  console.log(
    JSON.stringify({
      status: "ok",
      mode,
      deploymentId,
      projectBound: true,
      commitBound: true,
    }),
  );
}

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required.`);
  return value;
}

function parseProductionUrl(raw) {
  const url = new URL(raw);
  if (
    url.protocol !== "https:" ||
    !url.hostname.endsWith(".vercel.app") ||
    url.pathname !== "/" ||
    url.search ||
    url.hash ||
    url.username ||
    url.password ||
    url.port
  )
    throw new Error(
      "VERCEL_PRODUCTION_URL must be the protected project .vercel.app HTTPS origin.",
    );
  return url;
}

async function getVercelJson(pathname, bearerToken, teamId) {
  const url = new URL(pathname, "https://api.vercel.com");
  url.searchParams.set("teamId", teamId);
  const response = await fetch(url, {
    redirect: "error",
    signal: AbortSignal.timeout(15_000),
    headers: {
      Authorization: `Bearer ${bearerToken}`,
      Accept: "application/json",
      "User-Agent": "nailsize-guided-release-verifier/1",
    },
  });
  if (!response.ok)
    throw new Error(`Vercel API ${pathname} returned HTTP ${response.status}.`);
  if (
    !(response.headers.get("content-type") ?? "").includes("application/json")
  )
    throw new Error("Vercel API did not return JSON.");
  const body = await response.text();
  if (Buffer.byteLength(body, "utf8") > 2_000_000)
    throw new Error("Vercel API response exceeded 2 MB.");
  return JSON.parse(body);
}
