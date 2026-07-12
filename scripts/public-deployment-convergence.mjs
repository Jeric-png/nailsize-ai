export async function waitForPublicDeploymentConvergence({
  verify,
  timeoutMilliseconds = 60_000,
  intervalMilliseconds = 5_000,
  now = () => performance.now(),
  wait = (milliseconds) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds)),
}) {
  if (
    typeof verify !== "function" ||
    typeof now !== "function" ||
    typeof wait !== "function"
  )
    throw new Error("Public convergence callbacks are required.");
  if (!Number.isSafeInteger(timeoutMilliseconds) || timeoutMilliseconds <= 0)
    throw new Error("Public convergence timeout is invalid.");
  if (!Number.isSafeInteger(intervalMilliseconds) || intervalMilliseconds < 0)
    throw new Error("Public convergence interval is invalid.");

  const startedAt = now();
  if (!Number.isFinite(startedAt))
    throw new Error("Public convergence clock is invalid.");
  const deadline = startedAt + timeoutMilliseconds;
  let lastError;

  while (true) {
    const remainingMilliseconds = Math.floor(deadline - now());
    if (remainingMilliseconds <= 0) break;
    try {
      return await verify({ deadline, remainingMilliseconds });
    } catch (error) {
      lastError = error;
    }

    const remainingAfterAttempt = Math.floor(deadline - now());
    if (remainingAfterAttempt <= 0) break;
    await wait(Math.min(intervalMilliseconds, remainingAfterAttempt));
  }

  if (lastError) throw lastError;
  throw new Error("Public deployment convergence timed out.");
}
