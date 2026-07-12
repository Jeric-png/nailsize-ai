import assert from "node:assert/strict";
import test from "node:test";
import { waitForPublicDeploymentConvergence } from "./public-deployment-convergence.mjs";

test("retries transient public edge responses until verification succeeds", async () => {
  let clock = 0;
  let attempts = 0;
  const result = await waitForPublicDeploymentConvergence({
    verify: async ({ remainingMilliseconds }) => {
      attempts += 1;
      assert.ok(remainingMilliseconds > 0);
      if (attempts === 1) throw new Error("old artifact digest");
      if (attempts === 2) throw new Error("HTTP 503");
      return { status: "ok" };
    },
    timeoutMilliseconds: 60_000,
    intervalMilliseconds: 5_000,
    now: () => clock,
    wait: async (milliseconds) => {
      clock += milliseconds;
    },
  });

  assert.deepEqual(result, { status: "ok" });
  assert.equal(attempts, 3);
  assert.equal(clock, 10_000);
});

test("does not retry beyond the monotonic public convergence deadline", async () => {
  let clock = 0;
  let attempts = 0;
  await assert.rejects(
    waitForPublicDeploymentConvergence({
      verify: async ({ remainingMilliseconds }) => {
        attempts += 1;
        assert.equal(remainingMilliseconds, 50);
        clock = 50;
        throw new Error("edge still stale");
      },
      timeoutMilliseconds: 50,
      intervalMilliseconds: 10,
      now: () => clock,
      wait: async (milliseconds) => {
        clock += milliseconds;
      },
    }),
    /edge still stale/u,
  );
  assert.equal(attempts, 1);
  assert.equal(clock, 50);
});
