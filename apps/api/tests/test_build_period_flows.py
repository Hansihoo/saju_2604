import unittest
from datetime import datetime

from app.domain.saju.localization import TEN_GOD_ENGLISH, contains_hangul, contains_hanja, localize_ten_god
from app.domain.saju.pydantic_compat import model_to_dict, model_validate_compat
from app.domain.saju.schemas import PeriodFlows, SajuPreviewRequest
from app.domain.saju.services.build_period_flows import _period_basis_explanation, _rule, _ten_god_for, _ten_god_group, build_period_flows
from app.domain.saju.services.calculate_saju import calculate_saju
from app.domain.saju.services.region_catalog import find_region_by_id


class PeriodFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.region = find_region_by_id("kr-seoul")
        self.payload = SajuPreviewRequest(
            birth_date="1990-01-01",
            birth_time="10:30",
            gender="male",
            region_id="kr-seoul",
            debug=False,
        )
        self.calculation = calculate_saju(
            corrected_solar_datetime="1990-01-01 10:20:00",
            gender="male",
            tzid="Asia/Seoul",
        )

    def test_period_basis_links_actual_calendar_signal_and_existing_focus_in_both_locales(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                request = model_validate_compat(SajuPreviewRequest, {**model_to_dict(self.payload), "locale": locale})
                flows = build_period_flows(payload=request, region=self.region, saju_calculation=self.calculation,
                                           as_of=datetime(2026, 8, 25, 12, 0))
                for flow in (flows.today, flows.month):
                    basis = flow.basis_explanation
                    self.assertIsNotNone(basis)
                    self.assertIn(flow.period_label, basis.facts[0])
                    self.assertIn(flow.primary_signal, basis.facts[1])
                    self.assertIn(flow.primary_signal, basis.reading)
                    self.assertIn(flow.evidence[0 if flow.kind == "today" else 1].value, basis.facts[0])
                    for focus in flow.focus[:2]:
                        self.assertIn(focus.lower(), basis.reading.lower())
                    relation = next((item for item in flow.evidence if item.source == "period_rule_v1"), None)
                    if relation:
                        self.assertIn(relation.value, basis.facts[2])
                    text = " ".join([*basis.facts, basis.reading])
                    self.assertFalse(contains_hanja(text))
                    if locale == "en":
                        self.assertFalse(contains_hangul(text))
                    else:
                        self.assertIn("태어난 날의 기준(일간)", basis.facts[1])
                        self.assertNotIn("내 하루 기준", basis.facts[1])
                        self.assertIn("일간과 일진 천간" if flow.kind == "today" else "일간과 해당 절기 월주 천간", basis.reading)
                        self.assertIn("십성을 확인했습니다", basis.reading)
                        self.assertIn("관점에서 검토했습니다", basis.reading)
                restored = model_validate_compat(PeriodFlows, model_to_dict(flows, mode="json"))
                self.assertEqual(restored, flows)

    def test_unknown_time_period_basis_uses_no_hour_or_current_cycle_fact(self) -> None:
        for locale in ("ko", "en"):
            with self.subTest(locale=locale):
                request = model_validate_compat(SajuPreviewRequest, {
                    **model_to_dict(self.payload), "locale": locale,
                    "birth_time": "00:00", "is_birth_time_estimated": True,
                })
                flows = build_period_flows(payload=request, region=self.region, saju_calculation=self.calculation,
                                           as_of=datetime(2026, 8, 25, 12, 0))
                for flow in (flows.today, flows.month):
                    self.assertIsNone(flow.current_luck_cycle)
                    text = " ".join([*flow.basis_explanation.facts, flow.basis_explanation.reading])
                    self.assertNotIn("00:00", text)
                    facts = " ".join(flow.basis_explanation.facts)
                    for forbidden in ("시주", "대운", "Hour pillar", "Time pillar", "luck cycle"):
                        self.assertNotIn(forbidden, facts)
                    self.assertIn("시주와 대운 연결은 분석에서 제외했습니다" if locale == "ko" else "Hour-pillar and luck-cycle connections were excluded", text)

    def test_analysis_note_copy_fits_public_limit_across_period_rule_categories(self) -> None:
        for locale in ("ko", "en"):
            for kind in ("today", "month"):
                for label in TEN_GOD_ENGLISH:
                    for relation in (None, "same", "harmony", "clash"):
                        for estimated in (False, True):
                            with self.subTest(locale=locale, kind=kind, label=label, relation=relation, estimated=estimated):
                                basis = _period_basis_explanation(
                                    kind=kind, locale=locale, target_label="신해" if locale == "ko" else "Sin-Hae",
                                    natal_stem="계", ten_god=label,
                                    relation_match=(relation, "day", "해") if relation else None,
                                    estimated=estimated, period_label="2026년 10월 4일" if locale == "ko" else "Oct 4, 2026",
                                )
                                self.assertIsNotNone(basis)
                                self.assertLessEqual(len(basis.reading), 360)
                                self.assertNotIn("읽었어", basis.reading)
                                self.assertNotIn("살펴봤어", basis.reading)
                                self.assertNotIn(".Hour", basis.reading)
                                self.assertIn(label if locale == "ko" else TEN_GOD_ENGLISH[label], basis.reading)

    def test_unsupported_period_signal_has_no_invented_explanation(self) -> None:
        self.assertIsNone(_period_basis_explanation(
            kind="today", locale="ko", target_label="신해", natal_stem="병",
            ten_god="UNSUPPORTED", relation_match=None, estimated=False,
        ))
        with self.assertRaises(ValueError):
            _rule("UNSUPPORTED", "ko")
        with self.assertRaises(ValueError):
            _ten_god_for("INVALID", "甲")

    def test_library_stem_relations_and_seven_killings_alias_use_correct_rule_and_note(self) -> None:
        for natal in "甲乙丙丁戊己庚辛壬癸":
            for target in "甲乙丙丁戊己庚辛壬癸":
                raw = _ten_god_for(natal, target)
                self.assertIn(localize_ten_god(raw, "ko"), TEN_GOD_ENGLISH)
                self.assertIn(_ten_god_group(raw), {"peer", "output", "wealth", "officer", "resource"})
        for raw in ("七杀", "七殺", "偏官"):
            for locale in ("ko", "en"):
                with self.subTest(raw=raw, locale=locale):
                    self.assertEqual(_ten_god_group(raw), "officer")
                    note = _period_basis_explanation(kind="today", locale=locale, target_label="임자" if locale == "ko" else "Im-Ja",
                                                     natal_stem="병", ten_god=raw, relation_match=None, estimated=False)
                    self.assertIn("편관" if locale == "ko" else "Seven Killings", note.reading)
                    self.assertFalse(contains_hanja(note.reading))
                    self.assertEqual(_rule(raw, locale)["focus"], _rule("편관", locale)["focus"])

    def test_legacy_period_payload_without_explanation_remains_compatible(self) -> None:
        flows = build_period_flows(payload=self.payload, region=self.region, saju_calculation=self.calculation,
                                   as_of=datetime(2026, 8, 25, 12, 0))
        data = model_to_dict(flows, mode="json")
        for key in ("today", "month"):
            data[key].pop("basis_explanation")
        restored = model_validate_compat(PeriodFlows, data)
        self.assertIsNone(restored.today.basis_explanation)
        self.assertIsNone(restored.month.basis_explanation)

    def test_daily_and_monthly_flow_use_local_calendar_and_solar_term_facts(self) -> None:
        flows = build_period_flows(
            payload=self.payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 8, 25, 12, 0),
        )

        self.assertEqual(flows.timezone_id, "Asia/Seoul")
        self.assertEqual(flows.today.period_start, "2026-08-25")
        self.assertEqual(flows.today.target_gan_zhi, "辛未")
        self.assertEqual(flows.today.evidence[0].source, "kasi_lunar_reference")
        self.assertEqual(flows.month.period_label, "2026년 8월")
        self.assertEqual(flows.month.target_gan_zhi, "丙申")
        self.assertEqual(flows.month.evidence[0].value, "입추")
        self.assertNotIn("일진", flows.today.summary)
        self.assertNotIn("십성", flows.today.summary)
        self.assertNotIn("절기", flows.month.summary)
        self.assertNotIn("월주", flows.month.summary)
        self.assertTrue(flows.today.notes)
        self.assertTrue(all("점수" not in action for action in flows.today.actions))

    def test_month_flow_changes_at_exact_solar_term_boundary(self) -> None:
        before = build_period_flows(
            payload=self.payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 9, 7, 23, 40),
        )
        after = build_period_flows(
            payload=self.payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 9, 7, 23, 42),
        )

        self.assertEqual(before.month.evidence[0].value, "입추")
        self.assertEqual(after.month.evidence[0].value, "백로")
        self.assertNotEqual(before.month.target_gan_zhi, after.month.target_gan_zhi)

    def test_estimated_birth_time_does_not_show_luck_cycle_connection(self) -> None:
        estimated_payload = self.payload.copy(
            update={"is_birth_time_estimated": True, "birth_time": "00:00"}
        )

        flows = build_period_flows(
            payload=estimated_payload,
            region=self.region,
            saju_calculation=self.calculation,
            as_of=datetime(2026, 8, 25, 12, 0),
        )

        self.assertIsNone(flows.month.current_luck_cycle)
        self.assertTrue(any("출생시간 미상" in note for note in flows.month.notes))


if __name__ == "__main__":
    unittest.main()
