"""Build extensible special-star output for the Manse payload."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Dict, Iterable, List, Literal, Optional, Sequence, Tuple

from app.domain.saju.engine import PillarData
from app.domain.saju.schemas import ManseSpecialStar, ManseSpecialStarMatch


VisiblePillarKey = Literal["year", "month", "day", "time"]
StarCategory = Literal["auspicious", "sinsal"]
StarTier = Literal["S", "A", "B"]
StarScope = Literal["core", "expanded", "optional"]
MatchField = Literal["stem", "branch", "gan_zhi", "pair"]


@dataclass(frozen=True)
class StarMetadata:
    key: str
    family: str
    label: str
    category: StarCategory
    tier: StarTier
    scope: StarScope
    weight: float
    method_id: str
    basis_key: str
    basis: str
    usage_summary: str
    usage_keywords: Tuple[str, ...]
    note: Optional[str] = None


PILLAR_LABELS: Dict[VisiblePillarKey, str] = {
    "year": "연주",
    "month": "월주",
    "day": "일주",
    "time": "시주",
}

TIER_WEIGHT = {
    "S": 1.0,
    "A": 0.72,
    "B": 0.45,
}

TRIAD_GROUP_BY_BRANCH = {
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

SEASONAL_GROUP_BY_BRANCH = {
    "寅": "spring",
    "卯": "spring",
    "辰": "spring",
    "巳": "summer",
    "午": "summer",
    "未": "summer",
    "申": "autumn",
    "酉": "autumn",
    "戌": "autumn",
    "亥": "winter",
    "子": "winter",
    "丑": "winter",
}

BRANCH_GROUP_TARGETS = {
    "dohwa": {
        "wood": "子",
        "fire": "卯",
        "metal": "午",
        "water": "酉",
    },
    "yeokma": {
        "wood": "巳",
        "fire": "申",
        "metal": "亥",
        "water": "寅",
    },
    "hwagae": {
        "wood": "未",
        "fire": "戌",
        "metal": "丑",
        "water": "辰",
    },
    "jangseong": {
        "wood": "卯",
        "fire": "午",
        "metal": "酉",
        "water": "子",
    },
}

SEASONAL_BRANCH_TARGETS = {
    "gojin": {
        "spring": "巳",
        "summer": "申",
        "autumn": "亥",
        "winter": "寅",
    },
    "guasuk": {
        "spring": "丑",
        "summer": "辰",
        "autumn": "未",
        "winter": "戌",
    },
}

CHEONEUL_GWIIN_TARGETS_BY_DAY_STEM = {
    "甲": ["丑", "未"],
    "乙": ["子", "申"],
    "丙": ["亥", "酉"],
    "丁": ["亥", "酉"],
    "戊": ["丑", "未"],
    "己": ["子", "申"],
    "庚": ["丑", "未"],
    "辛": ["寅", "午"],
    "壬": ["卯", "巳"],
    "癸": ["卯", "巳"],
}

WOLDEOK_GWIIN_TARGET_BY_MONTH_GROUP = {
    "fire": "丙",
    "water": "壬",
    "wood": "甲",
    "metal": "庚",
}

MUNCHANG_GWIIN_TARGET_BY_DAY_STEM = {
    "甲": "巳",
    "乙": "午",
    "丙": "申",
    "丁": "酉",
    "戊": "申",
    "己": "酉",
    "庚": "亥",
    "辛": "子",
    "壬": "寅",
    "癸": "卯",
}

TAEGEUK_GWIIN_TARGETS_BY_DAY_STEM = {
    "甲": ["子", "午"],
    "乙": ["子", "午"],
    "丙": ["卯", "酉"],
    "丁": ["卯", "酉"],
    "戊": ["辰", "戌", "丑", "未"],
    "己": ["辰", "戌", "丑", "未"],
    "庚": ["寅", "亥"],
    "辛": ["寅", "亥"],
    "壬": ["巳", "申"],
    "癸": ["巳", "申"],
}

HAKDANG_TARGET_BY_DAY_STEM = {
    "甲": "巳",
    "乙": "巳",
    "丙": "申",
    "丁": "申",
    "戊": "亥",
    "己": "亥",
    "庚": "寅",
    "辛": "寅",
    "壬": "申",
    "癸": "申",
}

SAGWAN_TARGET_BY_DAY_STEM = {
    "甲": "申",
    "乙": "申",
    "丙": "亥",
    "丁": "亥",
    "戊": "寅",
    "己": "寅",
    "庚": "巳",
    "辛": "巳",
    "壬": "亥",
    "癸": "亥",
}

CHEONDEOK_GWIIN_TARGET_BY_MONTH_BRANCH = {
    "寅": "丁",
    "卯": "申",
    "辰": "壬",
    "巳": "辛",
    "午": "亥",
    "未": "甲",
    "申": "癸",
    "酉": "寅",
    "戌": "丙",
    "亥": "乙",
    "子": "巳",
    "丑": "庚",
}

YANGIN_TARGET_BY_DAY_STEM = {
    "甲": "卯",
    "乙": "辰",
    "丙": "午",
    "丁": "未",
    "戊": "午",
    "己": "未",
    "庚": "酉",
    "辛": "戌",
    "壬": "子",
    "癸": "丑",
}

HONGYEOM_TARGET_BY_DAY_STEM = {
    "甲": "午",
    "乙": "午",
    "丙": "寅",
    "丁": "未",
    "戊": "辰",
    "己": "辰",
    "庚": "戌",
    "辛": "酉",
    "壬": "子",
    "癸": "申",
}

MUNGOK_GWIIN_TARGET_BY_DAY_STEM = {
    "甲": "亥",
    "乙": "子",
    "丙": "寅",
    "丁": "卯",
    "戊": "寅",
    "己": "卯",
    "庚": "巳",
    "辛": "午",
    "壬": "申",
    "癸": "酉",
}

GWAEGANG_DAY_PILLARS = ["庚辰", "庚戌", "壬辰", "戊戌"]
BAEKHO_CLASSIC_DAY_PILLARS = ["庚午", "庚寅", "庚戌", "辛巳", "辛卯", "辛未"]
BAEKHO_MODERN_KR_DAY_PILLARS = ["甲辰", "乙未", "丙戌", "丁丑", "戊辰", "壬戌", "癸丑"]

HYEONCHIM_STEMS = {"甲", "辛"}
HYEONCHIM_BRANCHES = {"卯", "午", "申"}

WONJIN_BRANCH_PAIRS = {
    frozenset(("辰", "亥")),
    frozenset(("午", "丑")),
    frozenset(("巳", "戌")),
    frozenset(("卯", "申")),
    frozenset(("寅", "酉")),
    frozenset(("子", "未")),
}

GWIMUNGWAN_BRANCH_PAIRS = {
    frozenset(("辰", "亥")),
    frozenset(("午", "丑")),
    frozenset(("巳", "戌")),
    frozenset(("卯", "申")),
    frozenset(("寅", "未")),
    frozenset(("子", "酉")),
}

BRANCH_SET = {
    "子",
    "丑",
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
}

PREVIOUS_BRANCH_BY_BRANCH = {
    "子": "亥",
    "丑": "子",
    "寅": "丑",
    "卯": "寅",
    "辰": "卯",
    "巳": "辰",
    "午": "巳",
    "未": "午",
    "申": "未",
    "酉": "申",
    "戌": "酉",
    "亥": "戌",
}

WANGJI_DOHWA_BRANCHES = ("子", "午", "卯", "酉")

MOKYOK_DOHWA_TARGET_BY_DAY_STEM = {
    "甲": "子",
    "乙": "巳",
    "丙": "卯",
    "丁": "申",
    "戊": "卯",
    "己": "申",
    "庚": "午",
    "辛": "亥",
    "壬": "酉",
    "癸": "寅",
}


def _make_metadata(
    *,
    key: str,
    family: str,
    label: str,
    category: StarCategory,
    tier: StarTier,
    method_id: str,
    basis_key: str,
    basis: str,
    usage_summary: str,
    usage_keywords: Tuple[str, ...],
    note: Optional[str] = None,
) -> StarMetadata:
    return StarMetadata(
        key=key,
        family=family,
        label=label,
        category=category,
        tier=tier,
        scope={"S": "core", "A": "expanded", "B": "optional"}[tier],
        weight=TIER_WEIGHT[tier],
        method_id=method_id,
        basis_key=basis_key,
        basis=basis,
        usage_summary=usage_summary,
        usage_keywords=usage_keywords,
        note=note,
    )


def _build_match(
    *,
    pillar_key: VisiblePillarKey,
    pillar: PillarData,
    matched_field: MatchField,
    matched_value: str,
    counterpart_key: Optional[VisiblePillarKey] = None,
    counterpart_pillar: Optional[PillarData] = None,
) -> ManseSpecialStarMatch:
    return ManseSpecialStarMatch(
        pillar_key=pillar_key,
        pillar_label=PILLAR_LABELS[pillar_key],
        gan_zhi=pillar.gan_zhi,
        stem=pillar.stem,
        branch=pillar.branch,
        matched_field=matched_field,
        matched_value=matched_value,
        counterpart_pillar_key=counterpart_key,
        counterpart_pillar_label=PILLAR_LABELS[counterpart_key] if counterpart_key else None,
        counterpart_gan_zhi=counterpart_pillar.gan_zhi if counterpart_pillar else None,
        counterpart_branch=counterpart_pillar.branch if counterpart_pillar else None,
    )


def _build_star(
    *,
    metadata: StarMetadata,
    anchor_value: str,
    target_values: Iterable[str],
    matches: List[ManseSpecialStarMatch],
) -> ManseSpecialStar:
    target_list = [value for value in target_values if value]
    return ManseSpecialStar(
        key=metadata.key,
        family=metadata.family,
        label=metadata.label,
        category=metadata.category,
        tier=metadata.tier,
        scope=metadata.scope,
        weight=metadata.weight,
        method_id=metadata.method_id,
        basis_key=metadata.basis_key,
        basis=metadata.basis,
        anchor_value=anchor_value,
        target_values=target_list,
        usage_summary=metadata.usage_summary,
        usage_keywords=list(metadata.usage_keywords),
        note=metadata.note,
        active=bool(matches),
        count=len(matches),
        matches=matches,
    )


def _collect_stem_matches(
    *,
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
    target_stems: Iterable[str],
    excluded_pillar_keys: Sequence[VisiblePillarKey] = (),
) -> List[ManseSpecialStarMatch]:
    target_set = set(target_stems)
    excluded_set = set(excluded_pillar_keys)
    matches: List[ManseSpecialStarMatch] = []
    for pillar_key in visible_pillar_keys:
        if pillar_key in excluded_set:
            continue
        pillar = pillars[pillar_key]
        if pillar.stem in target_set:
            matches.append(
                _build_match(
                    pillar_key=pillar_key,
                    pillar=pillar,
                    matched_field="stem",
                    matched_value=pillar.stem,
                )
            )
    return matches


def _collect_branch_matches(
    *,
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
    target_branches: Iterable[str],
    excluded_pillar_keys: Sequence[VisiblePillarKey] = (),
) -> List[ManseSpecialStarMatch]:
    target_set = set(target_branches)
    excluded_set = set(excluded_pillar_keys)
    matches: List[ManseSpecialStarMatch] = []
    for pillar_key in visible_pillar_keys:
        if pillar_key in excluded_set:
            continue
        pillar = pillars[pillar_key]
        if pillar.branch in target_set:
            matches.append(
                _build_match(
                    pillar_key=pillar_key,
                    pillar=pillar,
                    matched_field="branch",
                    matched_value=pillar.branch,
                )
            )
    return matches


def _collect_gan_zhi_matches(
    *,
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
    target_gan_zhi_values: Iterable[str],
    excluded_pillar_keys: Sequence[VisiblePillarKey] = (),
) -> List[ManseSpecialStarMatch]:
    target_set = set(target_gan_zhi_values)
    excluded_set = set(excluded_pillar_keys)
    matches: List[ManseSpecialStarMatch] = []
    for pillar_key in visible_pillar_keys:
        if pillar_key in excluded_set:
            continue
        pillar = pillars[pillar_key]
        if pillar.gan_zhi in target_set:
            matches.append(
                _build_match(
                    pillar_key=pillar_key,
                    pillar=pillar,
                    matched_field="gan_zhi",
                    matched_value=pillar.gan_zhi,
                )
            )
    return matches


def _collect_pair_matches(
    *,
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
    pair_set: Iterable[frozenset[str]],
    require_day_pillar: bool = False,
) -> List[ManseSpecialStarMatch]:
    allowed_pairs = set(pair_set)
    matches: List[ManseSpecialStarMatch] = []
    for left_key, right_key in combinations(visible_pillar_keys, 2):
        if require_day_pillar and "day" not in {left_key, right_key}:
            continue
        left_pillar = pillars[left_key]
        right_pillar = pillars[right_key]
        if frozenset((left_pillar.branch, right_pillar.branch)) not in allowed_pairs:
            continue
        matches.append(
            _build_match(
                pillar_key=left_key,
                pillar=left_pillar,
                matched_field="pair",
                matched_value=left_pillar.branch,
                counterpart_key=right_key,
                counterpart_pillar=right_pillar,
            )
        )
        matches.append(
            _build_match(
                pillar_key=right_key,
                pillar=right_pillar,
                matched_field="pair",
                matched_value=right_pillar.branch,
                counterpart_key=left_key,
                counterpart_pillar=left_pillar,
            )
        )
    return matches


def _parse_xun_kong_branches(value: str) -> List[str]:
    return [char for char in value if char in BRANCH_SET]


def _filter_matches_by_pillar_keys(
    matches: Sequence[ManseSpecialStarMatch],
    allowed_pillar_keys: Iterable[VisiblePillarKey],
) -> List[ManseSpecialStarMatch]:
    allowed_set = set(allowed_pillar_keys)
    return [match for match in matches if match.pillar_key in allowed_set]


def _build_direct_lookup_star(
    *,
    metadata: StarMetadata,
    anchor_value: str,
    target_values: Iterable[str],
    match_mode: Literal["stem", "branch", "gan_zhi"],
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
    excluded_pillar_keys: Sequence[VisiblePillarKey] = (),
) -> ManseSpecialStar:
    if match_mode == "stem":
        matches = _collect_stem_matches(
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
            target_stems=target_values,
            excluded_pillar_keys=excluded_pillar_keys,
        )
    elif match_mode == "branch":
        matches = _collect_branch_matches(
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
            target_branches=target_values,
            excluded_pillar_keys=excluded_pillar_keys,
        )
    else:
        matches = _collect_gan_zhi_matches(
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
            target_gan_zhi_values=target_values,
            excluded_pillar_keys=excluded_pillar_keys,
        )
    return _build_star(
        metadata=metadata,
        anchor_value=anchor_value,
        target_values=target_values,
        matches=matches,
    )


def _append_branch_group_star_variants(
    *,
    stars: List[ManseSpecialStar],
    family: str,
    label: str,
    category: StarCategory,
    tier: StarTier,
    usage_summary: str,
    usage_keywords: Tuple[str, ...],
    target_by_group: Dict[str, str],
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
) -> None:
    for anchor_key, basis_label in [("year", "연지 기준"), ("day", "일지 기준")]:
        anchor_branch = pillars[anchor_key].branch
        group_key = TRIAD_GROUP_BY_BRANCH.get(anchor_branch)
        if not group_key:
            continue
        target_branch = target_by_group[group_key]
        metadata = _make_metadata(
            key=f"{family}-{anchor_key}-branch",
            family=family,
            label=label,
            category=category,
            tier=tier,
            method_id=f"triad-{family}-{anchor_key}-branch",
            basis_key=f"{anchor_key}_branch",
            basis=basis_label,
            usage_summary=usage_summary,
            usage_keywords=usage_keywords,
        )
        stars.append(
            _build_direct_lookup_star(
                metadata=metadata,
                anchor_value=anchor_branch,
                target_values=[target_branch],
                match_mode="branch",
                pillars=pillars,
                visible_pillar_keys=visible_pillar_keys,
            )
        )


def _append_seasonal_branch_star_variants(
    *,
    stars: List[ManseSpecialStar],
    family: str,
    label: str,
    usage_summary: str,
    usage_keywords: Tuple[str, ...],
    target_by_group: Dict[str, str],
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
) -> None:
    for anchor_key, basis_label in [("year", "연지 기준"), ("day", "일지 기준")]:
        anchor_branch = pillars[anchor_key].branch
        group_key = SEASONAL_GROUP_BY_BRANCH.get(anchor_branch)
        if not group_key:
            continue
        target_branch = target_by_group[group_key]
        metadata = _make_metadata(
            key=f"{family}-{anchor_key}-branch",
            family=family,
            label=label,
            category="sinsal",
            tier="A",
            method_id=f"seasonal-group-{family}-{anchor_key}-branch",
            basis_key=f"{anchor_key}_branch",
            basis=basis_label,
            usage_summary=usage_summary,
            usage_keywords=usage_keywords,
        )
        stars.append(
            _build_direct_lookup_star(
                metadata=metadata,
                anchor_value=anchor_branch,
                target_values=[target_branch],
                match_mode="branch",
                pillars=pillars,
                visible_pillar_keys=visible_pillar_keys,
            )
        )


def build_special_stars(
    *,
    pillars: Dict[str, PillarData],
    visible_pillar_keys: Sequence[VisiblePillarKey],
) -> List[ManseSpecialStar]:
    day_stem = pillars["day"].stem
    day_branch = pillars["day"].branch
    day_gan_zhi = pillars["day"].gan_zhi
    month_branch = pillars["month"].branch
    year_branch = pillars["year"].branch
    month_group = TRIAD_GROUP_BY_BRANCH.get(month_branch)

    stars: List[ManseSpecialStar] = []

    cheoneul_targets = CHEONEUL_GWIIN_TARGETS_BY_DAY_STEM.get(day_stem, [])
    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="cheoneul-gwiin",
                family="cheoneul-gwiin",
                label="천을귀인",
                category="auspicious",
                tier="S",
                method_id="day-stem-fixed-table",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="보호, 귀인 도움, 위기 완화 보조 지표로 사용합니다.",
                usage_keywords=("귀인", "보호", "완화", "회복"),
            ),
            anchor_value=day_stem,
            target_values=cheoneul_targets,
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    woldeok_targets = [WOLDEOK_GWIIN_TARGET_BY_MONTH_GROUP[month_group]] if month_group else []
    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="woldeok-gwiin",
                family="woldeok-gwiin",
                label="월덕귀인",
                category="auspicious",
                tier="S",
                method_id="month-branch-samhap-group",
                basis_key="month_branch",
                basis="월지 기준",
                usage_summary="덕성, 회복력, 흉의 완화 경향을 볼 때 사용합니다.",
                usage_keywords=("덕성", "회복력", "완화", "안정"),
            ),
            anchor_value=month_branch,
            target_values=woldeok_targets,
            match_mode="stem",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="munchang-gwiin",
                family="munchang-gwiin",
                label="문창귀인",
                category="auspicious",
                tier="S",
                method_id="day-stem-fixed-table",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="학문, 글쓰기, 시험, 연구, 문예 역량 보조 지표로 사용합니다.",
                usage_keywords=("학문", "문장", "시험", "연구", "표현"),
            ),
            anchor_value=day_stem,
            target_values=[MUNCHANG_GWIIN_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="taegeuk-gwiin",
                family="taegeuk-gwiin",
                label="태극귀인",
                category="auspicious",
                tier="S",
                method_id="day-stem-fixed-table",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="정신성, 학문, 자격, 명예 보조 지표로 사용합니다.",
                usage_keywords=("정신성", "학문", "자격", "명예"),
            ),
            anchor_value=day_stem,
            target_values=TAEGEUK_GWIIN_TARGETS_BY_DAY_STEM.get(day_stem, []),
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="hakdang",
                family="gwangwi-hakgwan",
                label="학당",
                category="auspicious",
                tier="S",
                method_id="day-stem-changsheng",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="학업, 자격시험, 문서 역량을 볼 때 사용하는 학당 계열 길성입니다.",
                usage_keywords=("학업", "자격시험", "문서", "성취"),
            ),
            anchor_value=day_stem,
            target_values=[HAKDANG_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="sagwan",
                family="gwangwi-hakgwan",
                label="사관",
                category="auspicious",
                tier="S",
                method_id="day-stem-linguan",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="관직, 커리어, 전문직, 문서 실무 적합성 보조 지표로 사용합니다.",
                usage_keywords=("관직", "커리어", "전문직", "문서"),
            ),
            anchor_value=day_stem,
            target_values=[SAGWAN_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    hamji_dohwa_stars: List[ManseSpecialStar] = []
    for anchor_key, basis_label in [("year", "연지 기준"), ("day", "일지 기준")]:
        anchor_branch = pillars[anchor_key].branch
        group_key = TRIAD_GROUP_BY_BRANCH.get(anchor_branch)
        if not group_key:
            continue
        target_branch = BRANCH_GROUP_TARGETS["dohwa"][group_key]
        hamji_star = _build_direct_lookup_star(
            metadata=_make_metadata(
                key=f"dohwa-{anchor_key}-branch",
                family="dohwa",
                label="함지도화",
                category="sinsal",
                tier="S",
                method_id=f"triad-dohwa-{anchor_key}-branch",
                basis_key=f"{anchor_key}_branch",
                basis=basis_label,
                usage_summary="정식 도화살(함지)로, 연애운, 이성운, 인기, 매력, 대중성 해석의 핵심 보조 지표로 사용합니다.",
                usage_keywords=("함지", "연애", "매력", "인기", "대중성"),
                note="실무에서 가장 먼저 보는 기본 도화 규칙입니다.",
            ),
            anchor_value=anchor_branch,
            target_values=[target_branch],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
        hamji_dohwa_stars.append(hamji_star)
        stars.append(hamji_star)

    hamji_dohwa_matches = [
        match
        for star in hamji_dohwa_stars
        for match in star.matches
    ]

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="wangji-dohwa",
                family="dohwa-extended",
                label="왕지도화",
                category="sinsal",
                tier="B",
                method_id="visible-wangji-branch-common-kr",
                basis_key="visible_branch",
                basis="가시 지지 기준",
                usage_summary="자오묘유 왕지 자체의 주목성·매력성을 보는 넓은 의미의 도화 보조 지표입니다.",
                usage_keywords=("왕지", "가도화", "주목", "매력"),
                note="실무에서는 가도화로 함께 부르기도 하며, 함지도화와는 별도로 취급합니다.",
            ),
            anchor_value="자오묘유",
            target_values=WANGJI_DOHWA_BRANCHES,
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="mokyok-dohwa",
                family="dohwa-extended",
                label="목욕도화",
                category="sinsal",
                tier="A",
                method_id="day-stem-mokyok-branch",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="감수성, 꾸밈, 애정 욕구, 미적 성향, 방종성 해석에 쓰는 도화 계열 보조 지표입니다.",
                usage_keywords=("목욕", "감수성", "꾸밈", "애정", "미감"),
                note="일간의 12운성 목욕지에 해당하는 지지가 사주에 있을 때 성립합니다.",
            ),
            anchor_value=day_stem,
            target_values=[MOKYOK_DOHWA_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_star(
            metadata=_make_metadata(
                key="byeongnae-dohwa",
                family="dohwa-location",
                label="벽내도화",
                category="sinsal",
                tier="B",
                method_id="hamji-location-year-month-common-kr",
                basis_key="hamji_match_location",
                basis="함지도화 위치",
                usage_summary="함지도화가 년지 또는 월지에 놓였을 때 관계가 비교적 안쪽으로 수렴하는 경향을 보는 위치 태그입니다.",
                usage_keywords=("벽내", "도화위치", "관계", "안정"),
                note="독립 신살이라기보다 함지도화의 위치 해석 태그입니다.",
            ),
            anchor_value="함지도화",
            target_values=["년지", "월지"],
            matches=_filter_matches_by_pillar_keys(hamji_dohwa_matches, ("year", "month")),
        )
    )

    stars.append(
        _build_star(
            metadata=_make_metadata(
                key="byeokoe-dohwa",
                family="dohwa-location",
                label="벽외도화",
                category="sinsal",
                tier="B",
                method_id="hamji-location-time-common-kr",
                basis_key="hamji_match_location",
                basis="함지도화 위치",
                usage_summary="함지도화가 시지에 놓였을 때 관계가 비교적 바깥으로 드러나는 경향을 보는 위치 태그입니다.",
                usage_keywords=("벽외", "도화위치", "표현", "외향"),
                note="독립 신살이라기보다 함지도화의 위치 해석 태그입니다.",
            ),
            anchor_value="함지도화",
            target_values=["시지"],
            matches=_filter_matches_by_pillar_keys(hamji_dohwa_matches, ("time",)),
        )
    )

    _append_branch_group_star_variants(
        stars=stars,
        family="yeokma",
        label="역마",
        category="sinsal",
        tier="S",
        usage_summary="이동, 출장, 이직, 해외, 변동성 보조 지표로 사용합니다.",
        usage_keywords=("이동", "출장", "이직", "해외", "변동"),
        target_by_group=BRANCH_GROUP_TARGETS["yeokma"],
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
    )
    _append_branch_group_star_variants(
        stars=stars,
        family="hwagae",
        label="화개",
        category="sinsal",
        tier="S",
        usage_summary="예술, 종교, 철학, 몰입, 고독 성향 보조 지표로 사용합니다.",
        usage_keywords=("예술", "종교", "철학", "몰입", "고독"),
        target_by_group=BRANCH_GROUP_TARGETS["hwagae"],
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
    )
    _append_branch_group_star_variants(
        stars=stars,
        family="jangseong",
        label="장성",
        category="sinsal",
        tier="S",
        usage_summary="리더십, 권한, 조직 주도성, 존재감 보조 지표로 사용합니다.",
        usage_keywords=("리더십", "권한", "조직", "주도성", "존재감"),
        target_by_group=BRANCH_GROUP_TARGETS["jangseong"],
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="yangin",
                family="yangin",
                label="양인",
                category="sinsal",
                tier="S",
                method_id="day-stem-yangren-fixed-table",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="강한 추진, 결단, 압박, 힘의 과잉 성향 보조 지표로 사용합니다.",
                usage_keywords=("추진", "결단", "압박", "강성"),
            ),
            anchor_value=day_stem,
            target_values=[YANGIN_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    gongmang_targets = _parse_xun_kong_branches(pillars["day"].xun_kong)
    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="gongmang",
                family="gongmang",
                label="공망",
                category="sinsal",
                tier="S",
                method_id="day-pillar-xunkong",
                basis_key="day_pillar",
                basis="일주 기준",
                usage_summary="공백, 지연, 체감 불일치, 효력 약화 보조 지표로 사용합니다.",
                usage_keywords=("공백", "지연", "허무", "약화"),
            ),
            anchor_value=day_gan_zhi,
            target_values=gongmang_targets,
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
            excluded_pillar_keys=["day"],
        )
    )

    gwaegang_active = day_gan_zhi in GWAEGANG_DAY_PILLARS
    stars.append(
        _build_star(
            metadata=_make_metadata(
                key="gwaegang",
                family="gwaegang",
                label="괴강",
                category="sinsal",
                tier="S",
                method_id="day-pillar-classic4",
                basis_key="day_pillar",
                basis="일주 기준",
                usage_summary="강성, 권력성, 결단력, 사건성 보조 지표로 사용합니다.",
                usage_keywords=("강성", "권력", "결단", "사건성"),
            ),
            anchor_value=day_gan_zhi,
            target_values=GWAEGANG_DAY_PILLARS,
            matches=[
                _build_match(
                    pillar_key="day",
                    pillar=pillars["day"],
                    matched_field="gan_zhi",
                    matched_value=day_gan_zhi,
                )
            ]
            if gwaegang_active
            else [],
        )
    )

    cheondeok_target = CHEONDEOK_GWIIN_TARGET_BY_MONTH_BRANCH.get(month_branch, "")
    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="cheondeok-gwiin",
                family="cheondeok-gwiin",
                label="천덕귀인",
                category="auspicious",
                tier="A",
                method_id="month-branch-trigram-conversion-common-kr",
                basis_key="month_branch",
                basis="월지 기준",
                usage_summary="흉 완화, 덕성, 사고 회피 보조 지표로 사용합니다.",
                usage_keywords=("완화", "덕성", "보호", "회피"),
                note="坤·乾·艮·巽을 申·亥·寅·巳로 바꿔 쓰는 common_kr 변환을 사용합니다.",
            ),
            anchor_value=month_branch,
            target_values=[cheondeok_target],
            match_mode="stem" if cheondeok_target not in BRANCH_SET else "branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    hyeonchim_matches: List[ManseSpecialStarMatch] = []
    sharp_stem_matches = _collect_stem_matches(
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
        target_stems=HYEONCHIM_STEMS,
    )
    sharp_branch_matches = _collect_branch_matches(
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
        target_branches=HYEONCHIM_BRANCHES,
    )
    if sharp_stem_matches and sharp_branch_matches:
        hyeonchim_matches = sharp_stem_matches + sharp_branch_matches

    stars.append(
        _build_star(
            metadata=_make_metadata(
                key="hyeonchim",
                family="hyeonchim",
                label="현침살",
                category="sinsal",
                tier="A",
                method_id="sharp-symbol-pattern-common-kr",
                basis_key="pattern",
                basis="패턴 기준",
                usage_summary="사건성, 예민성, 날카로움 보조 지표로 사용합니다.",
                usage_keywords=("사건성", "예민", "날카로움"),
                note="甲·辛과 卯·午·申 계열이 함께 드러날 때 활성화하는 보수적 패턴 규칙입니다.",
            ),
            anchor_value="甲辛 / 卯午申",
            target_values=["甲", "辛", "卯", "午", "申"],
            matches=hyeonchim_matches,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="baekho-daesal-classic",
                family="baekho-daesal",
                label="백호대살",
                category="sinsal",
                tier="A",
                method_id="day-pillar-classic",
                basis_key="day_pillar",
                basis="일주 기준",
                usage_summary="상해, 수술, 급격한 사건성 보조 지표로 사용합니다.",
                usage_keywords=("상해", "수술", "사건성", "급변"),
                note="고전형 일주 표를 별도 method_id로 유지합니다.",
            ),
            anchor_value=day_gan_zhi,
            target_values=BAEKHO_CLASSIC_DAY_PILLARS,
            match_mode="gan_zhi",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
            excluded_pillar_keys=["year", "month", "time"],
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="baekho-daesal-modern-kr",
                family="baekho-daesal",
                label="백호대살",
                category="sinsal",
                tier="A",
                method_id="day-pillar-modern-kr",
                basis_key="day_pillar",
                basis="일주 기준",
                usage_summary="상해, 수술, 급격한 사건성 보조 지표로 사용합니다.",
                usage_keywords=("상해", "수술", "사건성", "급변"),
                note="현대 한국 실무형 일주 표를 별도 method_id로 유지합니다.",
            ),
            anchor_value=day_gan_zhi,
            target_values=BAEKHO_MODERN_KR_DAY_PILLARS,
            match_mode="gan_zhi",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
            excluded_pillar_keys=["year", "month", "time"],
        )
    )

    _append_seasonal_branch_star_variants(
        stars=stars,
        family="gojin",
        label="고진",
        usage_summary="관계의 고독, 독립성, 정서적 거리감 보조 지표로 사용합니다.",
        usage_keywords=("고독", "독립성", "거리감"),
        target_by_group=SEASONAL_BRANCH_TARGETS["gojin"],
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
    )
    _append_seasonal_branch_star_variants(
        stars=stars,
        family="guasuk",
        label="과숙",
        usage_summary="관계의 고독, 결혼·연애의 거리감 보조 지표로 사용합니다.",
        usage_keywords=("고독", "관계", "거리감"),
        target_by_group=SEASONAL_BRANCH_TARGETS["guasuk"],
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
    )

    wonjin_matches = _collect_pair_matches(
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
        pair_set=WONJIN_BRANCH_PAIRS,
    )
    stars.append(
        _build_star(
            metadata=_make_metadata(
                key="wonjin",
                family="wonjin",
                label="원진",
                category="sinsal",
                tier="A",
                method_id="visible-branch-pair-common-kr",
                basis_key="visible_branch_pair",
                basis="가시 지지 조합",
                usage_summary="관계 갈등, 섭섭함, 감정 앙금 보조 지표로 사용합니다.",
                usage_keywords=("갈등", "섭섭함", "앙금", "관계"),
                note="한국 실무 common pair 표를 사용합니다.",
            ),
            anchor_value="가시 지지 조합",
            target_values=["辰亥", "午丑", "巳戌", "卯申", "寅酉", "子未"],
            matches=wonjin_matches,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="hongyeom",
                family="hongyeom",
                label="홍염도화",
                category="sinsal",
                tier="A",
                method_id="day-stem-common-kr",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="강한 이성 매력, 감정적 끌림, 꾸밈 성향을 보는 도화 계열 보조 지표로 사용합니다.",
                usage_keywords=("홍염", "도화", "매력", "이성", "대중성"),
                note="함지도화와는 별개로 보되, 실무에서는 도화 계열 확장 항목으로 함께 해석합니다.",
            ),
            anchor_value=day_stem,
            target_values=[HONGYEOM_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="munguok-gwiin",
                family="munguok-gwiin",
                label="문곡귀인",
                category="auspicious",
                tier="B",
                method_id="day-stem-common-kr",
                basis_key="day_stem",
                basis="일간 기준",
                usage_summary="문학, 인문학, 예술, 종교 감수성 보조 지표로 사용합니다.",
                usage_keywords=("문학", "인문학", "예술", "종교"),
            ),
            anchor_value=day_stem,
            target_values=[MUNGOK_GWIIN_TARGET_BY_DAY_STEM.get(day_stem, "")],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    cheonmun_target = PREVIOUS_BRANCH_BY_BRANCH.get(month_branch, "")
    stars.append(
        _build_direct_lookup_star(
            metadata=_make_metadata(
                key="cheonmun-seong",
                family="cheonmun-seong",
                label="천문성",
                category="auspicious",
                tier="B",
                method_id="month-prev-branch-common-kr",
                basis_key="month_branch",
                basis="월지 기준",
                usage_summary="학문, 연구, 분석, 철학, 종교, 상담 같은 정신성·몰입형 적성 해석의 보조 지표로 사용합니다.",
                usage_keywords=("학문", "연구", "분석", "철학", "종교", "상담"),
                note="일부 실무에서는 천의성과 같은 계열로 함께 해석하는 보조 규칙입니다.",
            ),
            anchor_value=month_branch,
            target_values=[cheonmun_target],
            match_mode="branch",
            pillars=pillars,
            visible_pillar_keys=visible_pillar_keys,
        )
    )

    gwimungwan_matches = _collect_pair_matches(
        pillars=pillars,
        visible_pillar_keys=visible_pillar_keys,
        pair_set=GWIMUNGWAN_BRANCH_PAIRS,
        require_day_pillar=True,
    )
    stars.append(
        _build_star(
            metadata=_make_metadata(
                key="gwimungwan",
                family="gwimungwan",
                label="귀문관",
                category="sinsal",
                tier="B",
                method_id="day-branch-pair-common-kr",
                basis_key="day_branch_visible_pair",
                basis="일지와 가시 지지 조합",
                usage_summary="직관, 집착, 몰입, 심리 예민성 보조 지표로 사용합니다.",
                usage_keywords=("직관", "집착", "몰입", "예민성"),
                note="일지를 중심으로 월지·시지 등 가시 지지와의 pair를 우선 조회합니다.",
            ),
            anchor_value=day_branch,
            target_values=["辰亥", "午丑", "巳戌", "卯申", "寅未", "子酉"],
            matches=gwimungwan_matches,
        )
    )

    return stars
