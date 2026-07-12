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
  if (payload.id !== expected.deploymentId)
    throw new Error("Vercel API returned a different deployment ID.");
  if (payload.url !== expected.deploymentHost)
    throw new Error(
      "Vercel API returned a different generated deployment URL.",
    );
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
    if (!aliases.includes(expected.productionHost))
      throw new Error(
        "Production hostname does not point to the verified deployment.",
      );
    if (payload.readySubstate && payload.readySubstate !== "PROMOTED")
      throw new Error(
        "Production deployment is not in Vercel's promoted state.",
      );
  }
}
