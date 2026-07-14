import { appendFile, readdir, readFile, stat } from "node:fs/promises";
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
const forbiddenModelFiles = files.filter((file) => {
  const relative = path.relative(root, file);
  const segments = relative.split(path.sep);
  return (
    /\.(?:onnx|wasm)$/iu.test(relative) ||
    segments.some((segment) => /^(?:models?|ort)$/iu.test(segment))
  );
});
if (forbiddenModelFiles.length > 0)
  throw new Error(
    `Guided-only artifact contains a forbidden model/runtime file: ${forbiddenModelFiles
      .map((file) => path.relative(root, file))
      .join(", ")}.`,
  );

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
  const allowedEntries = new Set([
    "builds.json",
    "config.json",
    "diagnostics",
    "static",
  ]);
  const unexpected = entries
    .map((entry) => entry.name)
    .filter((name) => !allowedEntries.has(name));
  if (unexpected.length > 0)
    throw new Error(
      `Static Vercel output contains unexpected entries: ${unexpected.join(", ")}.`,
    );

  const byName = new Map(entries.map((entry) => [entry.name, entry]));
  assertEntryType(byName, "config.json", "file");
  assertEntryType(byName, "static", "directory");

  if (byName.has("builds.json")) {
    assertEntryType(byName, "builds.json", "file");
    const buildsPath = path.join(outputRoot, "builds.json");
    const buildsStat = await stat(buildsPath);
    if (buildsStat.size > 2 * 1024 * 1024)
      throw new Error("Vercel builds.json exceeds the metadata size limit.");
    try {
      JSON.parse(await readFile(buildsPath, "utf8"));
    } catch {
      throw new Error("Vercel builds.json must contain valid JSON metadata.");
    }
  }

  if (byName.has("diagnostics")) {
    assertEntryType(byName, "diagnostics", "directory");
    await verifyDiagnostics(path.join(outputRoot, "diagnostics"));
  }

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

function assertEntryType(entries, name, expectedType) {
  const entry = entries.get(name);
  const matches =
    expectedType === "file" ? entry?.isFile() : entry?.isDirectory();
  if (!matches)
    throw new Error(`Vercel output ${name} must be a regular ${expectedType}.`);
}

async function verifyDiagnostics(directory) {
  const limits = { files: 100, bytes: 5 * 1024 * 1024 };
  const totals = { files: 0, bytes: 0 };
  await inspectDiagnostics(directory, totals, limits);
}

async function inspectDiagnostics(directory, totals, limits) {
  const entries = await readdir(directory, { withFileTypes: true });
  for (const entry of entries) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await inspectDiagnostics(target, totals, limits);
      continue;
    }
    if (!entry.isFile())
      throw new Error(
        "Vercel diagnostics metadata may contain only regular files and directories.",
      );

    totals.files += 1;
    totals.bytes += (await stat(target)).size;
    if (totals.files > limits.files || totals.bytes > limits.bytes)
      throw new Error(
        "Vercel diagnostics metadata exceeds the allowed limits.",
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
