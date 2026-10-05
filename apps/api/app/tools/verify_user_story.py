"""Run repeatable, tokenless HTTP checks against the already-running local app.

This checks observable contracts and content defects, not prediction accuracy or
real users' enjoyment. It deliberately imports no application/provider code.
The provider preflight must prove fallback before any POST, and every POST asks
the API's verification guard to reject a provider mismatch. Reports contain
fixture names and selected comparison evidence, never request payloads or logs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


TOPIC_KEYS = {"core", "love", "work_money", "luck_flow"}
ELEMENTS = ("wood", "fire", "earth", "metal", "water")
ELEMENT_KO = dict(zip(ELEMENTS, ("목", "화", "토", "금", "수")))
TEN_GOD_KO = dict(zip(("比肩", "劫財", "劫财", "食神", "傷官", "伤官", "偏財", "偏财", "正財", "正财", "偏官", "正官", "偏印", "正印", "日主"),
                     ("비견", "겁재", "겁재", "식신", "상관", "상관", "편재", "편재", "정재", "정재", "편관", "정관", "편인", "정인", "일간")))
TEN_GOD_KO.update({"七杀": "편관", "七殺": "편관"})
TEN_GOD_EN = dict(zip(("비견", "겁재", "식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인", "일간"),
                     ("Peer", "Rival", "Expression", "Output", "Indirect Wealth", "Direct Wealth", "Seven Killings", "Direct Officer", "Indirect Resource", "Direct Resource", "Day master")))
STEM_KO = dict(zip("甲乙丙丁戊己庚辛壬癸", ("갑", "을", "병", "정", "무", "기", "경", "신", "임", "계")))
STEM_EN = dict(zip("甲乙丙丁戊己庚辛壬癸", ("Gap", "Eul", "Byeong", "Jeong", "Mu", "Gi", "Gyeong", "Sin", "Im", "Gye")))
BRANCH_KO = dict(zip("子丑寅卯辰巳午未申酉戌亥", ("자", "축", "인", "묘", "진", "사", "오", "미", "신", "유", "술", "해")))
BRANCH_EN = dict(zip("子丑寅卯辰巳午未申酉戌亥", ("Ja", "Chuk", "In", "Myo", "Jin", "Sa", "O", "Mi", "Sin", "Yu", "Sul", "Hae")))
SECTION_KEYS = ("core_analysis", "love", "career", "wealth", "luck_flow")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[4] / "docs/ai/USER_STORY_VERIFICATION.json"
MAX_RESPONSE_BYTES = 2_000_000
KNOWLEDGE_CATALOG = Path(__file__).resolve().parents[1] / "domain/saju/data/reading_knowledge/catalog.json"
READING_ROLES = ("answer", "scene", "tradeoff", "action")
READING_KINDS = ("interpretation", "illustration", "interpretation", "advice")
UNSUPPORTED_QUESTIONS = {
    "love.meeting_window": ("needs_rule_review", "relationship_pattern_only"),
    "career.entry_window": ("needs_rule_review", "work_style_only"),
    "career.recognition_window": ("needs_rule_review", "role_and_responsibility_only"),
    "career.reward_window": ("needs_rule_review", "reward_conditions_only"),
    "fortune.population_comparison": ("needs_reference_population", "no_population_comparison"),
}
FORBIDDEN_QUESTION_CLAIMS = {"event_probability", "guaranteed_event_date", "population_percentile"}


class VerificationBlocked(RuntimeError):
    """A precondition failed; do not continue generating reports."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def local_base(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError("Only credential-free loopback HTTP base URLs are allowed.")
    return value.rstrip("/")


@dataclass
class HttpResult:
    status: int
    data: Any
    content_type: str


class LocalHttp:
    def __init__(self, timeout: float = 15, total_timeout: float = 180):
        self.timeout = timeout
        self.deadline = time.monotonic() + total_timeout
        self.opener = build_opener(NoRedirect)

    def request(self, base: str, path: str = "", payload: Optional[Dict[str, Any]] = None,
                *, accept: str = "application/json") -> HttpResult:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise VerificationBlocked("Overall runtime verification deadline exceeded.")
        headers = {"Accept": accept}
        body = None
        if payload is not None:
            headers.update({"Content-Type": "application/json", "X-Saju-Verification-Provider": "fallback"})
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(base + path, data=body, headers=headers)
        try:
            response = self.opener.open(request, timeout=min(self.timeout, remaining))
        except HTTPError as exc:
            response = exc
        except (URLError, TimeoutError, OSError) as exc:
            raise VerificationBlocked("Local HTTP request failed (%s)." % type(exc).__name__) from exc
        with response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise VerificationBlocked("Response exceeds verification size limit.")
            content_type = response.headers.get("Content-Type", "")
            if "json" in content_type:
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (ValueError, UnicodeDecodeError) as exc:
                    raise VerificationBlocked("API returned invalid JSON.") from exc
            else:
                data = raw.decode("utf-8", errors="replace")
            return HttpResult(response.code, data, content_type)


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def natal_facts(response: Dict[str, Any]) -> Dict[str, Any]:
    """Exclude trace IDs and current-period clocks from deterministic comparison."""
    manse = response.get("manse", {})
    result = response.get("result", {})
    return {
        "pillars": manse.get("pillars"), "elements": manse.get("elements"),
        "luck_cycles": manse.get("luck_cycles"), "signals": result.get("signals"),
        "basis": result.get("calculation_basis"),
        "time_correction": response.get("time_correction"),
        "regional_solar_correction": response.get("regional_solar_correction"),
    }


def card_map(response: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cards = response.get("result", {}).get("free_preview", {}).get("cards", [])
    return {card.get("key", ""): card for card in cards if isinstance(card, dict)}


def basis_structure(value: Any) -> Tuple[bool, Dict[str, Any]]:
    """Check API shape/length only; this does not establish factual relevance."""
    if not isinstance(value, dict):
        return False, {"present": False}
    facts, reading = value.get("facts"), value.get("reading")
    valid = (isinstance(facts, list) and 1 <= len(facts) <= 3
             and all(isinstance(item, str) and item.strip() and len(item) <= 96 for item in facts)
             and isinstance(reading, str) and bool(reading.strip()) and len(reading) <= 360)
    return bool(valid), {"present": True, "fact_count": len(facts) if isinstance(facts, list) else None,
                         "fact_lengths": [len(item) if isinstance(item, str) else None for item in facts] if isinstance(facts, list) else [],
                         "reading_chars": len(reading) if isinstance(reading, str) else None}


def localized_ten_god(value: Optional[str], locale: str) -> Optional[str]:
    canonical = TEN_GOD_KO.get(value, value)
    return canonical if locale == "ko" else TEN_GOD_EN.get(canonical, canonical)


def compact_cycle_period(cycle: Dict[str, Any], locale: str) -> str:
    start, end = cycle.get("start_datetime"), cycle.get("change_datetime")
    if (isinstance(start, str) and isinstance(end, str)
            and re.match(r"^\d{4}-\d{2}", start) and re.match(r"^\d{4}-\d{2}", end)):
        return (f"{start[:4]}년 {int(start[5:7])}월 ~ {end[:4]}년 {int(end[5:7])}월" if locale == "ko"
                else f"{start[:7]} to {end[:7]}")
    return f"{cycle.get('start_year')} ~ {cycle.get('end_year')}"


def knowledge_catalog() -> Dict[str, Any]:
    """Read the checked-in policy data without invoking the application/LLM."""
    try:
        value = json.loads(KNOWLEDGE_CATALOG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise VerificationBlocked("Checked-in reading knowledge catalog cannot be read.") from exc
    if not isinstance(value, dict) or value.get("schema_version") != "saju-knowledge-v1":
        raise VerificationBlocked("Checked-in reading knowledge catalog has an unsupported contract.")
    return value


def canonical_ten_god(value: Optional[str]) -> Optional[str]:
    return TEN_GOD_KO.get(value, {label: key for key, label in TEN_GOD_EN.items()}.get(value, value))


def knowledge_cycle_period(cycle: Dict[str, Any], locale: str) -> str:
    """Format supplied dates as the payload does; do not calculate a cycle."""
    dates = (cycle.get("start_datetime"), cycle.get("change_datetime"))
    if all(isinstance(value, str) and re.match(r"^\d{4}-\d{2}", value) for value in dates):
        labels = [f"{value[:4]}년 {int(value[5:7])}월" if locale == "ko" else value[:7] for value in dates]
        return " ~ ".join(labels)
    return f"{cycle.get('start_year')}-{cycle.get('end_year')}"


def display_cycle_gan_zhi(cycle: Dict[str, Any], locale: str) -> Optional[str]:
    """Localize an existing public pillar string; never calculate a pillar."""
    raw = cycle.get("gan_zhi")
    stems, branches = (STEM_KO, BRANCH_KO) if locale == "ko" else (STEM_EN, BRANCH_EN)
    if not isinstance(raw, str) or len(raw) != 2 or raw[0] not in stems or raw[1] not in branches:
        return None
    return stems[raw[0]] + ("" if locale == "ko" else "-") + branches[raw[1]]


def unavailable_luck_assertions(report: Dict[str, Any], *, restricted: bool) -> List[Dict[str, str]]:
    """Catch only confirmed fallback regressions when cycles are unavailable.

    The exact phrases below previously asserted current/next cycle facts for
    unknown birth times. This is not a general semantic verifier. Merely saying
    'current/next cycles were not calculated' must remain valid limitation copy.
    """
    if not restricted:
        return []
    confirmed_phrases = {
        "invented_pre_first_cycle": "첫 대운이 시작되기 전의 현재 구간",
        "invented_current_cycle_improvement": "현재 대운에서 좋아지는 점",
        "invented_next_cycle_outcome": "다음 대운에서는 지금 정리한 기준",
        "invented_current_flow_en": "the current flow asks for a pause",
        "invented_next_cycle_preparation_en": "preparing for the next cycle",
    }
    # These negatives are close to the particular phrase, not arbitrary words
    # elsewhere in a paragraph (e.g. 'do not overspend' does not excuse a claim).
    limitation = re.compile(r"^(?:을|를|은|는|으로|에\s*대한\s*판단을)?\s*(?:"
                            r"(?:확인|판단|단정|사용|산출|제시|표시|계산|대입|정)"
                            r"(?:하지(?:는)?\s*않|할\s*수(?:는)?\s*없)|알\s*수\s*없)")
    english_limitation_after = re.compile(
        r"^[\s\"'’”]*(?:(?:is|are|was|were|will\s+be)\s+)?"
        r"(?:not\s+(?:asserted|claimed|calculated|confirmed|used|shown|available|recommended)|"
        r"cannot\s+be\s+(?:asserted|claimed|calculated|confirmed)|unavailable|unknown)", re.IGNORECASE)
    english_limitation_before = re.compile(
        r"(?:(?:do|does|did|must|will)\s+not|cannot)\s+(?:assert|claim|assume|say)(?:\s+that)?$", re.IGNORECASE)
    found = []
    blocks = [(key, report.get(key) or {}) for key in ("summary", *SECTION_KEYS)]
    # The same regression can leak into the first preview, before free-detail.
    for card in report.get("cards", []):
        blocks.append(("preview_card:" + card.get("key", ""),
                       {"title": card.get("title", ""), "body": "\n".join(card.get("preview_paragraphs", [])),
                        "overview": card.get("user_takeaway", "")}))
    for block_key, block in blocks:
        for field in ("title", "headline", "overview", "body"):
            text = block.get(field, "")
            if not isinstance(text, str):
                continue
            for line in re.split(r"[\n.!?]", text):
                normalized = re.sub(r"\s+", " ", line).strip()
                for code, phrase in confirmed_phrases.items():
                    position = normalized.casefold().find(phrase.casefold())
                    if position < 0:
                        continue
                    after = normalized[position + len(phrase):]
                    before = normalized[:position].rstrip(" \"'‘“")
                    if (limitation.search(after) or english_limitation_after.search(after)
                            or english_limitation_before.search(before)):
                        continue
                    found.append({"code": code, "block": block_key, "field": field,
                                  "excerpt": normalized[max(0, position - 35):position + 180]})
    return found


def check_periods(response: Dict[str, Any], started: datetime, finished: datetime) -> Tuple[bool, Dict[str, Any]]:
    flows = response.get("period_flows", {})
    today, month = flows.get("today", {}), flows.get("month", {})
    evidence = {"timezone_id": flows.get("timezone_id"), "as_of": flows.get("as_of"),
                "today_start": today.get("period_start"), "today_end": today.get("period_end"),
                "month_start": month.get("period_start"), "month_end": month.get("period_end")}
    try:
        as_of = datetime.fromisoformat(flows["as_of"])
        expected_zone = response["region"]["tzid"]
        # The checked-in domestic catalog uses Asia/Seoul. Do not silently
        # invent offsets for an unsupported catalog/timezone.
        zone_ok = (expected_zone == "Asia/Seoul" and flows["timezone_id"] == expected_zone
                   and as_of.utcoffset() == timedelta(hours=9))
        clock_ok = started - timedelta(seconds=15) <= as_of <= finished + timedelta(seconds=15)
        date_ok = today["period_start"] == today["period_end"] == as_of.date().isoformat()
        start = datetime.fromisoformat(month["period_start"]).replace(tzinfo=as_of.tzinfo)
        end = datetime.fromisoformat(month["period_end"]).replace(tzinfo=as_of.tzinfo)
        month_ok = start <= as_of < end and timedelta(days=20) <= end - start <= timedelta(days=40)
        evidence.update({"zone_matches_birth_region": zone_ok, "clock_in_request_window": clock_ok,
                         "solar_term_window_contains_as_of": month_ok})
        return zone_ok and clock_ok and date_ok and month_ok, evidence
    except (KeyError, ValueError, TypeError):
        return False, evidence


class UserStoryVerifier:
    def __init__(self, client: LocalHttp, api_base: str, web_base: str):
        self.client, self.api_base, self.web_base = client, local_base(api_base), local_base(web_base)
        self.checks: List[Dict[str, Any]] = []
        self.cases: List[Dict[str, Any]] = []
        self.responses: Dict[str, Dict[str, Any]] = {}
        self.preflight_recorded = False
        self.unobservable_luck_fact_recorded = False

    def add(self, key: str, status: str, category: str, evidence: Dict[str, Any]) -> None:
        self.checks.append({"id": key, "status": status, "category": category, "evidence": evidence})

    def verify(self, key: str, passed: bool, evidence: Dict[str, Any], category: str = "functional") -> None:
        self.add(key, "PASS" if passed else "FAIL", category, evidence)

    def provider_preflight(self) -> None:
        result = self.client.request(self.api_base, "/verification/provider")
        config = result.data if result.status == 200 and isinstance(result.data, dict) else {}
        provider = config.get("configured_provider")
        confirmed = provider == "fallback" and config.get("fallback_only") is True
        if not self.preflight_recorded or not confirmed:
            self.verify("safety.provider_preflight", confirmed,
                        {"http_status": result.status,
                         "configured_provider": provider if provider in {"openai", "codex", "fallback"} else "unconfirmed",
                         "fallback_only": config.get("fallback_only") is True})
            self.preflight_recorded = True
        if not confirmed:
            raise VerificationBlocked("Runtime provider is not confirmed as fallback; no further POST requests sent.")

    def check_basis(self, fixture: str, payload: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Compare selected explanation facts to public calculation fields.

        Shape checks and narrow fact comparisons are separate. No attempt is
        made to prove the complete meaning or predictive validity of 'reading'.
        """
        locale = payload.get("locale", "ko")
        estimated = payload.get("is_birth_time_estimated") is True
        public, manse = response.get("result", {}), response.get("manse", {})
        cards, valid = card_map(response), {}
        flows = response.get("period_flows", {})
        for key, block in [*cards.items(), *[(kind, flows.get(kind, {})) for kind in ("today", "month")]]:
            explanation = block.get("basis_explanation")
            shape_ok, evidence = basis_structure(explanation)
            self.verify(fixture + ".basis_" + key + "_structure", shape_ok, evidence)
            if shape_ok:
                valid[key] = explanation
        pillars = manse.get("pillars", {})
        for key, pillar, field, marker in (
            ("work_money", "month", "stem_ten_god", "월간" if locale == "ko" else "month stem"),
            ("love", "day", "branch_ten_god", "배우자궁" if locale == "ko" else "spouse house"),
        ):
            if key not in valid or cards.get(key, {}).get("reading_structure") is not None:
                continue
            expected = localized_ten_god(pillars.get(pillar, {}).get(field), locale)
            fact = valid[key]["facts"][0]
            actual = fact.split(":", 1)[1].strip() if ":" in fact else None
            self.verify(fixture + ".basis_" + key + "_fact_values", bool(expected) and actual == expected and marker in fact,
                        {"source_field": "manse.pillars." + pillar + "." + field, "expected_signal": expected,
                         "actual_signal": actual, "fact": fact}, "content")
        if "core" in valid and cards.get("core", {}).get("reading_structure") is None:
            facts = valid["core"]["facts"]
            labels = ELEMENT_KO if locale == "ko" else {key: key for key in ELEMENTS}
            counts = manse.get("elements", {})
            dominant = public.get("signals", {}).get("dominant_elements", [])[:2]
            count_pattern = r"(목|화|토|금|수)\s+(\d+)개" if locale == "ko" else r"\b(wood|fire|earth|metal|water)\s+(\d+)\b"
            stated = [(label, int(count)) for label, count in re.findall(count_pattern, facts[0])]
            expected = [(labels[item], counts.get(item)) for item in dominant if item in labels]
            missing = public.get("signals", {}).get("missing_elements", [])
            missing_fact = next((fact for fact in facts if ("없는 오행:" if locale == "ko" else "absent from the visible pillars:") in fact), None)
            expected_missing = [labels[item] for item in missing if item in labels]
            actual_missing = [item.strip() for item in missing_fact.split(":", 1)[1].split(",")] if missing_fact else []
            correct = (bool(expected) and stated == expected and all(counts.get(item, 0) > 0 for item in dominant)
                       and actual_missing == expected_missing and all(counts.get(item) == 0 for item in missing))
            self.verify(fixture + ".basis_core_fact_values", correct,
                        {"expected_dominant_counts": expected, "stated_counts": stated,
                         "expected_missing_elements": expected_missing, "stated_missing_elements": actual_missing}, "content")
        if "luck_flow" in valid:
            explanation = valid["luck_flow"]
            facts, reading = explanation["facts"], explanation["reading"]
            restricted = estimated or "luck_cycles" in public.get("disabled_sections", [])
            if restricted:
                text = " ".join(facts) + " " + reading
                dated = re.findall(r"\b\d{4}(?:[-/년]|\s*~\s*\d{4})", text)
                attribution = ("출생시간 미상" in text if locale == "ko" else "unknown birth time" in text.lower()) if estimated else True
                unavailable = bool(re.search(r"비활성|미확인|disabled|unconfirmed|unavailable", " ".join(facts), re.IGNORECASE))
                withheld = bool(re.search(r"읽지 않았|보류|제외|withheld|excluded|not (?:read|calculated|used)", reading, re.IGNORECASE))
                regressions = unavailable_luck_assertions({"luck_flow": {"body": text}}, restricted=True)
                self.verify(fixture + ".basis_luck_unknown_limit", attribution and unavailable and withheld and not dated and not regressions,
                            {"facts": facts, "reading": reading, "dated_window_claims": dated,
                             "states_birth_time_limit": attribution, "timing_withheld": withheld,
                             "confirmed_regression_claims": regressions}, "content")
            elif cards.get("luck_flow", {}).get("reading_structure") is None:
                # Legacy notes compare current/next cycles. Structured notes use
                # only the selected current cycle and current stem ten-god;
                # check_reading_contract compares that narrower source directly.
                cycles = manse.get("luck_cycles", [])
                try:
                    year = datetime.fromisoformat(flows["as_of"]).year
                except (KeyError, ValueError, TypeError):
                    year = 0
                active_index = next((index for index, cycle in enumerate(cycles)
                                     if cycle.get("start_year", 1) <= year <= cycle.get("end_year", 0)), None)
                if active_index is not None:
                    expected_cycles = cycles[active_index:active_index + 2]
                    periods = [compact_cycle_period(cycle, locale) for cycle in expected_cycles]
                    correct = all(index < len(facts) and period in facts[index] for index, period in enumerate(periods))
                    self.verify(fixture + ".basis_luck_period_values", correct,
                                {"source": "visible manse luck-cycle year windows", "expected_periods": periods,
                                 "facts": facts, "scope": "Compares supplied year-selected windows, not all timing semantics."}, "content")
        for kind in ("today", "month"):
            if kind not in valid:
                continue
            flow, explanation = flows.get(kind, {}), valid[kind]
            facts = explanation["facts"]
            items = flow.get("evidence", [])
            target_source = next((item for item in items if item.get("label") in
                                  ({"일진", "Day pillar"} if kind == "today" else {"이번 달 월주", "Month pillar"})), {})
            first = facts[0]
            target = first.split(":", 1)[1].strip() if ":" in first else None
            second = facts[1] if len(facts) > 1 else ""
            signal = second.split(":", 1)[1].strip() if ":" in second else None
            stem_map = STEM_KO if locale == "ko" else STEM_EN
            expected_stem = stem_map.get(pillars.get("day", {}).get("stem"))
            correct = (bool(target_source.get("value")) and target == target_source.get("value")
                       and bool(flow.get("period_label")) and flow["period_label"] in first
                       and signal == flow.get("primary_signal") and bool(expected_stem) and expected_stem in second)
            self.verify(fixture + ".basis_" + kind + "_fact_values", correct,
                        {"expected_target": target_source.get("value"), "stated_target": target,
                         "period_label": flow.get("period_label"), "expected_signal": flow.get("primary_signal"),
                         "stated_signal": signal, "expected_natal_stem": expected_stem, "facts": facts}, "content")
            if estimated:
                reading = explanation["reading"]
                correct_limit = (bool(re.search(r"미상|unknown birth time", reading, re.IGNORECASE))
                                 and bool(re.search(r"제외|비활성|exclud|disabled|withheld", reading, re.IGNORECASE)))
                self.verify(fixture + ".basis_" + kind + "_unknown_limit", correct_limit,
                            {"reading": reading, "states_exclusion": correct_limit}, "content")

    def check_reading_contract(self, fixture: str, payload: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Audit provenance, public fact values and rendered role text separately.

        No Ten-God/cycle/fortune value is recalculated. The derived active-cycle
        Ten-God field is not public, so source-path/rule consistency is checked
        without counting that field as an independently verified value.
        """
        report = response.get("result", {}).get("free_preview") or {}
        cards = card_map(response)
        public, manse = response.get("result", {}), response.get("manse", {})
        locale = payload.get("locale", "ko")
        estimated = payload.get("is_birth_time_estimated") is True
        restricted = (estimated
                      or bool({"luck_cycles", "luck_flow"}.intersection(public.get("disabled_sections", [])))
                      or public.get("evidence_sections", {}).get("luck_cycles", {}).get("status") == "disabled")
        if restricted:
            self.verify(fixture + ".knowledge_luck_exclusion", cards.get("luck_flow", {}).get("reading_structure") is None,
                        {"luck_cycle_availability": "unavailable", "marker_present": cards.get("luck_flow", {}).get("reading_structure") is not None})
        # Older unmarked replies remain valid: only the new declared contract
        # and present structures are audited here.
        marked = {key: card for key, card in cards.items() if card.get("reading_structure") is not None}
        critical = any(flag.get("severity") == "critical" for flag in public.get("uncertainty_summary", []) if isinstance(flag, dict))
        if critical:
            self.verify(fixture + ".knowledge_critical_exclusion", not marked,
                        {"critical_calculation_uncertainty": True, "marked_topics": sorted(marked),
                         "scope": "All policy markers must be withheld for critical calculation uncertainty."})
        if not marked and "question_capabilities" not in report:
            return
        catalog = knowledge_catalog()
        sources = {item["id"]: item for item in catalog.get("sources", [])}
        rules = {item["id"]: item for item in catalog.get("rules", [])}
        policies = {item["id"]: item for item in catalog.get("questions", [])}
        capabilities = report.get("question_capabilities")
        capability_list = isinstance(capabilities, list) and all(isinstance(item, dict) for item in capabilities)
        capability_ids = [item.get("question_id") for item in capabilities] if capability_list else []
        self.verify(fixture + ".knowledge_question_capabilities", capability_list and len(capability_ids) == 5
                    and set(capability_ids) == set(UNSUPPORTED_QUESTIONS) and len(set(capability_ids)) == len(capability_ids),
                    {"question_ids": capability_ids, "expected_unsupported_count": 5})
        for item in capabilities if capability_list else []:
            identifier = item.get("question_id")
            policy = policies.get(identifier, {})
            boundary = UNSUPPORTED_QUESTIONS.get(identifier)
            expected_status, expected_scope = boundary if boundary else (None, None)
            protected = (boundary is not None and item.get("status") == expected_status and item.get("supported_scope") == expected_scope
                         and item.get("question") == policy.get("question", {}).get(locale)
                         and bool(item.get("missing_requirements")) and item.get("missing_requirements") == policy.get("required_data")
                         and isinstance(item.get("forbidden_claims"), list)
                         and FORBIDDEN_QUESTION_CLAIMS.issubset(item.get("forbidden_claims", []))
                         and item.get("forbidden_claims") == policy.get("forbidden_claims"))
            self.verify(fixture + ".knowledge_unsupported_" + str(identifier), protected,
                        {"question_id": identifier, "status": item.get("status"), "supported_scope": item.get("supported_scope"),
                         "missing_requirements": item.get("missing_requirements"), "forbidden_claims": item.get("forbidden_claims"),
                         "scope": "Capability metadata must not authorize probabilities, event dates, or population ranks."}, "content")
        pillars, counts = manse.get("pillars", {}), manse.get("elements", {})
        dominant = public.get("signals", {}).get("dominant_elements", [])
        try:
            year = datetime.fromisoformat(response["period_flows"]["as_of"]).year
        except (KeyError, ValueError, TypeError):
            year = 0
        cycles = manse.get("luck_cycles", [])
        active_index = next((index for index, cycle in enumerate(cycles)
                             if cycle.get("start_year", 1) <= year <= cycle.get("end_year", 0)), None)
        cycle = cycles[active_index] if active_index is not None else {}
        for key, card in marked.items():
            structure = card.get("reading_structure")
            if not isinstance(structure, dict):
                self.verify(fixture + ".knowledge_" + key + "_format", False, {"structure_is_object": False})
                continue
            rule = rules.get(structure.get("rule_id"), {})
            source = sources.get(structure.get("source_id"), {})
            metadata_ok = (structure.get("format_version") == catalog.get("format_version") == "question-reading-v1"
                           and structure.get("knowledge_version") == catalog.get("knowledge_version")
                           and structure.get("copy_version") == catalog.get("copy_version")
                           and structure.get("provenance") == "server_project_policy" and structure.get("expert_review") == "not_completed"
                           and source.get("kind") == "project_policy" and source.get("expert_review") == "not_completed"
                           and bool(source.get("reference")) and rule.get("source_id") == structure.get("source_id")
                           and rule.get("topic") == key and rule.get("status") == "active_project_policy"
                           and rule.get("claim_scope") == "interpretation_only" and type(structure.get("rule_version")) is int
                           and structure.get("rule_version") == rule.get("version"))
            self.verify(fixture + ".knowledge_" + key + "_format", metadata_ok,
                        {"format_version": structure.get("format_version"), "knowledge_version": structure.get("knowledge_version"),
                         "source_id": structure.get("source_id"), "rule_id": structure.get("rule_id"), "rule_version": structure.get("rule_version"),
                         "provenance": structure.get("provenance"), "expert_review": structure.get("expert_review")})
            facts = structure.get("facts")
            facts_ok = isinstance(facts, list) and bool(facts) and all(isinstance(fact, dict) for fact in facts)
            by_id = {fact.get("id"): fact for fact in facts} if facts_ok else {}
            expected = {}
            feature_value = None
            unobservable = []
            if key in {"love", "work_money"}:
                love = key == "love"
                identifier = "love.spouse_house_ten_god" if love else "career.month_stem_ten_god"
                raw = pillars.get("day" if love else "month", {}).get("branch_ten_god" if love else "stem_ten_god")
                expected[identifier] = ("love_facts.spouse_house_ten_god" if love else "career_facts.month_stem_ten_god", localized_ten_god(raw, locale))
                feature_value = canonical_ten_god(raw)
            elif key == "core":
                expected = {"core.dominant_elements": ("signals.dominant_elements", ", ".join(dominant)),
                            "core.element_counts": ("element_counts", json.dumps(counts, sort_keys=True))}
                highest = max(counts.values(), default=0)
                dominant_matches_counts = (set(counts) == set(ELEMENTS) and highest > 0 and len(dominant) == len(set(dominant))
                                          and set(dominant) == {element for element, count in counts.items() if count == highest})
                self.verify(fixture + ".knowledge_core_dominant_counts", dominant_matches_counts,
                            {"supplied_dominant": dominant, "actual_highest_count_elements": [element for element, count in counts.items() if count == highest]}, "content")
                feature_value = dominant[0] if len(dominant) == 1 else "mixed"
            elif key == "luck_flow":
                expected = {"luck.current_gan_zhi": ("current_flow.active_luck_cycle.display_gan_zhi", display_cycle_gan_zhi(cycle, locale)),
                            "luck.current_period": (f"luck_cycle_analysis[{active_index}].period", knowledge_cycle_period(cycle, locale) if cycle else None),
                            "luck.current_stem_ten_god": (f"luck_cycle_analysis[{active_index}].stem_ten_god", None)}
                unobservable = ["luck.current_stem_ten_god"]
                feature_value = canonical_ten_god(by_id.get("luck.current_stem_ten_god", {}).get("value"))
                if not self.unobservable_luck_fact_recorded:
                    self.add("quality.unobservable_luck_ten_god", "WARN", "human_review",
                             {"fact_id": "luck.current_stem_ten_god", "reason": "luck_cycle_analysis is not exposed in the preview response.",
                              "value_independently_verified": False, "scope": "Only source-path/rule consistency is checked for this derived value; no recalculation was performed."})
                    self.unobservable_luck_fact_recorded = True
            paths_ok = (facts_ok and len(by_id) == len(facts) and set(by_id) == set(expected)
                        and all(isinstance(fact.get("id"), str) and isinstance(fact.get("value"), str) and bool(fact.get("value"))
                                and fact.get("source_path") == expected[identifier][0] for identifier, fact in by_id.items()))
            self.verify(fixture + ".knowledge_" + key + "_fact_paths", paths_ok,
                        {"source_paths": {identifier: fact.get("source_path") for identifier, fact in by_id.items()},
                         "expected_source_paths": {identifier: values[0] for identifier, values in expected.items()}})
            observed_ids = [identifier for identifier in expected if identifier not in unobservable]
            comparisons = [{"fact_id": identifier, "stated_value": by_id.get(identifier, {}).get("value"), "expected_value": expected[identifier][1]}
                           for identifier in observed_ids]
            values_ok = bool(observed_ids) and all(item["expected_value"] is not None and item["stated_value"] == item["expected_value"] for item in comparisons)
            self.verify(fixture + ".knowledge_" + key + "_public_fact_values", values_ok,
                        {"comparisons": comparisons, "checked_fact_ids": observed_ids, "unverified_fact_ids": unobservable}, "content")
            selected = bool(rule) and feature_value in rule.get("any_of", [])
            self.verify(fixture + ".knowledge_" + key + "_rule_selection", selected,
                        {"rule_id": structure.get("rule_id"), "supplied_feature": feature_value, "allowed_rule_features": rule.get("any_of", []),
                         "scope": "Input-to-policy match; this does not independently validate an unexposed derived fact."})
            blocks = structure.get("blocks")
            block_list = isinstance(blocks, list) and all(isinstance(block, dict) for block in blocks)
            blocks = blocks if block_list else []
            blocks_ok = (len(blocks) == 4 and [block.get("role") for block in blocks] == list(READING_ROLES)
                         and [block.get("kind") for block in blocks] == list(READING_KINDS)
                         and all(isinstance(block.get("text"), str) and 8 <= len(block["text"]) <= 300 for block in blocks)
                         and all(block.get("rule_id") == structure.get("rule_id") and isinstance(block.get("fact_ids"), list)
                                 and bool(block["fact_ids"]) and all(identifier in by_id for identifier in block["fact_ids"])
                                 and len(block["fact_ids"]) == len(set(block["fact_ids"])) for block in blocks))
            self.verify(fixture + ".knowledge_" + key + "_roles_and_links", blocks_ok,
                        {"roles": [block.get("role") for block in blocks], "kinds": [block.get("kind") for block in blocks],
                         "fact_ids": [block.get("fact_ids") for block in blocks]})
            wording = rule.get("wording", {}).get(locale, {})
            substitutions = {"period": by_id.get("luck.current_period", {}).get("value", "")}
            try:
                policy_text = [wording[role].format(**substitutions) for role in READING_ROLES]
            except (KeyError, ValueError):
                policy_text = []
            text_match = (blocks_ok and [block["text"] for block in blocks] == policy_text
                          and structure.get("question") == wording.get("question") == card.get("title") == card.get("subtitle")
                          and card.get("user_takeaway") == blocks[0].get("text")
                          and card.get("preview_paragraphs") == [block.get("text") for block in blocks[1:]]
                          and len(card.get("preview_paragraphs", [])) == 3 and card.get("next_question") == wording.get("next_question"))
            self.verify(fixture + ".knowledge_" + key + "_rendered_text", text_match,
                        {"takeaway_matches_answer": bool(blocks) and card.get("user_takeaway") == blocks[0].get("text"),
                         "paragraph_count": len(card.get("preview_paragraphs", [])), "policy_text_matches": [block.get("text") for block in blocks] == policy_text}, "content")
            note = structure.get("analysis_note")
            note_shape, note_evidence = basis_structure(note)
            # Strict server note contract: extra fields cannot silently acquire
            # new meaning outside the published facts/reading slots.
            note_shape = note_shape and set(note) == {"facts", "reading"}
            self.verify(fixture + ".knowledge_" + key + "_analysis_note_structure", note_shape, note_evidence)
            basis_match = note_shape and card.get("basis_explanation") == note
            line_match = note_shape and card.get("basis_line") == " · ".join(note["facts"])
            self.verify(fixture + ".knowledge_" + key + "_analysis_note_card_match", basis_match and line_match,
                        {"basis_explanation_matches": basis_match, "basis_line_matches": line_match}, "content")
            ko = locale == "ko"
            note_facts, note_substitutions = [], {}
            if key == "core":
                labels = ELEMENT_KO if ko else {element: element.title() for element in ELEMENTS}
                if all(element in counts for element in ELEMENTS) and all(element in labels for element in dominant):
                    dominant_label = ", ".join(labels[element] for element in dominant)
                    distribution = " · ".join((f"{labels[element]} {counts[element]}개" if ko else
                                               f"{element} {counts[element]}") for element in ELEMENTS)
                    note_facts = [("보이는 오행 분포: " if ko else "Visible element counts: ") + distribution,
                                  ("최다 오행: " if ko else "Most frequent visible elements: ") + dominant_label]
                    note_substitutions = {"dominant_label": dominant_label}
                    if estimated:
                        note_facts.append("출생시간 미상: 시주 제외" if ko else "Unknown birth time: hour pillar excluded")
            elif key in {"love", "work_money"}:
                identifier = "love.spouse_house_ten_god" if key == "love" else "career.month_stem_ten_god"
                label = expected.get(identifier, (None, None))[1]
                if label:
                    prefix = ("배우자궁 십성: " if ko else "Spouse-house ten-god: ") if key == "love" else (
                        "월간 십성: " if ko else "Month-stem ten-god: ")
                    note_facts = [prefix + label]
                    note_substitutions = {"feature_label": label}
            elif key == "luck_flow":
                cycle_label = expected.get("luck.current_gan_zhi", (None, None))[1]
                period = expected.get("luck.current_period", (None, None))[1]
                # This supplied derived label is not independently observable.
                # Its public-value limitation is already reported once above.
                label = by_id.get("luck.current_stem_ten_god", {}).get("value")
                if cycle_label and period and label:
                    note_facts = [(f"현재 대운: {cycle_label} · {period}" if ko else f"Current cycle: {cycle_label} · {period}"),
                                  (f"현재 대운 천간 십성: {label}" if ko else f"Current cycle stem ten-god: {label}")]
                    note_substitutions = {"period": period, "feature_label": label}
            try:
                note_reading = wording["analysis_note"].format(**note_substitutions)
            except (KeyError, ValueError, AttributeError):
                note_reading = None
            note_policy_match = (note_shape and bool(note_facts) and bool(note_reading)
                                 and note["facts"] == note_facts and note["reading"] == note_reading)
            self.verify(fixture + ".knowledge_" + key + "_analysis_note_policy", note_policy_match,
                        {"stated_facts": note.get("facts") if isinstance(note, dict) else None,
                         "expected_facts": note_facts, "policy_reading_matches": note_shape and note["reading"] == note_reading,
                         "checked_public_fact_ids": observed_ids, "unverified_fact_ids": unobservable,
                         "scope": "Public fact linkage and catalog wording; any unexposed derived label remains unverified."}, "content")

    def preview(self, fixture: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.provider_preflight()
        started = datetime.now(timezone.utc)
        result = self.client.request(self.api_base, "/saju/preview", payload)
        finished = datetime.now(timezone.utc)
        self.verify(fixture + ".preview_http", result.status == 200, {"http_status": result.status})
        if result.status != 200 or not isinstance(result.data, dict):
            return None
        response = result.data
        report = response.get("result", {}).get("free_preview") or {}
        diagnostics = report.get("diagnostics") or {}
        safe_provider = (report.get("provider") == "fallback"
                         and diagnostics.get("configured_provider") == "fallback"
                         and diagnostics.get("final_provider") == "fallback"
                         and not diagnostics.get("attempts"))
        self.verify(fixture + ".provider", safe_provider,
                    {"provider": report.get("provider"), "configured_provider": diagnostics.get("configured_provider"),
                     "external_attempt_count": len(diagnostics.get("attempts") or [])})
        if not safe_provider:
            raise VerificationBlocked("Preview provider diagnostics are not tokenless fallback; further requests stopped.")
        self.verify(fixture + ".calculation_pipeline", all(response.get("pipeline_status", {}).get(key) == "passed"
                    for key in ("input_validation", "region_resolution", "time_correction", "calendar_normalization",
                                "regional_solar_correction", "saju_calculation", "analysis_engine")),
                    {"stages": {key: value for key, value in response.get("pipeline_status", {}).items()
                                if key not in {"llm_formatting", "free_preview_formatting"}}})
        cards = card_map(response)
        self.verify(fixture + ".four_preview_topics", set(cards) == TOPIC_KEYS
                    and len(report.get("cards", [])) == 4, {"keys": sorted(cards)})
        text_ok = bool(report.get("headline", "").strip()) and bool(report.get("hero_overview"))
        for card in cards.values():
            text_ok = text_ok and bool(card.get("title", "").strip()) and bool(card.get("user_takeaway", "").strip())
            paragraphs = card.get("preview_paragraphs", [])
            text_ok = text_ok and len(paragraphs) >= 3 and all(isinstance(p, str) and p.strip() for p in paragraphs)
            text_ok = text_ok and bool(card.get("basis_line", "").strip())
        self.verify(fixture + ".nonempty_reading", text_ok,
                    {"headline": report.get("headline"), "paragraph_counts": {key: len(card.get("preview_paragraphs", []))
                                                                               for key, card in cards.items()}})
        periods_ok, evidence = check_periods(response, started, finished)
        self.verify(fixture + ".today_and_month_periods", periods_ok, evidence)
        for kind in ("today", "month"):
            flow = response.get("period_flows", {}).get(kind, {})
            items = flow.get("evidence", [])
            self.verify(fixture + "." + kind + "_evidence", bool(items) and bool(flow.get("actions"))
                        and all(all(item.get(field) for field in ("label", "value", "detail", "source")) for item in items),
                        {"source_ids": [item.get("source") for item in items], "primary_signal": flow.get("primary_signal")},
                        "content")
        estimated = payload.get("is_birth_time_estimated", False)
        manse, public = response.get("manse", {}), response.get("result", {})
        enabled = public.get("hour_pillar_enabled") is True
        keys = public.get("signals", {}).get("visible_pillar_keys", [])
        hour = manse.get("pillars", {}).get("time", {})
        if estimated:
            policy_ok = (not enabled and "time" not in keys and hour.get("enabled") is False
                         and not manse.get("luck_cycles") and not response.get("period_flows", {}).get("month", {}).get("current_luck_cycle")
                         and {"time_pillar", "luck_cycles", "hour_based_interpretation"}.issubset(public.get("disabled_sections", []))
                         and public.get("evidence_sections", {}).get("luck_cycles", {}).get("status") == "disabled"
                         and bool(public.get("limitations")) and response.get("time_correction", {}).get("is_placeholder_time") is True)
        else:
            policy_ok = enabled and keys == ["year", "month", "day", "time"] and hour.get("enabled") is True
        self.verify(fixture + ".birth_time_policy", policy_ok,
                    {"estimated": estimated, "visible_pillars": keys, "hour_enabled": enabled,
                     "disabled_sections": public.get("disabled_sections", [])})
        if estimated or "luck_cycles" in public.get("disabled_sections", []):
            claims = unavailable_luck_assertions(report, restricted=True)
            self.verify(fixture + ".preview_unavailable_luck_assertions", not claims,
                        {"locale": payload.get("locale", "ko"), "luck_cycle_availability": "unavailable",
                         "confirmed_regression_claims": claims,
                         "scope": "Narrow known KO/EN fallback phrases; full semantic accuracy needs human review."}, "content")
        counts = manse.get("elements", {})
        expected_total = 6 if estimated else 8
        self.verify(fixture + ".visible_element_total", sum(counts.get(key, 0) for key in ELEMENTS) == expected_total,
                    {"counts": counts, "expected_total": expected_total})
        self.verify(fixture + ".no_public_scores", all(public.get("signals", {}).get(key) is None
                    for key in ("internal_grade", "balance_score", "charm_score", "wealth_score", "career_score", "leadership_score")),
                    {"raw_scores_exposed": any(public.get("signals", {}).get(key) is not None
                                               for key in ("internal_grade", "balance_score", "charm_score", "wealth_score", "career_score", "leadership_score"))}, "content")
        text = " ".join([report.get("headline", ""), *report.get("hero_overview", []),
                         *[p for card in cards.values() for p in card.get("preview_paragraphs", [])]])
        guarantees = re.findall(r"(?:반드시|무조건).{0,20}(?:결혼|성공|대박|당첨|부자)|(?:정확도|적중률)\s*\d", text)
        self.verify(fixture + ".no_unsupported_guarantees", not guarantees, {"matched_claims": guarantees}, "content")
        self.check_basis(fixture, payload, response)
        self.check_reading_contract(fixture, payload, response)
        self.responses[fixture] = response
        self.cases.append({"fixture": fixture, "estimated_time": estimated, "calendar": payload.get("calendar_type", "solar"),
                           "locale": payload.get("locale", "ko"),
                           "chart_signature": digest(natal_facts(response)),
                           "pillars": public.get("signals", {}).get("visible_pillar_values", []),
                           "headline": report.get("headline"), "topic_keys": sorted(cards)})
        return response

    def detail(self, fixture: str, payload: Dict[str, Any], preview: Dict[str, Any]) -> None:
        self.provider_preflight()
        result = self.client.request(self.api_base, "/saju/free-detail", payload)
        self.verify(fixture + ".detail_http", result.status == 200, {"http_status": result.status})
        if result.status != 200 or not isinstance(result.data, dict):
            return
        report = result.data.get("interpretation") or {}
        diagnostics = report.get("diagnostics") or {}
        tokenless = (report.get("provider") == "fallback" and diagnostics.get("configured_provider") == "fallback"
                     and diagnostics.get("final_provider") == "fallback" and not diagnostics.get("attempts"))
        self.verify(fixture + ".detail_provider", tokenless, {"provider": report.get("provider"),
                    "configured_provider": diagnostics.get("configured_provider"), "external_attempt_count": len(diagnostics.get("attempts") or [])})
        if not tokenless:
            raise VerificationBlocked("Detail provider diagnostics are not tokenless fallback; further requests stopped.")
        sections = preview.get("result", {}).get("evidence_sections", {})
        restricted = (payload.get("is_birth_time_estimated") is True
                      or "luck_cycles" in preview.get("result", {}).get("disabled_sections", [])
                      or sections.get("luck_cycles", {}).get("status") == "disabled")
        if restricted:
            claims = unavailable_luck_assertions(report, restricted=True)
            self.verify(fixture + ".detail_unavailable_luck_assertions", not claims,
                        {"luck_cycle_availability": "unavailable", "confirmed_regression_claims": claims,
                         "scope": "Narrow known fallback phrases; this does not establish full semantic accuracy."}, "content")
        valid_ids = set(sections) | {"star:" + star["key"] for star in preview.get("manse", {}).get("special_stars", [])}
        for key in SECTION_KEYS:
            block = report.get(key, {})
            ids = block.get("evidence_ids", [])
            self.verify(fixture + ".detail_" + key, bool(block.get("title")) and bool(block.get("body", "").strip())
                        and bool(ids) and all(item in valid_ids for item in ids),
                        {"title": block.get("title"), "body_chars": len(block.get("body", "")),
                         "evidence_ids": ids, "unresolved_ids": [item for item in ids if item not in valid_ids]}, "content")
            disabled = [item for item in ids if sections.get(item, {}).get("status") == "disabled"]
            if disabled:
                self.add(fixture + ".detail_" + key + "_disabled_evidence", "WARN", "content",
                         {"disabled_evidence_ids": disabled, "review": "Check that text describes the limitation rather than asserting unavailable timing."})

    def compare_personalization(self) -> None:
        known = [(name, response) for name, response in self.responses.items()
                 if name in {"known_seoul", "known_busan", "late_zi", "lunar_known"}]
        distinct = len({digest(natal_facts(response)) for _, response in known})
        self.verify("quality.distinct_fixture_charts", distinct >= 3, {"distinct_chart_count": distinct})
        for topic in ("love", "work_money"):
            paragraphs = {name: card_map(response).get(topic, {}).get("preview_paragraphs", []) for name, response in known}
            fingerprints = {name: digest(items) for name, items in paragraphs.items()}
            all_identical = len(set(fingerprints.values())) <= 1
            self.verify("quality." + topic + "_personalized_body", not all_identical,
                        {"distinct_chart_count": distinct, "body_fingerprints": fingerprints,
                         "same_complete_body_for_all_charts": all_identical,
                         "first_paragraph_excerpt": {name: (items[0][:180] if items else "") for name, items in paragraphs.items()}}, "content")
            takeaways = {name: card_map(response).get(topic, {}).get("user_takeaway", "") for name, response in known}
            same = len(set(takeaways.values())) <= 1
            self.add("quality." + topic + "_takeaway_variation", "WARN" if same else "PASS", "content",
                     {"all_identical": same, "takeaways": takeaways})
        self.add("quality.real_user_interest", "WARN", "human_review",
                 {"review_required": "Agent review and observable content checks cannot establish real users' enjoyment. Validate topic curiosity, reading value, and sharing intent with people; no conversion or accuracy percentage is inferred."})
        self.add("quality.live_llm_semantic_accuracy", "WARN", "human_review",
                 {"provider_tested": "fallback", "live_llm_executed": False,
                  "review_required": "These checks cover response contracts and narrow confirmed fallback regressions. They do not establish that a live LLM's wording faithfully follows every supplied fact or limitation. Review real-provider output against chart evidence separately when that execution is explicitly authorized."})

    def check_lunar_day30(self, baseline: Dict[str, Any]) -> None:
        """Keep the confirmed valid lunar-day-30 contract defect observable.

        This synthetic lunar date is valid in the calendar engine but not as a
        Gregorian date. A Gregorian request-schema rejection is a product bug,
        not an expected-invalid-input success. Changing that input contract is
        a separate decision; this check does not modify the running service.
        """
        self.provider_preflight()
        result = self.client.request(self.api_base, "/saju/preview",
                                     {**baseline, "calendar_type": "lunar", "birth_date": "1990-02-30"})
        response = result.data if isinstance(result.data, dict) else {}
        normalized = response.get("calendar_normalization", {})
        passed = (result.status == 200 and normalized.get("calendar_type") == "lunar"
                  and bool(normalized.get("normalized_solar_datetime"))
                  and response.get("pipeline_status", {}).get("saju_calculation") == "passed")
        self.verify("known_issue.valid_lunar_day30", passed,
                    {"fixture": "valid_lunar_day30", "expected_http_status": 200, "http_status": result.status,
                     "error_code": response.get("error_code"), "stage": response.get("stage"),
                     "known_issue": not passed,
                     "issue": "A valid lunar day 30 must reach lunar normalization; Gregorian date schema validation must not reject it.",
                     "decision": "Input-contract correction is pending review; keep this functional failure visible until resolved." if not passed else "Resolved."})
        if result.status == 200:
            report = response.get("result", {}).get("free_preview") or {}
            diagnostics = report.get("diagnostics") or {}
            if (report.get("provider") != "fallback" or diagnostics.get("configured_provider") != "fallback"
                    or diagnostics.get("final_provider") != "fallback" or diagnostics.get("attempts")):
                raise VerificationBlocked("Lunar-day-30 provider diagnostics are not tokenless fallback; further requests stopped.")

    def run(self) -> None:
        health = self.client.request(self.api_base, "/health")
        self.verify("runtime.api_health", health.status == 200 and isinstance(health.data, dict)
                    and health.data.get("status") == "ok", {"http_status": health.status})
        # Vite deliberately skips its HTML fallback for application/json.
        # Request a document like a browser instead of treating it as API JSON.
        web = self.client.request(self.web_base, accept="text/html")
        self.verify("runtime.web_document", web.status == 200 and "html" in web.content_type
                    and isinstance(web.data, str) and bool(re.search(r'<div\s+id=["\']root["\']', web.data)),
                    {"http_status": web.status, "root_present": isinstance(web.data, str) and "root" in web.data})
        self.provider_preflight()
        regions = {}
        for query in ("서울", "부산", "대전"):
            result = self.client.request(self.api_base, "/regions/search?" + urlencode({"q": query, "limit": 5}))
            items = result.data.get("items", []) if isinstance(result.data, dict) else []
            matching = [item for item in items if query in item.get("display_name", "") and item.get("id") and item.get("tzid") == "Asia/Seoul"]
            self.verify("region.search_" + query, result.status == 200 and bool(matching),
                        {"http_status": result.status, "matching_ids": [item["id"] for item in matching]})
            if not matching:
                raise VerificationBlocked("Synthetic birth region could not be resolved.")
            regions[query] = matching[0]["id"]
        baseline = {"birth_date": "1997-09-18", "birth_time": "14:30", "gender": "female",
                    "region_id": regions["서울"], "locale": "ko", "calendar_type": "solar", "is_birth_time_estimated": False}
        fixtures = [
            ("known_seoul", baseline),
            ("known_busan", {**baseline, "birth_date": "1990-01-01", "birth_time": "10:30", "gender": "male", "region_id": regions["부산"]}),
            ("late_zi", {**baseline, "birth_date": "1988-11-20", "birth_time": "23:30", "gender": "male"}),
            ("lunar_known", {**baseline, "birth_date": "1992-12-10", "birth_time": "08:15", "calendar_type": "lunar", "region_id": regions["대전"]}),
            ("unknown_time", {**baseline, "is_birth_time_estimated": True}),
            ("unknown_time_en", {**baseline, "is_birth_time_estimated": True, "locale": "en"}),
        ]
        for name, payload in fixtures:
            self.preview(name, payload)
        first = self.responses.get("known_seoul")
        if first:
            repeated = self.preview("known_seoul_repeat", baseline)
            explicit = self.preview("known_seoul_explicit_legacy", {**baseline, "accuracy_mode": "legacy"})
            self.verify("calculation.repeat_deterministic", repeated is not None and natal_facts(first) == natal_facts(repeated),
                        {"baseline_signature": digest(natal_facts(first)), "repeat_signature": digest(natal_facts(repeated)) if repeated else None})
            self.verify("calculation.default_legacy_unchanged", explicit is not None and natal_facts(first) == natal_facts(explicit)
                        and first.get("result", {}).get("calculation_basis", {}).get("accuracy_mode") == "legacy",
                        {"default_mode": first.get("result", {}).get("calculation_basis", {}).get("accuracy_mode"),
                         "explicit_matches": explicit is not None and natal_facts(first) == natal_facts(explicit)})
            self.detail("known_seoul", baseline, first)
        fixture_payloads = dict(fixtures)
        for fixture in ("unknown_time", "unknown_time_en"):
            unknown = self.responses.get(fixture)
            if unknown:
                self.detail(fixture, fixture_payloads[fixture], unknown)
        missing = dict(baseline)
        missing.pop("region_id")
        rejected = [("region_missing", missing), ("region_invalid", {**baseline, "region_id": "not-a-catalog-region"}),
                    ("date_invalid", {**baseline, "birth_date": "2024-02-30"}),
                    ("time_invalid", {**baseline, "birth_time": "25:61"})]
        for name, payload in rejected:
            self.provider_preflight()
            result = self.client.request(self.api_base, "/saju/preview", payload)
            error = result.data if isinstance(result.data, dict) else {}
            self.verify("validation." + name, result.status in {400, 422} and bool(error.get("error_code")),
                        {"http_status": result.status, "error_code": error.get("error_code"), "stage": error.get("stage")})
        self.check_lunar_day30(baseline)
        self.compare_personalization()

    def report(self, blocked: Optional[str] = None) -> Dict[str, Any]:
        counts = {status: sum(item["status"] == status for item in self.checks) for status in ("PASS", "WARN", "FAIL")}
        return {"schema_version": "user-story-verification-v1", "verified_at": datetime.now(timezone.utc).isoformat(),
                "scope": "Local HTTP contracts and synthetic content comparisons; browser UX and human interest require separate review.",
                "provider_policy": "fallback only; preflight + request guard + response diagnostics; no external generation authorized",
                "overall_status": "BLOCKED" if blocked else ("FAIL" if counts["FAIL"] else "WARN" if counts["WARN"] else "PASS"),
                "blocked_reason": blocked, "summary": counts,
                "functional_failures": sum(item["status"] == "FAIL" and item["category"] == "functional" for item in self.checks),
                "content_failures": sum(item["status"] == "FAIL" and item["category"] == "content" for item in self.checks),
                "synthetic_cases": self.cases, "checks": self.checks}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument("--web-base", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=float, default=15, help="Per-request timeout in seconds.")
    parser.add_argument("--total-timeout", type=float, default=180, help="Overall HTTP deadline in seconds.")
    args = parser.parse_args(argv)
    if args.timeout <= 0 or args.total_timeout <= 0:
        parser.error("Timeouts must be positive.")
    # Do not create an output directory or workspace implicitly.
    if not args.output.parent.is_dir():
        parser.error("Output parent directory must already exist.")
    try:
        verifier = UserStoryVerifier(LocalHttp(args.timeout, args.total_timeout), args.api_base, args.web_base)
    except ValueError as exc:
        parser.error(str(exc))
    blocked = None
    try:
        verifier.run()
    except VerificationBlocked as exc:
        blocked = str(exc)
    except (KeyError, TypeError, ValueError) as exc:
        blocked = "Unexpected response contract (%s); verification stopped." % type(exc).__name__
    report = verifier.report(blocked)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("User story verification: {overall_status}; PASS={PASS} WARN={WARN} FAIL={FAIL}".format(**report, **report["summary"]))
    print("Report: " + str(args.output.resolve()))
    for item in report["checks"]:
        if item["status"] in {"WARN", "FAIL"}:
            print("{status} [{category}] {id}".format(**item))
    if blocked:
        print("BLOCKED: " + blocked)
    return 2 if blocked else (1 if report["summary"]["FAIL"] else 0)


if __name__ == "__main__":
    sys.exit(main())
