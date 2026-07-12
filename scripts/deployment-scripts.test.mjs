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
} from "./vercel-api-contract.mjs";
import {
  flattenDeploymentTree,
  verifyVercelDeploymentFiles,
} from "./vercel-deployment-files.mjs";
import { guidedArtifactDigest } from "./guided-artifact.mjs";

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

test("binds inspection to the linked project and promoted alias", () => {
  const directory = workspace();
  writeProject(directory);
  const candidate = path.join(directory, "candidate.json");
  const promoted = path.join(directory, "promoted.json");
  writeJson(candidate, inspection());
  writeJson(promoted, {
    ...inspection(),
    aliases: ["nailsize-ai-web.vercel.app"],
  });
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

  const output = path.join(directory, "outputs.txt");
  const promotedResult = run(
    "verify-vercel-inspect.mjs",
    [promoted, "promoted"],
    directory,
    {
      ...environment,
      GITHUB_OUTPUT: output,
    },
  );
  assert.equal(promotedResult.status, 0, promotedResult.stderr);
  assert.match(
    readFileSync(output, "utf8"),
    /production_url=https:\/\/nailsize-ai-web\.vercel\.app/u,
  );

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
  const uploadedVerification = workflow.indexOf(
    "node scripts/verify-vercel-files.mjs",
  );
  const stagedRuntimeVerification = workflow.indexOf(
    'node scripts/verify-web-deployment.mjs "$DEPLOYMENT_URL" "$ARTIFACT_DIGEST"',
  );
  const promotion = workflow.indexOf('vercel promote "$DEPLOYMENT_URL"');
  assert.ok(uploadedVerification >= 0);
  assert.ok(stagedRuntimeVerification > uploadedVerification);
  assert.ok(promotion > stagedRuntimeVerification);
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
    /unexpected size|contents differ/u,
  );
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

test("binds production domains and deployments to project, team, commit, and alias", () => {
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
      alias: [expected.productionHost],
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
  const entries = [];
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
  entries.push({
    name: ".vercel",
    type: "directory",
    mode: 16_877,
    children: [
      {
        name: "output",
        type: "directory",
        mode: 16_877,
        children: visit(output),
      },
    ],
  });
  return entries;
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
