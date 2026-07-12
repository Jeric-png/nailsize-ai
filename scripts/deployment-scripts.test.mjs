import assert from "node:assert/strict";
import {
  mkdtempSync,
  mkdirSync,
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

test("accepts the locked install contract and only Vercel's system token", () => {
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
    '# Created by Vercel CLI\nVERCEL_OIDC_TOKEN="header.payload.signature"\n',
    "utf8",
  );
  const environment = {
    VERCEL_ORG_ID: "team_expected",
    VERCEL_PROJECT_ID: "prj_expected",
  };

  const empty = run("verify-vercel-pull.mjs", [], directory, environment);
  assert.equal(empty.status, 0, empty.stderr);
  assert.equal(JSON.parse(empty.stdout).systemVariables, 1);

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

  mkdirSync(path.join(output, "functions"));
  const functionOutput = run(
    "verify-guided-build.mjs",
    [".vercel/output/static"],
    directory,
  );
  assert.notEqual(functionOutput.status, 0);
  assert.match(functionOutput.stderr, /unexpected entries/u);
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
