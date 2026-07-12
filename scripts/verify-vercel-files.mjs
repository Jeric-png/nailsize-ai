import path from "node:path";
import { verifyVercelDeploymentFiles } from "./vercel-deployment-files.mjs";

const result = await verifyVercelDeploymentFiles({
  deploymentId: required("DEPLOYMENT_ID"),
  teamId: required("VERCEL_ORG_ID"),
  token: required("VERCEL_TOKEN"),
  expectedArtifactDigest: required("ARTIFACT_DIGEST"),
  outputRoot: path.resolve(".vercel/output"),
});

console.log(JSON.stringify(result));

function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required.`);
  return value;
}
