// Exercise the actual stream parser/transport without a server or model calls.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const webRoot = path.resolve(__dirname, "../apps/web");
const ts = createRequire(path.join(webRoot, "package.json"))("typescript");
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file);
  const helper = { exports: {} };
  const compiled = ts.transpileModule(fs.readFileSync(file, "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const localRequire = (ref) => load(path.resolve(path.dirname(file), ref + ".ts"));
  new Function("exports", "module", "require", compiled)(helper.exports, helper, localRequire);
  cache.set(file, helper.exports);
  return helper.exports;
}
const { readPreviewStream, requestProgressPreview, previewProgressVersion } = load(path.join(webRoot, "src/shared/api/previewProgress.ts"));
const { waitingStepStates, waitingMessage, hasFreshWaitingSignal, formatWaitingElapsed } = load(path.join(webRoot, "src/features/service/experience/waitingModel.ts"));
const payload = { birth_date: "1997-09-18", birth_time: "14:30", region_id: "kr-seoul", locale: "ko" };
const data = { trace_id: "synthetic", result: { text: "한글 문장" }, pipeline_status: {} };
const frame = (item) => JSON.stringify({ version: previewProgressVersion, ...item }) + "\n";
const good = [frame({ type: "stage", stage: "accepted" }), frame({ type: "stage", stage: "calculating" }), frame({ type: "heartbeat" }), frame({ type: "stage", stage: "writing" }), frame({ type: "result", data })].join("");
function stream(text, bytewise = false) {
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({ start(controller) {
    if (bytewise) for (const byte of bytes) controller.enqueue(Uint8Array.of(byte));
    else controller.enqueue(bytes);
    controller.close();
  } });
}
function response(text, status = 200) {
  return new Response(stream(text), { status, headers: { "Content-Type": "application/x-ndjson" } });
}
let checks = 0;
async function check(name, verify) { await verify(); checks++; console.log(`PASS ${name}`); }
async function main() {
  await check("UTF-8 byte boundaries and combined frames retain the result and actual stages", async () => {
    const signals = [];
    assert.deepEqual(await readPreviewStream(stream(good, true), "ko", (value) => signals.push(value)), data);
    assert.deepEqual(signals.map((item) => item.stage), ["accepted", "calculating", "calculating", "writing"]);
    assert.ok(signals.every((item) => item.lastSignalAt > 0));
  });
  await check("truncated stream, unknown version, skipped/backward stages and malformed JSON fail", async () => {
    for (const text of [good.slice(0, good.indexOf('"type":"result"') - 1), "{}\n", "null\n", "garbage\n",
      frame({ type: "stage", stage: "writing" }), frame({ type: "stage", stage: "accepted" }) + frame({ type: "stage", stage: "accepted" })])
      await assert.rejects(readPreviewStream(stream(text), "ko", () => {}), /연결/);
  });
  await check("terminal errors are localized and do not expose raw diagnostics", async () => {
    await assert.rejects(readPreviewStream(stream(frame({ type: "error", status: 422, error: { error_code: "INPUT_SCHEMA_ERROR", message: "private diagnostics" } })), "ko", () => {}), /생년월일/);
    await assert.rejects(readPreviewStream(stream(frame({ type: "error", status: 500, error: { message: "private diagnostics" } })), "en", () => {}), /Couldn't load/);
  });
  await check("one progress request delivers the final result without a second generation", async () => {
    const calls = [];
    const result = await requestProgressPreview({ baseUrl: "/api", payload, onProgress: () => {}, fetcher: async (url) => { calls.push(url); return response(good); } });
    assert.deepEqual(result, data);
    assert.deepEqual(calls, ["/api/saju/preview-stream"]);
  });
  await check("category reading uses only its own stream and JSON fallback endpoints", async () => {
    for (const status of [200, 404]) {
      const calls = [];
      await requestProgressPreview({ baseUrl: "/api", payload, endpoint: "/saju/reading", onProgress: () => {}, fetcher: async (url) => {
        calls.push(url);
        return calls.length === 1 ? (status === 200 ? response(good) : new Response("Not found", {status})) : Response.json(data);
      }});
      assert.deepEqual(calls, status === 200 ? ["/api/saju/reading-stream"] : ["/api/saju/reading-stream", "/api/saju/reading"]);
    }
  });
  await check("only a missing endpoint uses legacy JSON and never pretends calculation is complete", async () => {
    for (const status of [404, 405]) {
      const calls = [], states = [];
      await requestProgressPreview({ baseUrl: "/api", payload, onProgress: (value) => states.push(value), fetcher: async (url) => {
        calls.push(url);
        return calls.length === 1 ? new Response("Not found", { status }) : Response.json(data);
      } });
      assert.deepEqual(calls, ["/api/saju/preview-stream", "/api/saju/preview"]);
      assert.deepEqual(states, [{ stage: "waiting", lastSignalAt: null, transport: "legacy" }]);
    }
  });
  await check("network, provider and broken-stream failures never automatically retry", async () => {
    for (const make of [() => { throw new Error("network ended"); }, () => response("{}\n"), () => new Response("failure", { status: 500 })]) {
      let calls = 0;
      await assert.rejects(requestProgressPreview({ baseUrl: "/api", payload, onProgress: () => {}, fetcher: async () => { calls++; return make(); } }));
      assert.equal(calls, 1);
    }
  });
  await check("heartbeat/elapsed time do not advance stages or invent completed legacy work", () => {
    assert.deepEqual(waitingStepStates("sending"), ["active", "pending", "pending"]);
    assert.deepEqual(waitingStepStates("calculating"), ["done", "active", "pending"]);
    assert.deepEqual(waitingStepStates("writing"), ["done", "done", "active"]);
    assert.deepEqual(waitingStepStates("waiting"), ["pending", "pending", "pending"]);
    for (const locale of ["ko", "en"]) {
      assert.doesNotMatch(waitingMessage({ stage: "waiting", transport: "legacy", lastSignalAt: null }, 400, locale), /끝났|calculated|complete/);
      assert.equal(waitingMessage({ stage: "calculating", transport: "stream", lastSignalAt: 1 }, 400, locale), waitingMessage({ stage: "calculating", transport: "stream", lastSignalAt: 1 }, 0, locale));
    }
    assert.equal(formatWaitingElapsed(185.5), "3:05");
    assert.equal(formatWaitingElapsed(-1), "0:00");
    assert.equal(hasFreshWaitingSignal({ stage: "writing", transport: "stream", lastSignalAt: 1000 }, 11000), true);
    assert.equal(hasFreshWaitingSignal({ stage: "writing", transport: "stream", lastSignalAt: 1000 }, 31001), false);
    assert.equal(hasFreshWaitingSignal({ stage: "waiting", transport: "legacy", lastSignalAt: null }, 11000), false);
  });
  console.log(`Web progress checks: ${checks} passed.`);
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
