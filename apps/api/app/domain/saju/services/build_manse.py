"""이 파일은 만세력을 조립하는 로직을 담는다."""

from typing import Dict, List, Optional

from app.domain.saju.analysis import AnalysisResult
from app.domain.saju.engine import PillarData, SajuCalculationResult, SupplementaryPosition
from app.domain.saju.schemas import (
    ManseAnalysisSummary,
    ManseData,
    ManseElementSummary,
    ManseElementPercentageSummary,
    ManseMeta,
    MansePillar,
    MansePillarSet,
    ManseSupplementaryPosition,
    ManseSupplementaryPositionSet,
    ManseTableRow,
)
from app.domain.saju.services.birth_time_policy import BirthTimePolicyResult
from app.domain.saju.services.calculate_special_stars import build_special_stars


PILLAR_LABELS = {
    "year": "년주",
    "month": "월주",
    "day": "일주",
    "time": "시주",
}

SUPPLEMENTARY_LABELS = {
    "tai_yuan": "태원",
    "ming_gong": "명궁",
    "shen_gong": "신궁",
    "tai_xi": "태식",
}

TEN_GOD_KO_BY_VALUE = {
    "比肩": "비견",
    "劫财": "겁재",
    "食神": "식신",
    "伤官": "상관",
    "偏财": "편재",
    "正财": "정재",
    "七杀": "편관",
    "正官": "정관",
    "偏印": "편인",
    "正印": "정인",
    "日主": "비견",
    "비견": "비견",
    "겁재": "겁재",
    "식신": "식신",
    "상관": "상관",
    "편재": "편재",
    "정재": "정재",
    "편관": "편관",
    "정관": "정관",
    "편인": "편인",
    "정인": "정인",
}

TWELVE_FORTUNE_KO_BY_VALUE = {
    "长生": "장생",
    "沐浴": "목욕",
    "冠带": "관대",
    "临官": "건록",
    "帝旺": "제왕",
    "衰": "쇠",
    "病": "병",
    "死": "사",
    "墓": "묘",
    "绝": "절",
    "胎": "태",
    "养": "양",
    "장생": "장생",
    "목욕": "목욕",
    "관대": "관대",
    "건록": "건록",
    "제왕": "제왕",
    "쇠": "쇠",
    "병": "병",
    "사": "사",
    "묘": "묘",
    "절": "절",
    "태": "태",
    "양": "양",
}

TWELVE_SHINSAL_KO_BY_VALUE = {
    "겁살": "겁살",
    "재살": "재살",
    "천살": "천살",
    "지살": "지살",
    "도화": "년살",
    "도화살": "년살",
    "월살": "월살",
    "망신": "망신살",
    "망신살": "망신살",
    "장성": "장성살",
    "장성살": "장성살",
    "반안": "반안살",
    "반안살": "반안살",
    "역마": "역마살",
    "역마살": "역마살",
    "육해": "육해살",
    "육해살": "육해살",
    "화개": "화개살",
    "화개살": "화개살",
    "년살": "년살",
}

HIDDEN_STEMS_BY_BRANCH = {
    "寅": ["무", "병", "갑"],
    "卯": ["갑", "을"],
    "辰": ["을", "계", "무"],
    "巳": ["무", "경", "병"],
    "午": ["병", "기", "정"],
    "未": ["정", "을", "기"],
    "申": ["무", "임", "경"],
    "酉": ["경", "신"],
    "戌": ["신", "정", "무"],
    "亥": ["무", "갑", "임"],
    "子": ["임", "계"],
    "丑": ["계", "신", "기"],
}

SAMHAP_GROUP_BY_BRANCH = {
    "亥": "wood",
    "卯": "wood",
    "未": "wood",
    "寅": "fire",
    "午": "fire",
    "戌": "fire",
    "巳": "metal",
    "酉": "metal",
    "丑": "metal",
    "申": "water",
    "子": "water",
    "辰": "water",
}

TWELVE_SHINSAL_BY_GROUP = {
    "wood": {
        "申": "겁살",
        "酉": "재살",
        "戌": "천살",
        "亥": "지살",
        "子": "도화",
        "丑": "월살",
        "寅": "망신",
        "卯": "장성",
        "辰": "반안",
        "巳": "역마",
        "午": "육해",
        "未": "화개",
    },
    "fire": {
        "亥": "겁살",
        "子": "재살",
        "丑": "천살",
        "寅": "지살",
        "卯": "도화",
        "辰": "월살",
        "巳": "망신",
        "午": "장성",
        "未": "반안",
        "申": "역마",
        "酉": "육해",
        "戌": "화개",
    },
    "metal": {
        "寅": "겁살",
        "卯": "재살",
        "辰": "천살",
        "巳": "지살",
        "午": "도화",
        "未": "월살",
        "申": "망신",
        "酉": "장성",
        "戌": "반안",
        "亥": "역마",
        "子": "육해",
        "丑": "화개",
    },
    "water": {
        "巳": "겁살",
        "午": "재살",
        "未": "천살",
        "申": "지살",
        "酉": "도화",
        "戌": "월살",
        "亥": "망신",
        "子": "장성",
        "丑": "반안",
        "寅": "역마",
        "卯": "육해",
        "辰": "화개",
    },
}


def _twelve_shinsal_for_pillar(
    *,
    pillars: Dict[str, PillarData],
    pillar_key: str,
) -> str:
    # Golden answers align with the convention where:
    # - the year pillar's 12신살 is anchored on the day branch
    # - the month/day/time pillar 12신살 are anchored on the year branch
    """shinsal for 기둥 관련 값을 반환하거나 처리한다."""
    anchor_branch = pillars["day"].branch if pillar_key == "year" else pillars["year"].branch
    group_key = SAMHAP_GROUP_BY_BRANCH.get(anchor_branch)
    if not group_key:
        return ""
    return TWELVE_SHINSAL_BY_GROUP[group_key].get(pillars[pillar_key].branch, "")


def _mask_value(value: str, enabled: bool) -> Optional[str]:
    """값을 숨긴다."""
    return value if enabled else None


def _mask_list(values: List[str], enabled: bool) -> List[str]:
    """list을 숨긴다."""
    return list(values) if enabled else []


def _normalize_ten_god(value: str, *, pillar_key: str, role: str) -> str:
    """ten god를 정규화한다."""
    if pillar_key == "day" and role == "stem":
        return "비견"
    return TEN_GOD_KO_BY_VALUE.get(value, value)


def _normalize_twelve_fortune(value: str) -> str:
    """twelve fortune를 정규화한다."""
    return TWELVE_FORTUNE_KO_BY_VALUE.get(value, value)


def _normalize_twelve_shinsal(value: str) -> str:
    """twelve shinsal를 정규화한다."""
    return TWELVE_SHINSAL_KO_BY_VALUE.get(value, value)


def _normalize_hidden_stems(branch: str, fallback_values: List[str]) -> List[str]:
    """지장간 stems를 정규화한다."""
    if branch in HIDDEN_STEMS_BY_BRANCH:
        return list(HIDDEN_STEMS_BY_BRANCH[branch])
    return [value for value in fallback_values if value]


def _build_pillar(
    *,
    pillar_key: str,
    pillar: PillarData,
    enabled: bool,
    twelve_shinsal: str,
) -> MansePillar:
    """기둥을 조립한다."""
    return MansePillar(
        key=pillar_key,
        label=PILLAR_LABELS[pillar_key],
        enabled=enabled,
        gan_zhi=_mask_value(pillar.gan_zhi, enabled),
        stem=_mask_value(pillar.stem, enabled),
        branch=_mask_value(pillar.branch, enabled),
        stem_element=_mask_value(pillar.stem_five_element, enabled),
        branch_element=_mask_value(pillar.branch_five_element, enabled),
        stem_ten_god=_mask_value(
            _normalize_ten_god(pillar.stem_ten_god, pillar_key=pillar_key, role="stem"),
            enabled,
        ),
        branch_ten_god=_mask_value(
            _normalize_ten_god(pillar.branch_ten_god, pillar_key=pillar_key, role="branch"),
            enabled,
        ),
        branch_ten_gods=_mask_list(
            [
                _normalize_ten_god(value, pillar_key=pillar_key, role="branch")
                for value in pillar.branch_ten_gods
            ],
            enabled,
        ),
        hidden_stems=_mask_list(_normalize_hidden_stems(pillar.branch, pillar.hidden_stems), enabled),
        twelve_fortune=_mask_value(_normalize_twelve_fortune(pillar.twelve_fortune), enabled),
        twelve_shinsal=_mask_value(_normalize_twelve_shinsal(twelve_shinsal), enabled),
        na_yin=_mask_value(pillar.na_yin, enabled),
        xun=_mask_value(pillar.xun, enabled),
        xun_kong=_mask_value(pillar.xun_kong, enabled),
    )


def _row_value(pillars: Dict[str, MansePillar], pillar_key: str, field_name: str) -> str:
    """값 관련 값을 반환하거나 처리한다."""
    value = getattr(pillars[pillar_key], field_name)
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(value)
    return value


def _build_table_rows(pillars: Dict[str, MansePillar]) -> List[ManseTableRow]:
    """표 rows을 조립한다."""
    row_specs = [
        ("천간", "stem"),
        ("천간 십성", "stem_ten_god"),
        ("지지", "branch"),
        ("지지 십성", "branch_ten_god"),
        ("지장간", "hidden_stems"),
        ("12운성", "twelve_fortune"),
        ("12신살", "twelve_shinsal"),
        ("납음", "na_yin"),
        ("공망", "xun_kong"),
    ]

    return [
        ManseTableRow(
            label=label,
            year=_row_value(pillars, "year", field_name),
            month=_row_value(pillars, "month", field_name),
            day=_row_value(pillars, "day", field_name),
            time=_row_value(pillars, "time", field_name),
        )
        for label, field_name in row_specs
    ]


def _build_visible_ten_god_distribution(
    pillars: Dict[str, MansePillar],
    visible_pillar_keys: List[str],
) -> Dict[str, int]:
    """표시 대상 ten god distribution을 조립한다."""
    distribution: Dict[str, int] = {}
    for pillar_key in visible_pillar_keys:
        pillar = pillars[pillar_key]
        for value in [pillar.stem_ten_god, pillar.branch_ten_god]:
            if value:
                distribution[value] = distribution.get(value, 0) + 1
    return distribution


def _build_analysis_summary(
    *,
    analysis_result: AnalysisResult,
    pillars: Dict[str, MansePillar],
    visible_pillar_keys: List[str],
    first_luck_cycle,
    luck_cycles_enabled: bool,
) -> ManseAnalysisSummary:
    """분석 요약을 조립한다."""
    return ManseAnalysisSummary(
        visible_element_total=analysis_result.visible_element_total,
        imbalance_gap=analysis_result.imbalance_gap,
        dominant_elements=analysis_result.dominant_elements,
        missing_elements=analysis_result.missing_elements,
        element_percentages=ManseElementPercentageSummary(**analysis_result.element_percentages),
        visible_ten_god_distribution=_build_visible_ten_god_distribution(
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        ),
        balance_score=analysis_result.balance_score,
        internal_grade=analysis_result.internal_grade,
        charm_score=analysis_result.charm_score,
        wealth_score=analysis_result.wealth_score,
        career_score=analysis_result.career_score,
        leadership_score=analysis_result.leadership_score,
        first_luck_cycle_direction=(
            first_luck_cycle.direction if luck_cycles_enabled and first_luck_cycle else None
        ),
        first_luck_cycle_exact_start_age_years=(
            first_luck_cycle.exact_start_age_years
            if luck_cycles_enabled and first_luck_cycle and first_luck_cycle.exact_start_age_years is not None
            else None
        ),
        first_luck_cycle_precise_start_age_years=(
            first_luck_cycle.precise_start_age_years
            if luck_cycles_enabled and first_luck_cycle and first_luck_cycle.precise_start_age_years is not None
            else None
        ),
        first_luck_cycle_start_age_years=(
            first_luck_cycle.start_age_years
            if luck_cycles_enabled and first_luck_cycle and first_luck_cycle.start_age_years is not None
            else None
        ),
        first_luck_cycle_start_age_months=(
            first_luck_cycle.start_age_months
            if luck_cycles_enabled and first_luck_cycle and first_luck_cycle.start_age_months is not None
            else None
        ),
        first_luck_cycle_start_age_total_months=(
            first_luck_cycle.start_age_total_months
            if luck_cycles_enabled and first_luck_cycle and first_luck_cycle.start_age_total_months is not None
            else None
        ),
        first_luck_cycle_boundary_datetime=(
            first_luck_cycle.month_boundary_datetime if luck_cycles_enabled and first_luck_cycle else None
        ),
    )


def _build_supplementary_positions(
    *,
    supplementary_positions: Dict[str, SupplementaryPosition],
) -> ManseSupplementaryPositionSet:
    """보조 위치 목록을 조립한다."""
    positions: Dict[str, ManseSupplementaryPosition] = {}
    for key in ["tai_yuan", "ming_gong", "shen_gong", "tai_xi"]:
        position = supplementary_positions[key]
        positions[key] = ManseSupplementaryPosition(
            key=key,
            label=SUPPLEMENTARY_LABELS.get(key, key),
            gan_zhi=position.gan_zhi,
            na_yin=position.na_yin,
        )
    return ManseSupplementaryPositionSet(**positions)


def build_manse_data(
    *,
    saju_calculation: SajuCalculationResult,
    analysis_result: AnalysisResult,
    birth_time_policy: BirthTimePolicyResult,
) -> ManseData:
    """계산 결과와 분석 결과를 만세력 응답 모델로 조립한다."""
    visible_luck_cycles = [cycle for cycle in saju_calculation.luck_cycles if cycle.gan_zhi]
    first_luck_cycle = visible_luck_cycles[0] if visible_luck_cycles else None
    pillar_enabled_map = {
        "year": True,
        "month": True,
        "day": True,
        "time": birth_time_policy.hour_pillar_enabled,
    }

    pillar_dict = {
        pillar_key: _build_pillar(
            pillar_key=pillar_key,
            pillar=pillar,
            enabled=pillar_enabled_map[pillar_key],
            twelve_shinsal=_twelve_shinsal_for_pillar(
                pillars=saju_calculation.pillars,
                pillar_key=pillar_key,
            ),
        )
        for pillar_key, pillar in saju_calculation.pillars.items()
    }
    pillars = MansePillarSet(**pillar_dict)

    notes: List[str] = []
    if not birth_time_policy.hour_pillar_enabled:
        notes.append("출생시간 미상으로 시주와 시주 기반 대운 정보는 비활성화되었습니다.")

    return ManseData(
        meta=ManseMeta(
            day_master=saju_calculation.meta["day_master"],
            pillar_order=["year", "month", "day", "time"],
            visible_pillar_keys=list(birth_time_policy.visible_pillar_keys),
            hour_pillar_enabled=birth_time_policy.hour_pillar_enabled,
            day_pillar_rule=saju_calculation.meta.get("day_pillar_rule", ""),
            day_time_basis_datetime=saju_calculation.meta.get("day_time_basis_datetime", ""),
            civil_date=saju_calculation.meta.get("civil_date", ""),
            day_pillar_basis_date=saju_calculation.meta.get("day_pillar_basis_date", ""),
            iljin_query_date=saju_calculation.meta.get("iljin_query_date", ""),
            day_pillar_source=saju_calculation.meta.get("day_pillar_source", ""),
            day_pillar_reference_matched_lunar_python=saju_calculation.meta.get(
                "day_pillar_reference_matched_lunar_python",
                "",
            ),
        ),
        pillars=pillars,
        table_rows=_build_table_rows(pillar_dict),
        elements=ManseElementSummary(**analysis_result.visible_element_counts),
        analysis=_build_analysis_summary(
            analysis_result=analysis_result,
            pillars=pillar_dict,
            visible_pillar_keys=list(birth_time_policy.visible_pillar_keys),
            first_luck_cycle=first_luck_cycle,
            luck_cycles_enabled=birth_time_policy.hour_pillar_enabled,
        ),
        luck_cycles_enabled=birth_time_policy.hour_pillar_enabled,
        luck_cycles=(
            [
                {
                    "index": cycle.index,
                    "gan_zhi": cycle.gan_zhi,
                    "start_year": cycle.start_year,
                    "end_year": cycle.end_year,
                    "start_age": cycle.start_age,
                    "end_age": cycle.end_age,
                    "start_age_years": cycle.start_age_years,
                    "start_age_months": cycle.start_age_months,
                    "start_age_total_months": cycle.start_age_total_months,
                    "change_age_years": cycle.change_age_years,
                    "change_age_months": cycle.change_age_months,
                    "change_age_total_months": cycle.change_age_total_months,
                    "start_datetime": cycle.start_datetime,
                    "change_datetime": cycle.change_datetime,
                }
                for cycle in visible_luck_cycles
            ]
            if birth_time_policy.hour_pillar_enabled
            else []
        ),
        supplementary_positions=_build_supplementary_positions(
            supplementary_positions=saju_calculation.supplementary_positions,
        ),
        special_stars=build_special_stars(
            pillars=saju_calculation.pillars,
            visible_pillar_keys=list(birth_time_policy.visible_pillar_keys),
        ),
        notes=notes,
    )
