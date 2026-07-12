import { readFile } from "node:fs/promises";

const source = process.argv[2];
const phase = process.argv[3] ?? "candidate";
const expectedId = process.env.DEPLOYMENT_ID;
const expectedUrl = process.env.DEPLOYMENT_URL;
const targetEnvironment = process.env.TARGET_ENVIRONMENT;
if (!source || !expectedId || !expectedUrl || !targetEnvironment)
  throw new Error(
    "Deployment inspection requires its JSON file, ID, URL, and target environment.",
  );
if (phase !== "candidate" && phase !== "promoted")
  throw new Error("Inspection phase must be candidate or promoted.");

const [inspection, project] = await Promise.all([
  readFile(source, "utf8").then(JSON.parse),
  readFile(".vercel/project.json", "utf8").then(JSON.parse),
]);
const expectedHost = new URL(expectedUrl).hostname;
if (inspection.id !== expectedId)
  throw new Error(
    "Inspected deployment ID does not match the created deployment.",
  );
if (inspection.url !== expectedHost)
  throw new Error(
    "Inspected deployment URL does not match the created deployment.",
  );
if (inspection.name !== project.projectName)
  throw new Error(
    "Inspected deployment belongs to a different Vercel project.",
  );
if (inspection.readyState !== "READY")
  throw new Error(`Inspected deployment is ${inspection.readyState}.`);

const expectedTarget =
  targetEnvironment === "production" ? "production" : "preview";
if (inspection.target !== expectedTarget)
  throw new Error(
    `Inspected deployment target ${inspection.target} does not match ${expectedTarget}.`,
  );

const aliases = inspection.aliases ?? [];
let productionUrl;
if (targetEnvironment === "production") {
  try {
    productionUrl = new URL(process.env.VERCEL_PRODUCTION_URL ?? "");
  } catch {
    throw new Error(
      "VERCEL_PRODUCTION_URL must be the protected project .vercel.app HTTPS origin.",
    );
  }
}
if (
  productionUrl &&
  (productionUrl.protocol !== "https:" ||
    !productionUrl.hostname.endsWith(".vercel.app") ||
    productionUrl.pathname !== "/" ||
    productionUrl.search ||
    productionUrl.hash ||
    productionUrl.username ||
    productionUrl.password ||
    productionUrl.port)
)
  throw new Error(
    "VERCEL_PRODUCTION_URL must be the protected project .vercel.app HTTPS origin.",
  );

if (phase === "candidate" && targetEnvironment === "production") {
  if (productionUrl && aliases.includes(productionUrl.hostname))
    throw new Error(
      "Production alias moved before candidate verification completed.",
    );
}

if (phase === "promoted") {
  if (targetEnvironment !== "production")
    throw new Error("Only a production deployment can be promoted.");
  if (!productionUrl)
    throw new Error("Production URL validation was not initialized.");
}

console.log(
  JSON.stringify({
    status: "ok",
    id: inspection.id,
    project: inspection.name,
    target: inspection.target,
    phase,
    aliases: aliases.length,
  }),
);
