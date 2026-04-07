from typing import Dict, List, Optional

from app.domain.saju.analysis import AnalysisResult
from app.domain.saju.engine import PillarData, SajuCalculationResult, SupplementaryPosition
from app.domain.saju.schemas import (
    ManseData,
    ManseElementSummary,
    ManseMeta,
    MansePillar,
    MansePillarSet,
    ManseSupplementaryPosition,
    ManseSupplementaryPositionSet,
    ManseTableRow,
)
from app.domain.saju.services.birth_time_policy import BirthTimePolicyResult


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
    day_branch = pillars["day"].branch
    group_key = SAMHAP_GROUP_BY_BRANCH.get(day_branch)
    if not group_key:
        return ""
    return TWELVE_SHINSAL_BY_GROUP[group_key].get(pillars[pillar_key].branch, "")


def _mask_value(value: str, enabled: bool) -> Optional[str]:
    return value if enabled else None


def _mask_list(values: List[str], enabled: bool) -> List[str]:
    return list(values) if enabled else []


def _build_pillar(
    *,
    pillar_key: str,
    pillar: PillarData,
    enabled: bool,
    twelve_shinsal: str,
) -> MansePillar:
    return MansePillar(
        key=pillar_key,
        label=PILLAR_LABELS[pillar_key],
        enabled=enabled,
        gan_zhi=_mask_value(pillar.gan_zhi, enabled),
        stem=_mask_value(pillar.stem, enabled),
        branch=_mask_value(pillar.branch, enabled),
        stem_element=_mask_value(pillar.stem_five_element, enabled),
        branch_element=_mask_value(pillar.branch_five_element, enabled),
        stem_ten_god=_mask_value(pillar.stem_ten_god, enabled),
        branch_ten_god=_mask_value(pillar.branch_ten_god, enabled),
        branch_ten_gods=_mask_list(pillar.branch_ten_gods, enabled),
        hidden_stems=_mask_list(pillar.hidden_stems, enabled),
        twelve_fortune=_mask_value(pillar.twelve_fortune, enabled),
        twelve_shinsal=_mask_value(twelve_shinsal, enabled),
        na_yin=_mask_value(pillar.na_yin, enabled),
        xun=_mask_value(pillar.xun, enabled),
        xun_kong=_mask_value(pillar.xun_kong, enabled),
    )


def _row_value(pillars: Dict[str, MansePillar], pillar_key: str, field_name: str) -> str:
    value = getattr(pillars[pillar_key], field_name)
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(value)
    return value


def _build_table_rows(pillars: Dict[str, MansePillar]) -> List[ManseTableRow]:
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


def _build_supplementary_positions(
    *,
    supplementary_positions: Dict[str, SupplementaryPosition],
) -> ManseSupplementaryPositionSet:
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
        ),
        pillars=pillars,
        table_rows=_build_table_rows(pillar_dict),
        elements=ManseElementSummary(**analysis_result.visible_element_counts),
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
                }
                for cycle in saju_calculation.luck_cycles
            ]
            if birth_time_policy.hour_pillar_enabled
            else []
        ),
        supplementary_positions=_build_supplementary_positions(
            supplementary_positions=saju_calculation.supplementary_positions,
        ),
        notes=notes,
    )
