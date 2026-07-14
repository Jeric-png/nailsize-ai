import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { existsSync, writeFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import {
  buildVercelCurlArguments,
  fetchProtectedVercelDeployment,
  parseVercelCurlHeaders,
} from "./vercel-curl-fetch.mjs";

test("builds a bounded shell-free Vercel curl request without credentials", () => {
  const arguments_ = buildVercelCurlArguments(
    new URL("https://candidate.vercel.app/assets/app.js"),
    2_000_000,
    path.resolve("headers"),
    path.resolve("body"),
  );

  assert.deepEqual(arguments_.slice(0, 3), [
    "curl",
    "/assets/app.js",
    "--deployment",
  ]);
  assert.equal(
    arguments_[arguments_.indexOf("--deployment") + 1],
    "https://candidate.vercel.app",
  );
  assert.ok(arguments_.includes("--max-filesize"));
  assert.ok(arguments_.includes("2000000"));
  assert.ok(arguments_.includes("--max-time"));
  assert.ok(arguments_.includes("--compressed"));
  assert.ok(arguments_.includes("--no-include"));
  assert.ok(arguments_.includes("--dump-header"));
  assert.ok(arguments_.includes("--output"));
  assert.doesNotMatch(arguments_.join(" "), /token|protection-bypass/iu);
});

test("parses the last complete strict curl header block", () => {
  const { status, headers } = parseVercelCurlHeaders(
    "HTTP/1.1 100 Continue\r\n\r\n" +
      "HTTP/2 200\r\nContent-Type: text/html; charset=utf-8\r\n" +
      "X-Frame-Options: DENY\r\n\r\n",
  );

  assert.equal(status, 200);
  assert.equal(headers.get("content-type"), "text/html; charset=utf-8");
  assert.equal(headers.get("x-frame-options"), "DENY");
});

test("rejects malformed or folded curl response headers", () => {
  assert.throws(
    () => parseVercelCurlHeaders("HTTP/2 200\nContent-Type: text/html\n\n"),
    /status is malformed/u,
  );
  assert.throws(
    () =>
      parseVercelCurlHeaders(
        "HTTP/2 200\r\nContent-Type: text/html\r\n continued\r\n\r\n",
      ),
    /folded headers/u,
  );
  assert.throws(
    () => parseVercelCurlHeaders("HTTP/2 100\r\n\r\n"),
    /interim response/u,
  );
});

test("runs Vercel curl without a shell or credential-bearing arguments", async () => {
  let temporaryHeaderPath;
  let temporaryBodyPath;
  const response = await fetchProtectedVercelDeployment(
    "https://candidate.vercel.app/",
    512_000,
    {
      environment: { PATH: process.env.PATH, VERCEL_TOKEN: "test-token" },
      spawnImplementation(command, arguments_, options) {
        assert.equal(command, "vercel");
        assert.equal(options.shell, false);
        assert.equal(options.stdio, "ignore");
        assert.equal(options.env.NO_COLOR, "1");
        assert.doesNotMatch(arguments_.join(" "), /test-token/u);
        temporaryHeaderPath =
          arguments_[arguments_.indexOf("--dump-header") + 1];
        temporaryBodyPath = arguments_[arguments_.indexOf("--output") + 1];
        assert.equal(arguments_[1], "/");
        assert.equal(
          arguments_[arguments_.indexOf("--deployment") + 1],
          "https://candidate.vercel.app",
        );
        writeFileSync(
          temporaryHeaderPath,
          "HTTP/2 200\r\nContent-Type: text/html\r\n\r\n",
        );
        writeFileSync(temporaryBodyPath, "<title>NailSize Guide</title>");
        const child = new EventEmitter();
        queueMicrotask(() => child.emit("close", 0));
        return child;
      },
    },
  );

  assert.equal(response.status, 200);
  assert.equal(
    await new Response(response.body).text(),
    "<title>NailSize Guide</title>",
  );
  assert.equal(existsSync(temporaryHeaderPath), false);
  assert.equal(existsSync(temporaryBodyPath), false);
});
