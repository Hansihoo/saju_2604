import json
import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from typing import Any, Dict, Iterable, List
from unittest.mock import patch

from app.domain.saju.pydantic_compat import model_to_dict
from app.domain.saju.schemas import RegionSuggestion, SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "saju_preview_golden_cases.json"

EXCLUDED_FIELDS = [
    "trace_id",
    "result.interpretation",
    "result.overview",
    "result.strengths",
    "result.cautions",
    "result.love",
    "result.career",
    "result.wealth",
    "result.action_advice",
    "debug_trace",
]

SEED_CASES: List[Dict[str, Any]] = [
    {
        "id": "kr_solar_regular",
        "description": "Regular Korea solar birth.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "2024-02-10",
            "birth_time": "10:30",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "male",
            "region_id": "kr-seoul",
            "debug": False,
        },
    },
    {
        "id": "estimated_birth_time",
        "description": "Birth time estimated; engine uses 00:00 and hides hour-dependent output.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "1994-10-13",
            "birth_time": "08:30",
            "is_birth_time_estimated": True,
            "is_lunar_leap_month": False,
            "gender": "female",
            "region_id": "kr-seoul",
            "debug": False,
        },
    },
    {
        "id": "late_zi_2330",
        "description": "Late zi-hour boundary case at 23:30.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "1988-11-20",
            "birth_time": "23:30",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "male",
            "region_id": "kr-seoul-special",
            "debug": False,
        },
    },
    {
        "id": "early_0030",
        "description": "Early day boundary case at 00:30.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "1988-11-21",
            "birth_time": "00:30",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "male",
            "region_id": "kr-seoul-special",
            "debug": False,
        },
    },
    {
        "id": "seoul_longitude_correction",
        "description": "Seoul longitude correction case.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "1996-06-19",
            "birth_time": "15:03",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "female",
            "region_id": "kr-seoul-special",
            "debug": False,
        },
    },
    {
        "id": "korea_dst_1988",
        "description": "Korea daylight-saving period in 1988.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "1988-05-20",
            "birth_time": "12:30",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "female",
            "region_id": "kr-seoul-special",
            "debug": False,
        },
    },
    {
        "id": "lunar_input_regular",
        "description": "Regular lunar input converted through the preview pipeline.",
        "request": {
            "calendar_type": "lunar",
            "birth_date": "2024-01-01",
            "birth_time": "10:30",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "male",
            "region_id": "kr-seoul",
            "debug": False,
        },
    },
    {
        "id": "lunar_leap_month_input",
        "description": "Leap lunar month input converted through the preview pipeline.",
        "request": {
            "calendar_type": "lunar",
            "birth_date": "2023-02-15",
            "birth_time": "10:30",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": True,
            "gender": "female",
            "region_id": "kr-seoul",
            "debug": False,
        },
    },
    {
        "id": "solar_term_near_ipchun",
        "description": "Birth close to an Ipchun solar-term boundary.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "2024-02-04",
            "birth_time": "17:00",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "female",
            "region_id": "kr-seoul",
            "debug": False,
        },
    },
    {
        "id": "overseas_timezone_new_york",
        "description": "Overseas timezone case using a test-only region override.",
        "request": {
            "calendar_type": "solar",
            "birth_date": "1990-07-15",
            "birth_time": "14:20",
            "is_birth_time_estimated": False,
            "is_lunar_leap_month": False,
            "gender": "female",
            "region_id": "test-new-york",
            "debug": False,
        },
        "region_override": {
            "id": "test-new-york",
            "display_name": "New York, United States",
            "country": "United States",
            "province": "New York",
            "city": "New York",
            "tzid": "America/New_York",
            "longitude": -74.006,
            "regional_time_offset_minutes": 3.976,
            "correction_basis": "test-standard-meridian-longitude",
            "aliases": ["New York", "NYC"],
        },
    },
]


def _case_definition_without_expected(case: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in case.items() if key != "expected"}


def _load_case_definitions_for_update() -> List[Dict[str, Any]]:
    if not FIXTURE_PATH.exists():
        return [_case_definition_without_expected(case) for case in SEED_CASES]

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [_case_definition_without_expected(case) for case in fixture["cases"]]


def _region_patch_context(case: Dict[str, Any]):
    region_override = case.get("region_override")
    if not region_override:
        return nullcontext()

    return patch(
        "app.domain.saju.services.preview_orchestrator.find_region_by_id",
        return_value=RegionSuggestion(**region_override),
    )


def _build_response(case: Dict[str, Any]):
    payload = SajuPreviewRequest(**case["request"])
    with patch("app.domain.saju.services.generate_interpretation.settings.llm_provider", "fallback"):
        with _region_patch_context(case):
            return create_saju_preview_response(
                payload=payload,
                trace_id=f"golden-preview-{case['id']}",
                debug_requested=False,
                service_name="test",
            )


def _extract_golden_snapshot(case: Dict[str, Any]) -> Dict[str, Any]:
    response = _build_response(case)
    first_luck_cycle = response.manse.luck_cycles[0] if response.manse.luck_cycles else None

    return {
        "regional_solar_correction": {
            "corrected_solar_datetime": response.regional_solar_correction.corrected_solar_datetime,
            "regional_time_offset_minutes": response.regional_solar_correction.regional_time_offset_minutes,
            "daylight_saving_offset_minutes": response.regional_solar_correction.daylight_saving_offset_minutes,
        },
        "time_correction": {
            "normalized_local_datetime": response.time_correction.normalized_local_datetime,
            "normalized_utc_datetime": response.time_correction.normalized_utc_datetime,
            "offset_minutes": response.time_correction.offset_minutes,
            "ambiguous": response.time_correction.ambiguous,
            "fold": response.time_correction.fold,
        },
        "calendar_normalization": {
            "normalized_solar_datetime": response.calendar_normalization.normalized_solar_datetime,
            "normalized_lunar_datetime": response.calendar_normalization.normalized_lunar_datetime,
        },
        "manse": {
            "pillars": {
                "year": model_to_dict(response.manse.pillars.year),
                "month": model_to_dict(response.manse.pillars.month),
                "day": model_to_dict(response.manse.pillars.day),
                "time": model_to_dict(response.manse.pillars.time),
            },
            "luck_cycles_enabled": response.manse.luck_cycles_enabled,
            "first_luck_cycle": (
                {
                    "gan_zhi": first_luck_cycle.gan_zhi,
                    "start_age": first_luck_cycle.start_age,
                }
                if first_luck_cycle is not None
                else None
            ),
        },
        "result": {
            "hour_pillar_enabled": response.result.hour_pillar_enabled,
        },
    }


def _build_fixture_payload(cases: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "description": "Golden regression baseline for deterministic /saju/preview calculation fields.",
        "excluded_fields": EXCLUDED_FIELDS,
        "cases": [
            {
                **_case_definition_without_expected(case),
                "expected": _extract_golden_snapshot(case),
            }
            for case in cases
        ],
    }


def write_fixture() -> None:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = _build_fixture_payload(_load_case_definitions_for_update())
    FIXTURE_PATH.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {FIXTURE_PATH}")


class SajuPreviewGoldenRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not FIXTURE_PATH.exists():
            raise AssertionError(
                f"Missing fixture: {FIXTURE_PATH}. "
                "Run `cd apps/api && python tests/test_saju_preview_golden_regression.py --write-fixture` "
                "only after intentionally accepting the current calculation baseline."
            )

        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_preview_calculation_fields_match_golden_fixture(self) -> None:
        self.assertEqual(self.fixture["schema_version"], 1)
        self.assertGreaterEqual(len(self.fixture["cases"]), 10)
        self.assertEqual(self.fixture["excluded_fields"], EXCLUDED_FIELDS)

        for case in self.fixture["cases"]:
            with self.subTest(case_id=case["id"]):
                actual = _extract_golden_snapshot(case)
                self.assertEqual(actual, case["expected"])


if __name__ == "__main__":
    if "--write-fixture" in sys.argv:
        write_fixture()
    else:
        unittest.main()
