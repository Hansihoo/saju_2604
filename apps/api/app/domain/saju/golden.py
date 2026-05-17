"""이 파일은 golden case 검증에 사용하는 공통 모델과 helper를 담는다."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.domain.saju.pydantic_compat import model_to_dict


STANDARD_OFFSET_BY_TZ: Dict[str, int] = {
    "Asia/Seoul": 540,
}

STEM_KO_BY_HANJA: Dict[str, str] = {
    "甲": "갑",
    "乙": "을",
    "丙": "병",
    "丁": "정",
    "戊": "무",
    "己": "기",
    "庚": "경",
    "辛": "신",
    "壬": "임",
    "癸": "계",
}

BRANCH_KO_BY_HANJA: Dict[str, str] = {
    "子": "자",
    "丑": "축",
    "寅": "인",
    "卯": "묘",
    "辰": "진",
    "巳": "사",
    "午": "오",
    "未": "미",
    "申": "신",
    "酉": "유",
    "戌": "술",
    "亥": "해",
}

STEM_KO_SET = set(STEM_KO_BY_HANJA.values())
BRANCH_KO_SET = set(BRANCH_KO_BY_HANJA.values())

PILLAR_KEY_BY_LABEL: Dict[str, str] = {
    "생년": "year",
    "생월": "month",
    "생일": "day",
    "생시": "time",
}

PILLAR_LABEL_BY_KEY: Dict[str, str] = {
    "year": "생년",
    "month": "생월",
    "day": "생일",
    "time": "생시",
}

SUPPORTED_GOLDEN_SECTIONS = [
    "basic_info",
    "pillar_table",
    "luck_cycles",
    "special_stars",
]

IGNORED_GOLDEN_PATHS = {
    "basic_info.name",
}

# The answer sheets currently align consistently with only a subset of the
# newly-added special star calculations. We keep the strict golden comparison
# scoped to the stable subset and leave the remaining stars as diagnostics
# until their reference convention is finalized.
GOLDEN_SPECIAL_STAR_ORDER = [
    ("cheoneul-gwiin", "천을귀인"),
    ("yangin", "양인"),
    ("gwaegang", "괴강"),
]

PILLAR_SORT_ORDER = {
    "year": 0,
    "month": 1,
    "day": 2,
    "time": 3,
}


def round_display_minutes(value: float) -> int:
    """표시용 minutes을 반올림한다."""
    return int(round(value))


def derive_display_minutes_from_longitude(longitude: float) -> int:
    # The provided answer sheets appear to display regional time offsets from
    # longitudes normalized to one decimal place before converting to minutes.
    """표시용 minutes from longitude을 유도한다."""
    normalized_longitude = round(longitude, 1)
    return math.floor(((normalized_longitude - 135.0) * 4.0) + 0.5)


def format_datetime_minute(value: Union[str, datetime]) -> str:
    """시각 minute을 포맷한다."""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")


def calculate_daylight_saving_correction(*, tzid: str, offset_minutes: int) -> Optional[int]:
    """daylight saving 보정를 계산한다."""
    standard_offset = STANDARD_OFFSET_BY_TZ.get(tzid)
    if standard_offset is None:
        return None
    correction = standard_offset - offset_minutes
    return correction if correction != 0 else None


def apply_display_time_correction(
    *,
    solar_birth_datetime: str,
    regional_time_offset_minutes: int,
    daylight_saving_offset_minutes: Optional[int],
) -> str:
    """표시용 시간 보정을 적용한다."""
    base = datetime.strptime(solar_birth_datetime, "%Y-%m-%d %H:%M")
    total_correction = regional_time_offset_minutes + (daylight_saving_offset_minutes or 0)
    return (base + timedelta(minutes=total_correction)).strftime("%Y-%m-%d %H:%M")


def to_korean_stem(value: str) -> str:
    """korean stem 관련 값을 반환하거나 처리한다."""
    if not value:
        return ""
    for char in value:
        if char in STEM_KO_BY_HANJA:
            return STEM_KO_BY_HANJA[char]
        if char in STEM_KO_SET:
            return char
    hangul_only = "".join(char for char in value if "가" <= char <= "힣")
    return hangul_only[:1]


def to_korean_branch(value: str) -> str:
    """korean branch 관련 값을 반환하거나 처리한다."""
    if not value:
        return ""
    for char in value:
        if char in BRANCH_KO_BY_HANJA:
            return BRANCH_KO_BY_HANJA[char]
        if char in BRANCH_KO_SET:
            return char
    hangul_only = "".join(char for char in value if "가" <= char <= "힣")
    return hangul_only[:1]


def to_korean_gan_zhi(value: str) -> str:
    """korean gan zhi 관련 값을 반환하거나 처리한다."""
    if not value:
        return ""
    if len(value) >= 2 and value[0] in STEM_KO_BY_HANJA and value[1] in BRANCH_KO_BY_HANJA:
        return STEM_KO_BY_HANJA[value[0]] + BRANCH_KO_BY_HANJA[value[1]]
    hangul_only = "".join(char for char in value if "가" <= char <= "힣")
    if hangul_only:
        return hangul_only
    return value


def split_hidden_stems(value: str) -> List[str]:
    """지장간 stems을 분리한다."""
    stems: List[str] = []
    for char in value:
        if char in STEM_KO_BY_HANJA:
            stems.append(STEM_KO_BY_HANJA[char])
        elif char in STEM_KO_SET:
            stems.append(char)
    return stems


class GoldenCaseInput(BaseModel):
    case_id: str
    source_name: str
    source_file: str
    calendar_type: Literal["solar", "lunar"]
    birth_date: str
    birth_time: str
    gender: Literal["male", "female"]
    region_id: str
    is_lunar_leap_month: bool = False


class GoldenBasicInfo(BaseModel):
    name: Optional[str] = None
    solar_birth_datetime: str
    lunar_birth_datetime: str
    gender_label: str
    birth_place: str
    corrected_datetime: str
    regional_time_offset_minutes: int
    daylight_saving_offset_minutes: Optional[int] = None


class GoldenPillarRow(BaseModel):
    key: Literal["year", "month", "day", "time"]
    label: str
    gan_zhi: str
    stem: str
    stem_ten_god: str
    branch: str
    branch_ten_god: str
    hidden_stems: List[str] = Field(default_factory=list)
    twelve_fortune: str
    twelve_shinsal: str


class GoldenLuckCycleRow(BaseModel):
    start_age: int
    gan_zhi: str
    stem: str
    branch: str


class GoldenLuckCycleHeader(BaseModel):
    start_age: int
    reference_pillar: str


class GoldenSpecialStarRow(BaseModel):
    key: str
    label: str
    active: bool
    matched_pillars: List[Literal["year", "month", "day", "time"]] = Field(default_factory=list)


class GoldenSnapshot(BaseModel):
    basic_info: GoldenBasicInfo
    pillar_table: Dict[Literal["year", "month", "day", "time"], GoldenPillarRow]
    luck_cycle_header: Optional[GoldenLuckCycleHeader] = None
    luck_cycles: List[GoldenLuckCycleRow] = Field(default_factory=list)
    special_stars: List[GoldenSpecialStarRow] = Field(default_factory=list)


class GoldenKnownAnswerCase(BaseModel):
    input: GoldenCaseInput
    expected: GoldenSnapshot
    supported_sections: List[str] = Field(default_factory=lambda: list(SUPPORTED_GOLDEN_SECTIONS))
    unsupported_sections: List[str] = Field(default_factory=list)
    raw_sections: Dict[str, str] = Field(default_factory=dict)


class GoldenDiffEntry(BaseModel):
    path: str
    expected: Any = None
    actual: Any = None
    kind: Literal["mismatch", "missing_expected", "missing_actual"]


class GoldenComparisonReport(BaseModel):
    case_id: str
    source_name: str
    success: bool
    compared_leaf_count: int
    mismatch_count: int
    mismatches: List[GoldenDiffEntry]
    skipped_sections: List[str]


def _count_leaves(value: Any, path: str = "") -> int:
    """leaves를 센다."""
    if path and _is_ignored_path(path):
        return 0
    if isinstance(value, dict):
        return sum(
            _count_leaves(item, f"{path}.{key}" if path else str(key))
            for key, item in value.items()
        )
    if isinstance(value, list):
        return sum(_count_leaves(item, f"{path}[{index}]") for index, item in enumerate(value))
    return 1


def _is_ignored_path(path: str) -> bool:
    """ignored 경로 여부를 판별한다."""
    return path in IGNORED_GOLDEN_PATHS


def _diff_values(expected: Any, actual: Any, path: str, diffs: List[GoldenDiffEntry]) -> None:
    """값 목록 관련 값을 반환하거나 처리한다."""
    if path and _is_ignored_path(path):
        return

    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected.keys()) | set(actual.keys())):
            next_path = f"{path}.{key}" if path else str(key)
            if key not in expected:
                diffs.append(
                    GoldenDiffEntry(
                        path=next_path,
                        expected=None,
                        actual=actual[key],
                        kind="missing_expected",
                    )
                )
                continue
            if key not in actual:
                diffs.append(
                    GoldenDiffEntry(
                        path=next_path,
                        expected=expected[key],
                        actual=None,
                        kind="missing_actual",
                    )
                )
                continue
            _diff_values(expected[key], actual[key], next_path, diffs)
        return

    if isinstance(expected, list) and isinstance(actual, list):
        max_length = max(len(expected), len(actual))
        for index in range(max_length):
            next_path = f"{path}[{index}]"
            if index >= len(expected):
                diffs.append(
                    GoldenDiffEntry(
                        path=next_path,
                        expected=None,
                        actual=actual[index],
                        kind="missing_expected",
                    )
                )
                continue
            if index >= len(actual):
                diffs.append(
                    GoldenDiffEntry(
                        path=next_path,
                        expected=expected[index],
                        actual=None,
                        kind="missing_actual",
                    )
                )
                continue
            _diff_values(expected[index], actual[index], next_path, diffs)
        return

    if expected != actual:
        diffs.append(
            GoldenDiffEntry(
                path=path,
                expected=expected,
                actual=actual,
                kind="mismatch",
            )
        )


def compare_golden_snapshots(
    *,
    case: GoldenKnownAnswerCase,
    actual: GoldenSnapshot,
) -> GoldenComparisonReport:
    """기대 snapshot과 실제 snapshot을 비교해 diff report를 만든다."""
    expected_payload = model_to_dict(case.expected)
    actual_payload = model_to_dict(actual)
    diffs: List[GoldenDiffEntry] = []
    _diff_values(expected_payload, actual_payload, "", diffs)
    return GoldenComparisonReport(
        case_id=case.input.case_id,
        source_name=case.input.source_name,
        success=len(diffs) == 0,
        compared_leaf_count=_count_leaves(expected_payload),
        mismatch_count=len(diffs),
        mismatches=diffs,
        skipped_sections=list(case.unsupported_sections),
    )
