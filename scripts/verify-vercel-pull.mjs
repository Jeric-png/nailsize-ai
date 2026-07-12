import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const ALLOWED_VERCEL_SYSTEM_VARIABLES = new Set([
  "VERCEL_AUTOMATION_BYPASS_SECRET",
  "VERCEL_OIDC_TOKEN",
]);

const expectedOrgId = process.env.VERCEL_ORG_ID;
const expectedProjectId = process.env.VERCEL_PROJECT_ID;
if (!expectedOrgId || !expectedProjectId)
  throw new Error("Expected Vercel organization and project IDs are required.");

const vercelDirectory = path.resolve(".vercel");
const project = JSON.parse(
  await readFile(path.join(vercelDirectory, "project.json"), "utf8"),
);
if (project.orgId !== expectedOrgId)
  throw new Error(
    "Pulled Vercel organization does not match the protected environment.",
  );
if (project.projectId !== expectedProjectId)
  throw new Error(
    "Pulled Vercel project does not match the protected environment.",
  );
if (!/^[a-z0-9][a-z0-9._-]*$/u.test(project.projectName ?? ""))
  throw new Error("Pulled Vercel project name is missing or invalid.");

const settings = project.settings ?? {};
assertSetting(settings, "framework", [undefined, null, "vite"]);
assertSetting(settings, "rootDirectory", [undefined, null, ""]);
assertSetting(settings, "buildCommand", [undefined, null, "npm run build"]);
assertSetting(settings, "outputDirectory", [undefined, null, "apps/web/dist"]);
assertSetting(settings, "installCommand", [undefined, null, "npm ci"]);
assertSetting(settings, "devCommand", [undefined, null]);
assertSetting(settings, "nodeVersion", [undefined, null, "22.x"]);

const entries = await readdir(vercelDirectory, { withFileTypes: true });
const environmentFiles = entries.filter(
  (entry) => entry.isFile() && /^\.env(?:\..+)?\.local$/u.test(entry.name),
);
let systemVariables = 0;
for (const entry of environmentFiles) {
  const content = await readFile(
    path.join(vercelDirectory, entry.name),
    "utf8",
  );
  const assignments = content
    .replace(/^\uFEFF/u, "")
    .split(/\r?\n/u)
    .filter((line) => line.trim() && !line.trimStart().startsWith("#"));
  const keys = assignments.map((line) => {
    const match = line.match(/^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=/u);
    if (!match)
      throw new Error(
        `${entry.name} contains an unsupported environment-file entry.`,
      );
    return match[1];
  });
  const unsupported = [
    ...new Set(keys.filter((key) => !ALLOWED_VERCEL_SYSTEM_VARIABLES.has(key))),
  ];
  if (unsupported.length > 0)
    throw new Error(
      `${entry.name} contains unsupported application environment variables: ${unsupported.join(", ")}.`,
    );
  systemVariables += keys.length;
}

console.log(
  JSON.stringify({
    status: "ok",
    projectName: project.projectName,
    environmentFiles: environmentFiles.length,
    systemVariables,
    applicationVariables: 0,
  }),
);

function assertSetting(settings, name, allowed) {
  if (!allowed.includes(settings[name]))
    throw new Error(
      `Vercel project setting ${name}=${JSON.stringify(settings[name])} conflicts with the committed static-client contract.`,
    );
}
