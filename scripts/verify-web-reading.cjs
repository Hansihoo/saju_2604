// Test the pure input/error/reading helpers using the existing TypeScript compiler.
// No browser, provider calls, generated files, or extra test dependency required.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const webRoot = path.resolve(__dirname, "../apps/web");
const ts = createRequire(path.join(webRoot, "package.json"))("typescript");

function loadHelper(relativePath) {
  const source = fs.readFileSync(path.join(webRoot, "src", relativePath), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const helper = { exports: {} };
  new Function("exports", "module", compiled)(helper.exports, helper);
  return helper.exports;
}

const { isValidBirthDate } = loadHelper("features/service/experience/validateBirthDate.ts");
const { getApiErrorMessage } = loadHelper("shared/api/errorMessage.ts");
const { getPrimaryReadingNotice, getReadingNotices, getShareLimitation } = loadHelper("features/service/experience/readingNotices.ts");
const { getReadingBasis } = loadHelper("features/service/experience/readingBasis.ts");
const { entryTopics } = loadHelper("features/service/experience/experienceCopy.ts");
const contentKnowledge = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../docs/ai/PRODUCT_CONTENT_KNOWLEDGE.json"), "utf8"));
function entryPolicyViolations(topics) {
  const guard = contentKnowledge.entry_guard;
  return topics.flatMap((topic) => {
    const violations = [];
    if (guard.forbidden_topic_ids.includes(topic.key)) violations.push(`QF-001: ${topic.key}`);
    for (const locale of ["ko", "en"]) {
      const visible = [topic.label?.[locale], topic.question?.[locale]].filter(Boolean).join(" ");
      if (guard.forbidden_patterns[locale].some((pattern) => new RegExp(pattern, "i").test(visible)))
        violations.push(`QF-001: ${locale}: ${visible}`);
    }
    return violations;
  });
}
let checks = 0;
function check(name, verify) {
  verify();
  checks++;
  console.log(`PASS ${name}`);
}

check("entry respects the recorded future-interest editorial policy", () => {
  assert.equal(contentKnowledge.schema_version, "product-content-knowledge-v1");
  assert.deepEqual(entryPolicyViolations(entryTopics), []);
});
check("reintroduced personality topics and rejected KO/EN hooks fail the entry guard", () => {
  assert.ok(entryPolicyViolations([{ key: "core", label: { ko: "내 사주", en: "My chart" } }]).length);
  for (const locale of ["ko", "en"]) {
    for (const phrase of contentKnowledge.entry_guard.rejected_examples[locale]) {
      const topic = { key: "love", label: { ko: "연애운", en: "Love fortune" }, question: { [locale]: phrase } };
      assert.ok(entryPolicyViolations([topic]).length, phrase);
    }
  }
});

check("solar invalid dates and century leap years", () => {
  for (const input of ["1997-02-31", "1900-02-29", "1997-04-31", "0000-01-01", "1997-13-01"])
    assert.equal(isValidBirthDate(input, "solar"), false, input);
  for (const input of ["2000-02-29", "1996-02-29", "1997-09-18"])
    assert.equal(isValidBirthDate(input, "solar"), true, input);
});
check("lunar calendar avoids Gregorian day validation", () => {
  assert.equal(isValidBirthDate("1990-02-30", "lunar"), true);
  assert.equal(isValidBirthDate("1990-02-31", "lunar"), false);
});
check("API errors are localized and never display diagnostics", () => {
  assert.match(getApiErrorMessage(422, { error_code: "INPUT_SCHEMA_ERROR", message: "internal secret" }, "ko"), /생년월일/);
  assert.match(getApiErrorMessage(400, { detail: { error_code: "REGION_NOT_SELECTED" } }, "en"), /birthplace/);
  for (const body of [null, "<html>trace data</html>", { message: "internal secret", error_code: "INTERNAL_SERVER_ERROR" }]) {
    assert.doesNotMatch(getApiErrorMessage(500, body, "ko"), /html|trace|internal|secret|error_code/i);
    assert.match(getApiErrorMessage(500, body, "en"), /try again/);
  }
  assert.match(getApiErrorMessage(429, {}, "ko"), /조금 뒤/);
});
const critical = {
  code: "day_pillar_uncertain_due_to_unknown_time", severity: "critical", user_message: "Day pillar may change.",
};
check("critical unknown-time warning is preserved and localized", () => {
  const result = { result: { hour_pillar_enabled: false, uncertainty_summary: [critical, critical] } };
  assert.equal(getReadingNotices(result, "ko").length, 1);
  assert.match(getReadingNotices(result, "ko")[0], /하루 기준과 풀이/);
  assert.equal(getReadingNotices(result, "en")[0], critical.user_message);
  assert.match(getShareLimitation(result, "ko"), /출생시간 미상/);
  assert.match(getShareLimitation(result, "en"), /unknown/);
});
check("informational flags do not add share restrictions", () => {
  const result = { result: { hour_pillar_enabled: true, uncertainty_summary: [{ ...critical, severity: "info" }] } };
  assert.deepEqual(getReadingNotices(result, "ko"), []);
  assert.equal(getShareLimitation(result, "ko"), undefined);
});
check("unrecognized critical codes retain a safe visible warning", () => {
  const result = { result: { hour_pillar_enabled: true, uncertainty_summary: [{ ...critical, code: "future_boundary" }] } };
  assert.match(getReadingNotices(result, "ko")[0], /달라질/);
  assert.match(getShareLimitation(result, "ko"), /달라질/);
});
check("compact notice keeps date uncertainty ahead of calculation differences", () => {
  const result = { result: { hour_pillar_enabled: false, uncertainty_summary: [
    { ...critical, code: "luck_cycle_start_age_changed", severity: "warning" }, critical,
  ] } };
  assert.match(getPrimaryReadingNotice(result, "ko"), /하루 기준과 풀이/);
  assert.equal(getReadingNotices(result, "ko").length, 2);
  assert.equal(getPrimaryReadingNotice({ result: { hour_pillar_enabled: true, uncertainty_summary: [] } }, "ko"), undefined);
});
check("reading basis preserves supplied facts and the actual advice", () => {
  const basis = getReadingBasis({
    basis_line: "old basis",
    user_takeaway: " Agree on the deadline. ",
    basis_explanation: {
      facts: [" Month signal: officer ", "Month signal: officer", " "],
      reading: " Read through responsibility and deadlines. ",
    },
  });
  assert.deepEqual(basis, {
    facts: ["Month signal: officer"],
    reading: "Read through responsibility and deadlines.",
    takeaway: "Agree on the deadline.",
  });
});
check("legacy basis has no invented interpretation or advice connection", () => {
  const basis = getReadingBasis({ basis_line: " Supplied older basis. ", user_takeaway: "a different claim" });
  assert.deepEqual(basis, { facts: ["Supplied older basis."] });
  assert.equal(basis.reading, undefined);
  assert.equal(basis.takeaway, undefined);
});
check("missing or incomplete explanations never fabricate a basis", () => {
  for (const explanation of [null, { facts: [], reading: "unverified claim" }, { facts: ["checked"], reading: " " }]) {
    assert.equal(getReadingBasis({ basis_line: "", user_takeaway: "prediction", basis_explanation: explanation }), null);
  }
});
console.log(`Web reading helper checks: ${checks} passed.`);
