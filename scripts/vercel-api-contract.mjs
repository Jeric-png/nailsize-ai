export function assertProjectDomainContract(payload, expected) {
  if (payload.name !== expected.productionHost)
    throw new Error(
      "Protected production hostname is not the requested project domain.",
    );
  if (payload.projectId !== expected.projectId)
    throw new Error(
      "Protected production hostname belongs to a different project.",
    );
  if (payload.verified !== true)
    throw new Error("Protected production hostname is not verified by Vercel.");
}

export function assertDeploymentApiContract(payload, expected, phase) {
  if (phase !== "candidate" && phase !== "promoted")
    throw new Error("Deployment API phase must be candidate or promoted.");
  assertDeploymentBaseContract(payload, expected);

  const aliases = payload.alias ?? [];
  if (phase === "candidate" && expected.productionHost) {
    if (aliases.includes(expected.productionHost))
      throw new Error(
        "Production alias moved before candidate verification completed.",
      );
  }
  if (
    phase === "candidate" &&
    expected.targetEnvironment === "production" &&
    payload.readySubstate &&
    payload.readySubstate !== "STAGED"
  )
    throw new Error("Production candidate is not in Vercel's staged state.");
  if (phase === "promoted") {
    if (expected.targetEnvironment !== "production" || !expected.productionHost)
      throw new Error(
        "Only a production deployment can be verified as promoted.",
      );
    if (payload.readySubstate && payload.readySubstate !== "PROMOTED")
      throw new Error(
        "Production deployment is not in Vercel's promoted state.",
      );
  }
}

function assertDeploymentBaseContract(payload, expected) {
  if (payload.id !== expected.deploymentId)
    throw new Error("Vercel API returned a different deployment ID.");
  if (payload.url !== expected.deploymentHost)
    throw new Error(
      "Vercel API returned a different generated deployment URL.",
    );
  assertDeploymentOwnership(payload, expected);
  if (payload.meta?.nailsizeCommit !== expected.commitSha)
    throw new Error("Deployment metadata does not match the release commit.");
  if (payload.readyState !== "READY")
    throw new Error(`Deployment API state is ${payload.readyState}.`);
  if (payload.prebuilt !== true)
    throw new Error(
      "Deployment was not created from the verified prebuilt artifact.",
    );

  const expectedTarget =
    expected.targetEnvironment === "production" ? "production" : null;
  if (payload.target !== expectedTarget)
    throw new Error(
      "Deployment API target does not match the release environment.",
    );
}

function assertDeploymentOwnership(payload, expected) {
  if (payload.projectId !== expected.projectId)
    throw new Error("Deployment belongs to a different Vercel project.");
  if (payload.project && payload.project.id !== expected.projectId)
    throw new Error(
      "Deployment project metadata does not match the protected project.",
    );
  if (payload.project && payload.project.name !== expected.projectName)
    throw new Error(
      "Deployment project name does not match the linked project.",
    );
  if (payload.ownerId !== expected.orgId)
    throw new Error("Deployment belongs to a different Vercel organization.");
  if (payload.team && payload.team.id !== expected.orgId)
    throw new Error("Deployment team metadata does not match its owner.");
}

export async function waitForPromotedDeploymentContract({
  loadDeployment,
  expected,
  maximumAttempts = 25,
  intervalMilliseconds = 5_000,
  timeoutMilliseconds = 120_000,
  now = () => performance.now(),
  wait = (milliseconds) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds)),
}) {
  if (
    typeof loadDeployment !== "function" ||
    typeof now !== "function" ||
    typeof wait !== "function"
  )
    throw new Error("Promotion convergence callbacks are required.");
  if (!Number.isSafeInteger(maximumAttempts) || maximumAttempts <= 0)
    throw new Error("Promotion convergence attempt count is invalid.");
  if (!Number.isSafeInteger(intervalMilliseconds) || intervalMilliseconds < 0)
    throw new Error("Promotion convergence interval is invalid.");
  if (!Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds <= 0)
    throw new Error("Promotion convergence timeout is invalid.");

  const startedAt = now();
  if (!Number.isFinite(startedAt))
    throw new Error("Promotion convergence clock is invalid.");
  const deadline = startedAt + timeoutMilliseconds;

  let lastError;
  for (let attempt = 1; attempt <= maximumAttempts; attempt += 1) {
    const remainingMilliseconds = Math.floor(deadline - now());
    if (remainingMilliseconds <= 0) break;
    try {
      const deployment = await loadDeployment({
        timeoutMilliseconds: remainingMilliseconds,
      });
      assertPromotedDeploymentOrPending(deployment, expected);
      return deployment;
    } catch (error) {
      if (!(error instanceof PromotionConvergencePendingError)) throw error;
      lastError = error;
    }
    const remainingAfterAttempt = Math.floor(deadline - now());
    if (attempt < maximumAttempts && remainingAfterAttempt > 0)
      await wait(Math.min(intervalMilliseconds, remainingAfterAttempt));
  }

  throw new Error(
    "Production hostname did not converge to the verified deployment.",
    { cause: lastError },
  );
}

export class PromotionConvergencePendingError extends Error {}

export function isRetryablePromotionApiStatus(status) {
  return status === 404 || status === 429 || (status >= 500 && status <= 599);
}

function assertPromotedDeploymentOrPending(deployment, expected) {
  if (deployment.id !== expected.deploymentId) {
    assertDeploymentOwnership(deployment, expected);
    if (deployment.target !== "production")
      throw new Error("Previous production hostname target is not production.");
    throw new PromotionConvergencePendingError(
      "Production hostname still resolves to the previous deployment.",
    );
  }

  assertDeploymentBaseContract(deployment, expected);
  if (
    deployment.readySubstate &&
    deployment.readySubstate !== "STAGED" &&
    deployment.readySubstate !== "PROMOTED"
  )
    throw new Error("Production deployment has an invalid readiness state.");
  if (deployment.readySubstate === "STAGED")
    throw new PromotionConvergencePendingError(
      "Production deployment is still staged.",
    );

  // The caller queried v13 by the production hostname. Vercel documents
  // `alias` as optional creation-time metadata, so the exact returned ID is
  // the binding assertion; the separate public smoke proves served bytes.
  assertDeploymentApiContract(deployment, expected, "promoted");
}
