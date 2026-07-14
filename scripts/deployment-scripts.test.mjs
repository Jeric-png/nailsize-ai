import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  mkdtempSync,
  mkdirSync,
  readdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test, { after } from "node:test";
import { fileURLToPath } from "node:url";
import {
  assertDeploymentApiContract,
  assertProjectDomainContract,
  isRetryablePromotionApiStatus,
  waitForPromotedDeploymentContract,
} from "./vercel-api-contract.mjs";
import {
  flattenDeploymentTree,
  isCanonicalBase64,
  verifyVercelDeploymentFiles,
} from "./vercel-deployment-files.mjs";
import {
  assertPinnedRuntimeAsset,
  guidedArtifactDigest,
  parseReleaseManifest,
  pinnedRuntimeAssetPaths,
  releaseArtifactDigest,
} from "./guided-artifact.mjs";

const repositoryRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const temporaryDirectories = [];
after(() => {
  for (const directory of temporaryDirectories)
    rmSync(directory, { recursive: true, force: true });
});

test("records preview and production deployment JSON safely", () => {
  const directory = workspace();
  const output = path.join(directory, "outputs.txt");
  const preview = path.join(directory, "preview.json");
  writeJson(preview, {
    status: "ok",
    deployment: {
      id: "dpl_Abc123",
      url: "https://nailsize-preview.vercel.app",
      readyState: "READY",
      target: null,
    },
  });

  const result = run("record-vercel-deployment.mjs", [preview], directory, {
    TARGET_ENVIRONMENT: "staging",
    GITHUB_OUTPUT: output,
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(readFileSync(output, "utf8"), /id=dpl_Abc123/u);

  const mismatch = run("record-vercel-deployment.mjs", [preview], directory, {
    TARGET_ENVIRONMENT: "production",
    GITHUB_OUTPUT: output,
  });
  assert.notEqual(mismatch.status, 0);
  assert.match(mismatch.stderr, /does not match production/u);
});

test("binds inspection to the linked project and promoted deployment", () => {
  const directory = workspace();
  writeProject(directory);
  const candidate = path.join(directory, "candidate.json");
  const promoted = path.join(directory, "promoted.json");
  writeJson(candidate, inspection());
  writeJson(promoted, inspection());
  const environment = {
    TARGET_ENVIRONMENT: "production",
    DEPLOYMENT_ID: "dpl_Def456",
    DEPLOYMENT_URL: "https://nailsize-production.vercel.app",
    VERCEL_PRODUCTION_URL: "https://nailsize-ai-web.vercel.app",
  };

  const candidateResult = run(
    "verify-vercel-inspect.mjs",
    [candidate, "candidate"],
    directory,
    environment,
  );
  assert.equal(candidateResult.status, 0, candidateResult.stderr);

  const promotedResult = run(
    "verify-vercel-inspect.mjs",
    [promoted, "promoted"],
    directory,
    environment,
  );
  assert.equal(promotedResult.status, 0, promotedResult.stderr);

  const wrongId = run(
    "verify-vercel-inspect.mjs",
    [candidate, "candidate"],
    directory,
    { ...environment, DEPLOYMENT_ID: "dpl_Wrong" },
  );
  assert.notEqual(wrongId.status, 0);
});

test("accepts the locked install contract and only Vercel system tokens", () => {
  const directory = workspace();
  const settings = {
    framework: "vite",
    rootDirectory: null,
    buildCommand: "npm run build",
    outputDirectory: "apps/web/dist",
    installCommand: "npm ci",
    devCommand: null,
    nodeVersion: "22.x",
  };
  writeProject(directory, { settings });
  const environmentFile = path.join(directory, ".vercel", ".env.preview.local");
  writeFileSync(
    environmentFile,
    '# Created by Vercel CLI\nVERCEL_OIDC_TOKEN="header.payload.signature"\nVERCEL_AUTOMATION_BYPASS_SECRET="automation-secret"\n',
    "utf8",
  );
  const environment = {
    VERCEL_ORG_ID: "team_expected",
    VERCEL_PROJECT_ID: "prj_expected",
  };

  const empty = run("verify-vercel-pull.mjs", [], directory, environment);
  assert.equal(empty.status, 0, empty.stderr);
  assert.equal(JSON.parse(empty.stdout).systemVariables, 2);

  writeProject(directory, {
    settings: { ...settings, installCommand: "npm install" },
  });
  const unlockedInstall = run(
    "verify-vercel-pull.mjs",
    [],
    directory,
    environment,
  );
  assert.notEqual(unlockedInstall.status, 0);
  assert.match(unlockedInstall.stderr, /installCommand/u);

  writeProject(directory, { settings });

  writeFileSync(
    environmentFile,
    "VITE_REMOTE_API=https://example.test\n",
    "utf8",
  );
  const configured = run("verify-vercel-pull.mjs", [], directory, environment);
  assert.notEqual(configured.status, 0);
  assert.match(configured.stderr, /VITE_REMOTE_API/u);
  assert.doesNotMatch(configured.stderr, /example\.test/u);
});

test("accepts only a byte-identical static Vercel output", () => {
  const directory = workspace();
  const dist = path.join(directory, "apps", "web", "dist");
  const output = path.join(directory, ".vercel", "output");
  const staticRoot = path.join(output, "static");
  mkdirSync(dist, { recursive: true });
  mkdirSync(staticRoot, { recursive: true });
  writeGuidedArtifact(dist);
  writeGuidedArtifact(staticRoot);
  writeJson(path.join(output, "config.json"), { version: 3 });

  const exact = run(
    "verify-guided-build.mjs",
    [".vercel/output/static"],
    directory,
  );
  assert.equal(exact.status, 0, exact.stderr);

  writeJson(path.join(output, "builds.json"), {
    version: 1,
    cliVersion: "55.0.0",
  });
  writeJson(path.join(output, "diagnostics", "build.json"), {
    status: "ready",
  });
  const withVercelMetadata = run(
    "verify-guided-build.mjs",
    [".vercel/output/static"],
    directory,
  );
  assert.equal(withVercelMetadata.status, 0, withVercelMetadata.stderr);

  writeFileSync(path.join(output, "builds.json"), "not-json", "utf8");
  const invalidMetadata = run(
    "verify-guided-build.mjs",
    [".vercel/output/static"],
    directory,
  );
  assert.notEqual(invalidMetadata.status, 0);
  assert.match(invalidMetadata.stderr, /valid JSON metadata/u);
  writeJson(path.join(output, "builds.json"), { version: 1 });

  mkdirSync(path.join(output, "functions"));
  const functionOutput = run(
    "verify-guided-build.mjs",
    [".vercel/output/static"],
    directory,
  );
  assert.notEqual(functionOutput.status, 0);
  assert.match(functionOutput.stderr, /unexpected entries/u);
});

test("locks every automatic-sizing runtime asset into the release digest", () => {
  const manifest = Buffer.from(
    JSON.stringify({
      "index.html": {
        file: "assets/index-test.js",
        css: ["assets/index-test.css"],
      },
      "src/components/InstantSizing.tsx": {
        file: "assets/InstantSizing-test.js",
      },
    }),
  );
  assert.deepEqual(parseReleaseManifest(manifest), [
    "/assets/InstantSizing-test.js",
    "/assets/index-test.css",
    "/assets/index-test.js",
  ]);
  assert.deepEqual(parseReleaseManifest(new Uint8Array(manifest)), [
    "/assets/InstantSizing-test.js",
    "/assets/index-test.css",
    "/assets/index-test.js",
  ]);
  assert.throws(
    () =>
      parseReleaseManifest(
        JSON.stringify({ index: { file: "../outside.js" } }),
      ),
    /unsafe asset path/u,
  );
  assert.throws(
    () => parseReleaseManifest("not-json"),
    /valid JSON \(bytes=8, signature=6e6f742d, sha256=[a-f0-9]{64}\)/u,
  );

  const assets = [
    { pathname: "/asset-manifest.json", content: manifest },
    { pathname: "/assets/index-test.js", content: Buffer.from("entry") },
    {
      pathname: "/assets/InstantSizing-test.js",
      content: Buffer.from("automatic"),
    },
  ];
  const digest = releaseArtifactDigest("<title>NailSize Guide</title>", assets);
  assert.equal(
    releaseArtifactDigest(
      "<title>NailSize Guide</title>",
      [...assets].reverse(),
    ),
    digest,
  );
  assert.notEqual(
    releaseArtifactDigest("<title>NailSize Guide</title>", [
      ...assets.slice(0, 2),
      {
        pathname: "/assets/InstantSizing-test.js",
        content: Buffer.from("changed"),
      },
    ]),
    digest,
  );

  for (const pathname of pinnedRuntimeAssetPaths) {
    const content = readFileSync(
      path.join(repositoryRoot, "apps", "web", "public", pathname.slice(1)),
    );
    assert.doesNotThrow(() => assertPinnedRuntimeAsset(pathname, content));
  }
  const changedRuntime = Buffer.from(
    readFileSync(
      path.join(
        repositoryRoot,
        "apps",
        "web",
        "public",
        "ort",
        "ort-wasm-simd-threaded.mjs",
      ),
    ),
  );
  changedRuntime[0] ^= 1;
  assert.throws(
    () =>
      assertPinnedRuntimeAsset(
        "/ort/ort-wasm-simd-threaded.mjs",
        changedRuntime,
      ),
    /failed its pinned SHA-256/u,
  );
});

test("pins Vercel targets and verifies individual uploaded files", () => {
  const workflow = readFileSync(
    path.join(repositoryRoot, ".github", "workflows", "deploy.yml"),
    "utf8",
  );
  assert.match(workflow, /vercel build --target=preview --no-color/u);
  assert.match(workflow, /args\+=\(--target=preview\)/u);
  assert.match(workflow, /vercel build --prod --no-color/u);
  assert.match(workflow, /args\+=\(--prod --skip-domain\)/u);
  assert.match(workflow, /node scripts\/verify-vercel-files\.mjs/u);
  assert.doesNotMatch(workflow, /--archive/u);
  assert.doesNotMatch(workflow, /--vercel-protected/u);
  assert.equal(workflow.match(/--vercel-curl/gu)?.length, 1);
  assert.equal(workflow.match(/--wait-for-convergence/gu)?.length, 1);
  const uploadedVerification = workflow.indexOf(
    "node scripts/verify-vercel-files.mjs",
  );
  const stagedRuntimeVerification = workflow.indexOf(
    'node scripts/verify-web-deployment.mjs "$DEPLOYMENT_URL" "$ARTIFACT_DIGEST" --vercel-curl',
  );
  const promotion = workflow.indexOf('vercel promote "$DEPLOYMENT_URL"');
  const productionResolution = workflow.indexOf(
    "Wait for production URL to resolve to promoted deployment",
  );
  const publicRuntimeVerification = workflow.indexOf(
    'node scripts/verify-web-deployment.mjs "$PRODUCTION_URL" "$ARTIFACT_DIGEST"',
  );
  assert.ok(uploadedVerification >= 0);
  assert.ok(stagedRuntimeVerification > uploadedVerification);
  assert.ok(promotion > stagedRuntimeVerification);
  assert.ok(productionResolution > promotion);
  assert.ok(publicRuntimeVerification > productionResolution);
  assert.match(
    workflow.slice(
      workflow.lastIndexOf("- name: Verify staged production runtime"),
      promotion,
    ),
    /VERCEL_TOKEN: \$\{\{ secrets\.VERCEL_TOKEN \}\}/u,
  );
  const publicSmoke = workflow.slice(
    workflow.lastIndexOf("- name: Verify promoted production artifact"),
    workflow.lastIndexOf("- name: Publish deployment URL"),
  );
  assert.match(publicSmoke, /--wait-for-convergence/u);
  assert.doesNotMatch(publicSmoke, /VERCEL_TOKEN|vercel-curl/u);
});

test("verifies every uploaded Vercel output byte and application digest", async () => {
  const directory = workspace();
  const output = path.join(directory, ".vercel", "output");
  const staticRoot = path.join(output, "static");
  mkdirSync(staticRoot, { recursive: true });
  writeGuidedArtifact(staticRoot);
  writeJson(path.join(output, "config.json"), { version: 3 });

  const html = readFileSync(path.join(staticRoot, "index.html"), "utf8");
  const script = readFileSync(
    path.join(staticRoot, "assets", "index-test.js"),
    "utf8",
  );
  const style = readFileSync(
    path.join(staticRoot, "assets", "index-test.css"),
    "utf8",
  );
  const expectedArtifactDigest = guidedArtifactDigest(
    html,
    [{ pathname: "/assets/index-test.js", content: script }],
    [{ pathname: "/assets/index-test.css", content: style }],
  );
  const tree = deploymentTree(output);
  const contents = deploymentContents(output);
  const fetchImplementation = async (url, options) => {
    assert.equal(url.origin, "https://api.vercel.com");
    assert.equal(url.searchParams.get("teamId"), "team_expected");
    assert.equal(options.redirect, "error");
    assert.equal(options.headers.Authorization, "Bearer test-token");
    const payload = url.pathname.endsWith("/files")
      ? tree
      : {
          content: contents.get(url.pathname.split("/").at(-1)),
          encoding: "base64",
        };
    return Response.json(payload);
  };

  const result = await verifyVercelDeploymentFiles({
    deploymentId: "dpl_Test123",
    teamId: "team_expected",
    token: "test-token",
    expectedArtifactDigest,
    outputRoot: output,
    fetchImplementation,
  });
  assert.equal(result.files, 4);
  assert.equal(result.artifactDigest, expectedArtifactDigest);

  for (const contentEnvelope of [
    (content) => content,
    (content) => ({ data: content }),
  ]) {
    const envelopeResult = await verifyVercelDeploymentFiles({
      deploymentId: "dpl_Test123",
      teamId: "team_expected",
      token: "test-token",
      expectedArtifactDigest,
      outputRoot: output,
      fetchImplementation: async (url) =>
        Response.json(
          url.pathname.endsWith("/files")
            ? tree
            : contentEnvelope(contents.get(url.pathname.split("/").at(-1))),
        ),
    });
    assert.equal(envelopeResult.artifactDigest, expectedArtifactDigest);
  }

  const changedContents = new Map(contents);
  const scriptUid = sha1(Buffer.from(script));
  changedContents.set(
    scriptUid,
    Buffer.from("export { bad: true };", "utf8").toString("base64"),
  );
  await assert.rejects(
    verifyVercelDeploymentFiles({
      deploymentId: "dpl_Test123",
      teamId: "team_expected",
      token: "test-token",
      expectedArtifactDigest,
      outputRoot: output,
      fetchImplementation: async (url) =>
        Response.json(
          url.pathname.endsWith("/files")
            ? tree
            : {
                content: changedContents.get(url.pathname.split("/").at(-1)),
                encoding: "base64",
              },
        ),
    }),
    /expected canonical base64|contents differ/u,
  );
});

test("validates model-sized canonical base64 without recursive regex limits", () => {
  const encoded = Buffer.alloc(8 * 1024 * 1024, 0xa5).toString("base64");
  assert.equal(isCanonicalBase64(encoded), true);
  assert.equal(isCanonicalBase64(`${encoded.slice(0, -1)}!`), false);
  assert.equal(isCanonicalBase64("A==="), false);
});

test("rejects non-file entries in a Vercel deployment tree", () => {
  assert.throws(
    () =>
      flattenDeploymentTree([
        {
          name: ".vercel",
          type: "directory",
          mode: 16_877,
          children: [
            {
              name: "handler",
              type: "lambda",
              mode: 33_188,
            },
          ],
        },
      ]),
    /forbidden lambda/u,
  );
});

test("binds production domains and deployments to project, team, commit, and promoted state", () => {
  const expected = {
    deploymentId: "dpl_Def456",
    deploymentHost: "nailsize-production.vercel.app",
    projectId: "prj_expected",
    projectName: "nailsize-ai-web",
    orgId: "team_expected",
    commitSha: "a".repeat(40),
    targetEnvironment: "production",
    productionHost: "nailsize-ai-web.vercel.app",
  };
  const deployment = {
    id: expected.deploymentId,
    url: expected.deploymentHost,
    projectId: expected.projectId,
    project: { id: expected.projectId, name: expected.projectName },
    ownerId: expected.orgId,
    team: { id: expected.orgId },
    meta: { nailsizeCommit: expected.commitSha },
    readyState: "READY",
    readySubstate: "STAGED",
    prebuilt: true,
    target: "production",
    alias: [],
  };

  assertProjectDomainContract(
    {
      name: expected.productionHost,
      projectId: expected.projectId,
      verified: true,
    },
    expected,
  );
  assertDeploymentApiContract(deployment, expected, "candidate");
  assertDeploymentApiContract(
    {
      ...deployment,
      readySubstate: "PROMOTED",
    },
    expected,
    "promoted",
  );
  assert.throws(
    () =>
      assertDeploymentApiContract(
        { ...deployment, projectId: "prj_wrong" },
        expected,
        "candidate",
      ),
    /different Vercel project/u,
  );
  assert.throws(
    () =>
      assertDeploymentApiContract(
        { ...deployment, meta: { nailsizeCommit: "b".repeat(40) } },
        expected,
        "candidate",
      ),
    /release commit/u,
  );
});

test("waits for the production hostname to converge to the promoted deployment", async () => {
  const expected = {
    deploymentId: "dpl_Def456",
    deploymentHost: "nailsize-production.vercel.app",
    projectId: "prj_expected",
    projectName: "nailsize-ai-web",
    orgId: "team_expected",
    commitSha: "a".repeat(40),
    targetEnvironment: "production",
    productionHost: "nailsize-ai-web.vercel.app",
  };
  const promoted = {
    id: expected.deploymentId,
    url: expected.deploymentHost,
    projectId: expected.projectId,
    project: { id: expected.projectId, name: expected.projectName },
    ownerId: expected.orgId,
    team: { id: expected.orgId },
    meta: { nailsizeCommit: expected.commitSha },
    readyState: "READY",
    readySubstate: "PROMOTED",
    prebuilt: true,
    target: "production",
    alias: [],
  };
  const staged = { ...promoted, readySubstate: "STAGED", alias: [] };
  const sequence = [{ ...promoted, id: "dpl_Previous" }, staged, promoted];
  let clock = 0;
  let loads = 0;
  const observedTimeouts = [];
  const result = await waitForPromotedDeploymentContract({
    loadDeployment: async ({ timeoutMilliseconds }) => {
      observedTimeouts.push(timeoutMilliseconds);
      loads += 1;
      return sequence.shift();
    },
    expected,
    maximumAttempts: 5,
    intervalMilliseconds: 1_000,
    timeoutMilliseconds: 120_000,
    now: () => clock,
    wait: async (milliseconds) => {
      clock += milliseconds;
    },
  });

  assert.equal(result.id, expected.deploymentId);
  assert.equal(loads, 3);
  assert.equal(clock, 2_000);
  assert.deepEqual(observedTimeouts, [120_000, 119_000, 118_000]);

  let invariantWaited = false;
  await assert.rejects(
    waitForPromotedDeploymentContract({
      loadDeployment: async () => ({
        ...promoted,
        meta: { nailsizeCommit: "b".repeat(40) },
      }),
      expected,
      wait: async () => {
        invariantWaited = true;
      },
    }),
    /release commit/u,
  );
  assert.equal(invariantWaited, false);

  await assert.rejects(
    waitForPromotedDeploymentContract({
      loadDeployment: async () => ({
        ...promoted,
        id: "dpl_Previous",
        projectId: "prj_wrong",
      }),
      expected,
      wait: async () => {
        invariantWaited = true;
      },
    }),
    /different Vercel project/u,
  );
  assert.equal(invariantWaited, false);

  clock = 0;
  loads = 0;
  await assert.rejects(
    waitForPromotedDeploymentContract({
      loadDeployment: async ({ timeoutMilliseconds }) => {
        loads += 1;
        assert.equal(timeoutMilliseconds, 100);
        clock = 80;
        return { ...promoted, id: "dpl_Previous" };
      },
      expected,
      maximumAttempts: 5,
      intervalMilliseconds: 50,
      timeoutMilliseconds: 100,
      now: () => clock,
      wait: async (milliseconds) => {
        clock += milliseconds;
      },
    }),
    /did not converge/u,
  );
  assert.equal(loads, 1);
  assert.equal(clock, 100);

  for (const status of [404, 429, 500, 503, 599])
    assert.equal(isRetryablePromotionApiStatus(status), true);
  for (const status of [400, 401, 403, 422, 499, 600])
    assert.equal(isRetryablePromotionApiStatus(status), false);
});

function workspace() {
  const directory = mkdtempSync(
    path.join(tmpdir(), "nailsize-deployment-test-"),
  );
  temporaryDirectories.push(directory);
  return directory;
}

function writeProject(directory, extra = {}) {
  const target = path.join(directory, ".vercel");
  mkdirSync(target, { recursive: true });
  writeJson(path.join(target, "project.json"), {
    orgId: "team_expected",
    projectId: "prj_expected",
    projectName: "nailsize-ai-web",
    ...extra,
  });
}

function inspection() {
  return {
    id: "dpl_Def456",
    name: "nailsize-ai-web",
    url: "nailsize-production.vercel.app",
    target: "production",
    readyState: "READY",
  };
}

function writeJson(target, value) {
  mkdirSync(path.dirname(target), { recursive: true });
  writeFileSync(target, JSON.stringify(value), "utf8");
}

function writeGuidedArtifact(directory) {
  const assets = path.join(directory, "assets");
  mkdirSync(assets, { recursive: true });
  writeFileSync(
    path.join(directory, "index.html"),
    '<title>NailSize Guide</title><link rel="stylesheet" href="/assets/index-test.css"><script type="module" src="/assets/index-test.js"></script>',
  );
  writeFileSync(path.join(assets, "index-test.js"), "export {};", "utf8");
  writeFileSync(path.join(assets, "index-test.css"), "body{}", "utf8");
}

function deploymentTree(output) {
  const visit = (directory) =>
    readdirSync(directory, { withFileTypes: true }).map((entry) => {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory())
        return {
          name: entry.name,
          type: "directory",
          mode: 16_877,
          children: visit(target),
        };
      return {
        name: entry.name,
        type: "file",
        mode: 33_188,
        uid: sha1(readFileSync(target)),
      };
    });
  return visit(output);
}

function deploymentContents(output) {
  const contents = new Map();
  const visit = (directory) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const target = path.join(directory, entry.name);
      if (entry.isDirectory()) visit(target);
      else {
        const content = readFileSync(target);
        contents.set(sha1(content), content.toString("base64"));
      }
    }
  };
  visit(output);
  return contents;
}

function sha1(content) {
  return createHash("sha1").update(content).digest("hex");
}

function run(script, arguments_, cwd, environment = {}) {
  return spawnSync(
    process.execPath,
    [path.join(repositoryRoot, "scripts", script), ...arguments_],
    {
      cwd,
      encoding: "utf8",
      env: { ...process.env, ...environment },
    },
  );
}
