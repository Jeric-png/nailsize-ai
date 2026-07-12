import { appendFile, readdir, readFile } from "node:fs/promises";
import path from "node:path";
import {
  forbiddenClientBindings,
  guidedArtifactDigest,
  parseGuidedShell,
} from "./guided-artifact.mjs";

const root = path.resolve(process.argv[2] ?? "apps/web/dist");
const recordGitHubOutput = process.argv.includes("--github-output");

const files = await walk(root);
if (!files.some((file) => file.endsWith("index.html")))
  throw new Error("The guided web build is missing index.html.");
if (files.some((file) => file.endsWith(".map")))
  throw new Error("Production source maps must not be published.");

for (const file of files) {
  if (!/\.(?:html|js|css|json)$/u.test(file)) continue;
  const content = await readFile(file, "utf8");
  for (const value of forbiddenClientBindings)
    if (content.includes(value))
      throw new Error(
        `Forbidden remote-sizing dependency ${value} found in ${file}.`,
      );
}

if (root === path.resolve(".vercel/output/static"))
  await verifyVercelOutput(root);

const artifactDigest = await digestLocalApplication(root);
if (recordGitHubOutput) {
  if (!process.env.GITHUB_OUTPUT)
    throw new Error("GITHUB_OUTPUT is required to record the artifact digest.");
  await appendFile(
    process.env.GITHUB_OUTPUT,
    `artifact_digest=${artifactDigest}\n`,
    "utf8",
  );
}

console.log(
  JSON.stringify({
    status: "ok",
    root: path.relative(process.cwd(), root),
    files: files.length,
    artifactDigest,
    clientOnly: true,
  }),
);

async function digestLocalApplication(applicationRoot) {
  const html = await readFile(path.join(applicationRoot, "index.html"), "utf8");
  const { scripts, styles } = parseGuidedShell(
    html,
    "https://local-artifact.invalid/",
  );
  const readAssets = (assets) =>
    Promise.all(
      assets.map(async (asset) => ({
        pathname: asset.pathname,
        content: await readFile(
          safeAssetPath(applicationRoot, asset.pathname),
          "utf8",
        ),
      })),
    );
  return guidedArtifactDigest(
    html,
    await readAssets(scripts),
    await readAssets(styles),
  );
}

function safeAssetPath(applicationRoot, pathname) {
  const target = path.resolve(applicationRoot, `.${pathname}`);
  const relative = path.relative(applicationRoot, target);
  if (relative.startsWith("..") || path.isAbsolute(relative))
    throw new Error(`Artifact asset escapes the build root: ${pathname}.`);
  return target;
}

async function verifyVercelOutput(staticRoot) {
  const outputRoot = path.dirname(staticRoot);
  const entries = await readdir(outputRoot, { withFileTypes: true });
  const unexpected = entries
    .map((entry) => entry.name)
    .filter((name) => name !== "config.json" && name !== "static");
  if (unexpected.length > 0)
    throw new Error(
      `Static Vercel output contains unexpected entries: ${unexpected.join(", ")}.`,
    );

  const config = JSON.parse(
    await readFile(path.join(outputRoot, "config.json"), "utf8"),
  );
  if (config.version !== 3)
    throw new Error("Vercel output must use Build Output API version 3.");

  const distRoot = path.resolve("apps/web/dist");
  const distFiles = await walk(distRoot);
  const vercelFiles = await walk(staticRoot);
  const relativeDist = distFiles
    .map((file) => path.relative(distRoot, file))
    .sort();
  const relativeVercel = vercelFiles
    .map((file) => path.relative(staticRoot, file))
    .sort();
  if (JSON.stringify(relativeDist) !== JSON.stringify(relativeVercel))
    throw new Error(
      "Vercel prebuilt files do not exactly match the audited Vite distribution.",
    );

  for (const relative of relativeDist) {
    const [distContent, vercelContent] = await Promise.all([
      readFile(path.join(distRoot, relative)),
      readFile(path.join(staticRoot, relative)),
    ]);
    if (!distContent.equals(vercelContent))
      throw new Error(
        `Vercel prebuilt asset ${relative} differs from the audited Vite distribution.`,
      );
  }
}

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  return (
    await Promise.all(
      entries.map((entry) => {
        const target = path.join(directory, entry.name);
        return entry.isDirectory() ? walk(target) : [target];
      }),
    )
  ).flat();
}
