import { createHash } from "node:crypto";
import { lstat, readdir, readFile } from "node:fs/promises";
import path from "node:path";
import {
  assertPinnedRuntimeAsset,
  guidedArtifactDigest,
  parseGuidedShell,
  parseReleaseManifest,
  pinnedRuntimeAssetPaths,
  releaseArtifactDigest,
  releaseManifestPath,
} from "./guided-artifact.mjs";

const deploymentPrefix = ".vercel/output";
const maximumFiles = 100;
const maximumBytes = 80 * 1024 * 1024;

export async function verifyVercelDeploymentFiles({
  deploymentId,
  teamId,
  token,
  expectedArtifactDigest,
  outputRoot = path.resolve(".vercel/output"),
  fetchImplementation = fetch,
}) {
  if (!/^dpl_[A-Za-z0-9]+$/u.test(deploymentId ?? ""))
    throw new Error("DEPLOYMENT_ID is invalid.");
  if (!/^team_[A-Za-z0-9]+$/u.test(teamId ?? ""))
    throw new Error("VERCEL_ORG_ID is invalid.");
  if (!token) throw new Error("VERCEL_TOKEN is required.");
  if (!/^[a-f0-9]{64}$/u.test(expectedArtifactDigest ?? ""))
    throw new Error("ARTIFACT_DIGEST must be a lowercase SHA-256 value.");

  const localFiles = await readLocalOutput(outputRoot);
  const tree = await getJson(
    `/v6/deployments/${encodeURIComponent(deploymentId)}/files`,
    teamId,
    token,
    fetchImplementation,
    2_000_000,
  );
  const remoteFiles = normalizeRemotePaths(
    localFiles,
    flattenDeploymentTree(tree),
  );

  const contentByUid = new Map();
  let verifiedBytes = 0;
  for (const [filePath, localContent] of localFiles) {
    const remote = remoteFiles.get(filePath);
    const localUid = createHash("sha1").update(localContent).digest("hex");
    if (remote.uid !== localUid)
      throw new Error(
        `Uploaded deployment file digest differs for ${filePath}.`,
      );

    let remoteContent = contentByUid.get(remote.uid);
    if (!remoteContent) {
      remoteContent = await getFileContent(
        deploymentId,
        remote.uid,
        teamId,
        token,
        fetchImplementation,
        localContent,
      );
      contentByUid.set(remote.uid, remoteContent);
    }
    if (!remoteContent.equals(localContent))
      throw new Error(
        `Uploaded deployment file contents differ for ${filePath}.`,
      );
    verifiedBytes += localContent.byteLength;
  }

  const artifactDigest = deploymentArtifactDigest(remoteFiles, contentByUid);
  if (artifactDigest !== expectedArtifactDigest)
    throw new Error(
      "Uploaded deployment does not match the locally verified application digest.",
    );

  return {
    status: "ok",
    deploymentId,
    files: localFiles.size,
    bytes: verifiedBytes,
    artifactDigest,
    clientOnly: true,
  };
}

export function flattenDeploymentTree(tree) {
  if (!Array.isArray(tree))
    throw new Error("Vercel deployment file tree must be an array.");
  const files = new Map();
  let entries = 0;

  const visit = (nodes, parent, depth) => {
    if (!Array.isArray(nodes) || depth > 16)
      throw new Error("Vercel deployment file tree is malformed.");
    for (const node of nodes) {
      entries += 1;
      if (entries > maximumFiles * 4)
        throw new Error("Vercel deployment file tree exceeds its entry limit.");
      if (!node || typeof node !== "object" || Array.isArray(node))
        throw new Error("Vercel deployment file entry is malformed.");
      if (
        typeof node.name !== "string" ||
        !node.name ||
        node.name === "." ||
        node.name === ".." ||
        /[\\/\0]/u.test(node.name)
      )
        throw new Error("Vercel deployment file entry has an invalid name.");
      if (!Number.isInteger(node.mode) || node.mode < 0)
        throw new Error("Vercel deployment file entry has an invalid mode.");

      const entryPath = parent ? `${parent}/${node.name}` : node.name;
      if (node.type === "directory") {
        if (!Array.isArray(node.children))
          throw new Error(
            `Vercel deployment directory ${entryPath} has no children.`,
          );
        visit(node.children, entryPath, depth + 1);
        continue;
      }
      if (node.type !== "file")
        throw new Error(
          `Vercel deployment contains forbidden ${String(node.type)} entry ${entryPath}.`,
        );
      if (!/^[a-f0-9]{40}$/u.test(node.uid ?? ""))
        throw new Error(
          `Vercel deployment file ${entryPath} has an invalid content ID.`,
        );
      if (node.children !== undefined)
        throw new Error(
          `Vercel deployment file ${entryPath} cannot contain children.`,
        );
      if (files.has(entryPath))
        throw new Error(`Vercel deployment repeats file ${entryPath}.`);
      files.set(entryPath, { uid: node.uid });
    }
  };

  visit(tree, "", 0);
  if (files.size === 0 || files.size > maximumFiles)
    throw new Error("Vercel deployment file count is outside allowed limits.");
  return files;
}

async function readLocalOutput(outputRoot) {
  const files = new Map();
  let totalBytes = 0;

  const visit = async (directory, relativeDirectory = "") => {
    const entries = await readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
      const target = path.join(directory, entry.name);
      const relative = relativeDirectory
        ? `${relativeDirectory}/${entry.name}`
        : entry.name;
      const metadata = await lstat(target);
      if (metadata.isSymbolicLink())
        throw new Error(`Local Vercel output contains symlink ${relative}.`);
      if (metadata.isDirectory()) {
        await visit(target, relative);
        continue;
      }
      if (!metadata.isFile())
        throw new Error(
          `Local Vercel output contains non-file entry ${relative}.`,
        );
      const content = await readFile(target);
      totalBytes += content.byteLength;
      if (files.size + 1 > maximumFiles || totalBytes > maximumBytes)
        throw new Error("Local Vercel output exceeds verification limits.");
      files.set(`${deploymentPrefix}/${relative}`, content);
    }
  };

  await visit(outputRoot);
  if (files.size === 0)
    throw new Error("Local Vercel output contains no files.");
  return files;
}

function normalizeRemotePaths(localFiles, remoteFiles) {
  const staticIndexSuffix = "static/index.html";
  const indexPaths = [...remoteFiles.keys()].filter(
    (filePath) =>
      filePath === staticIndexSuffix ||
      filePath.endsWith(`/${staticIndexSuffix}`),
  );
  if (indexPaths.length !== 1)
    throw new Error(
      "Uploaded deployment must contain exactly one static/index.html path.",
    );
  const remotePrefix = indexPaths[0].slice(0, -staticIndexSuffix.length);
  if (remotePrefix && !remotePrefix.endsWith("/"))
    throw new Error("Uploaded deployment uses an invalid file-tree root.");

  const expectedRemotePaths = [...localFiles.keys()]
    .map((filePath) => {
      const relative = filePath.slice(`${deploymentPrefix}/`.length);
      return `${remotePrefix}${relative}`;
    })
    .sort();
  const actualRemotePaths = [...remoteFiles.keys()].sort();
  if (JSON.stringify(expectedRemotePaths) !== JSON.stringify(actualRemotePaths))
    throw new Error(
      "Uploaded deployment file tree does not exactly match .vercel/output below its Vercel-normalized root.",
    );

  return new Map(
    [...localFiles.keys()].map((filePath) => {
      const relative = filePath.slice(`${deploymentPrefix}/`.length);
      return [filePath, remoteFiles.get(`${remotePrefix}${relative}`)];
    }),
  );
}

function deploymentArtifactDigest(remoteFiles, contentByUid) {
  const staticPrefix = `${deploymentPrefix}/static`;
  const htmlPath = `${staticPrefix}/index.html`;
  const htmlEntry = remoteFiles.get(htmlPath);
  if (!htmlEntry)
    throw new Error("Uploaded deployment is missing static/index.html.");
  const html = contentByUid.get(htmlEntry.uid)?.toString("utf8");
  if (html === undefined)
    throw new Error("Uploaded deployment HTML was not verified.");

  const origin = new URL("https://uploaded-artifact.invalid/");
  const { scripts, styles } = parseGuidedShell(html, origin);
  const readAssets = (assets) =>
    assets.map((asset) => {
      const filePath = `${staticPrefix}${asset.pathname}`;
      const entry = remoteFiles.get(filePath);
      const content = entry && contentByUid.get(entry.uid);
      if (!content)
        throw new Error(
          `Uploaded deployment is missing verified asset ${asset.pathname}.`,
        );
      return { pathname: asset.pathname, content: content.toString("utf8") };
    });

  const scriptAssets = readAssets(scripts);
  const styleAssets = readAssets(styles);
  const manifestFilePath = `${staticPrefix}${releaseManifestPath}`;
  const manifestEntry = remoteFiles.get(manifestFilePath);
  if (!manifestEntry)
    return guidedArtifactDigest(html, scriptAssets, styleAssets);

  const manifestContent = contentByUid.get(manifestEntry.uid);
  if (!manifestContent)
    throw new Error("Uploaded release manifest was not verified.");
  const releasePaths = new Set([
    releaseManifestPath,
    ...parseReleaseManifest(manifestContent),
    ...pinnedRuntimeAssetPaths,
    ...scripts.map(({ pathname }) => pathname),
    ...styles.map(({ pathname }) => pathname),
  ]);
  const releaseAssets = [...releasePaths].map((pathname) => {
    const entry = remoteFiles.get(`${staticPrefix}${pathname}`);
    const content = entry && contentByUid.get(entry.uid);
    if (!content)
      throw new Error(
        `Uploaded deployment is missing verified release asset ${pathname}.`,
      );
    if (pinnedRuntimeAssetPaths.includes(pathname))
      assertPinnedRuntimeAsset(pathname, content);
    return { pathname, content };
  });
  return releaseArtifactDigest(html, releaseAssets);
}

async function getFileContent(
  deploymentId,
  fileId,
  teamId,
  token,
  fetchImplementation,
  expectedContent,
) {
  const payload = await getJson(
    `/v8/deployments/${encodeURIComponent(deploymentId)}/files/${encodeURIComponent(fileId)}`,
    teamId,
    token,
    fetchImplementation,
    Math.ceil((expectedContent.byteLength * 4) / 3) + 4096,
  );
  if (
    payload &&
    typeof payload === "object" &&
    !Array.isArray(payload) &&
    payload.encoding !== undefined &&
    payload.encoding !== "base64"
  )
    throw new Error(
      "Vercel deployment file response used a non-base64 encoding.",
    );

  const encodedCandidates = deploymentFileContentCandidates(payload);
  const matchingContents = encodedCandidates
    .filter(isCanonicalBase64)
    .map((candidate) => Buffer.from(candidate, "base64"))
    .filter(
      (content) =>
        content.byteLength === expectedContent.byteLength &&
        content.equals(expectedContent),
    );
  if (matchingContents.length !== 1)
    throw new Error(
      `Vercel deployment file response did not contain exactly one expected canonical base64 value (${describeJsonShape(payload)}).`,
    );
  return matchingContents[0];
}

function deploymentFileContentCandidates(payload) {
  if (typeof payload === "string") return [payload];
  if (!payload || typeof payload !== "object" || Array.isArray(payload))
    return [];
  const entries = Object.entries(payload);
  if (entries.length > 32)
    throw new Error("Vercel deployment file response has too many fields.");
  return [
    ...new Set(
      entries.flatMap(([name, value]) =>
        name !== "encoding" && typeof value === "string" ? [value] : [],
      ),
    ),
  ];
}

function describeJsonShape(payload) {
  if (payload === null) return "null";
  if (Array.isArray(payload)) return "array";
  if (typeof payload !== "object") return typeof payload;
  const fields = Object.keys(payload).length;
  return fields === 0
    ? "object with no fields"
    : `object with ${fields} fields`;
}

export function isCanonicalBase64(value) {
  if (value === "") return true;
  if (value.length % 4 !== 0) return false;
  const firstPadding = value.indexOf("=");
  const contentLength = firstPadding === -1 ? value.length : firstPadding;
  const paddingLength = value.length - contentLength;
  if (paddingLength > 2) return false;
  for (let index = 0; index < contentLength; index += 1) {
    const code = value.charCodeAt(index);
    const allowed =
      (code >= 65 && code <= 90) ||
      (code >= 97 && code <= 122) ||
      (code >= 48 && code <= 57) ||
      code === 43 ||
      code === 47;
    if (!allowed) return false;
  }
  for (let index = contentLength; index < value.length; index += 1)
    if (value.charCodeAt(index) !== 61) return false;
  return Buffer.from(value, "base64").toString("base64") === value;
}

async function getJson(
  pathname,
  teamId,
  token,
  fetchImplementation,
  maximumResponseBytes,
) {
  const url = new URL(pathname, "https://api.vercel.com");
  url.searchParams.set("teamId", teamId);
  const response = await fetchImplementation(url, {
    redirect: "error",
    signal: AbortSignal.timeout(20_000),
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
      "User-Agent": "nailsize-guided-release-verifier/1",
    },
  });
  if (!response.ok)
    throw new Error(`Vercel API ${pathname} returned HTTP ${response.status}.`);
  if (
    !(response.headers.get("content-type") ?? "")
      .toLowerCase()
      .includes("application/json")
  )
    throw new Error("Vercel deployment file API did not return JSON.");
  const body = await readBoundedText(response, maximumResponseBytes);
  try {
    return JSON.parse(body);
  } catch {
    throw new Error("Vercel deployment file API returned invalid JSON.");
  }
}

async function readBoundedText(response, maximumBytes) {
  const declaredLength = Number(response.headers.get("content-length"));
  if (Number.isFinite(declaredLength) && declaredLength > maximumBytes)
    throw new Error("Vercel deployment file API response is too large.");
  if (!response.body)
    throw new Error("Vercel deployment file API response has no body.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let length = 0;
  let content = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > maximumBytes) {
      await reader.cancel();
      throw new Error("Vercel deployment file API response is too large.");
    }
    content += decoder.decode(value, { stream: true });
  }
  return content + decoder.decode();
}
