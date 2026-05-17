"""Canonical year/month pillar shadow calculation using solar-term boundaries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from lunar_python.EightChar import EightChar
from lunar_python.util import LunarUtil

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo

from app.domain.saju.engine import PillarData
from app.domain.saju.services.solar_term_boundaries import (
    JIE_TERM_IDS_IN_MONTH_ORDER,
    SolarTermBoundary,
    find_jie_boundary_by_term,
    list_jie_boundaries_for_years,
)


STEMS = tuple(LunarUtil.GAN[1:])
BRANCHES = tuple(LunarUtil.ZHI[1:])
MONTH_BRANCH_INDEX_BY_TERM_ID = {
    "ipchun": 2,
    "gyeongchip": 3,
    "cheongmyeong": 4,
    "ipha": 5,
    "mangjong": 6,
    "soseo": 7,
    "ipchu": 8,
    "baengno": 9,
    "hallo": 10,
    "ipdong": 11,
    "daeseol": 0,
    "sohan": 1,
}
MONTH_OFFSET_BY_TERM_ID = {
    term_id: index for index, term_id in enumerate(JIE_TERM_IDS_IN_MONTH_ORDER)
}
CHANG_SHENG_OFFSET = getattr(EightChar, "_EightChar__CHANG_SHENG_OFFSET")


@dataclass(frozen=True)
class CanonicalYearMonthResult:
    year_pillar: Optional[PillarData]
    month_pillar: Optional[PillarData]
    context: Dict[str, object]


def _parse_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def _boundary_datetime(boundary: SolarTermBoundary) -> datetime:
    return _parse_datetime(boundary.datetime_text)


def _boundary_term_id(boundary: SolarTermBoundary) -> str:
    return str(boundary.reference.get("term_id", ""))


def _boundary_utc_text(boundary: SolarTermBoundary, timezone_id: str) -> str:
    local_dt = _boundary_datetime(boundary)
    zone = ZoneInfo(timezone_id)
    return local_dt.replace(tzinfo=zone).astimezone(timezone.utc).isoformat()


def _provider_source(boundary: Optional[SolarTermBoundary]) -> str:
    if boundary is None:
        return "UNAVAILABLE"
    if boundary.provider == "solar_term_reference_table":
        return "KASI"
    if boundary.provider == "skyfield":
        return "SKYFIELD"
    return "FALLBACK"


def year_ganzhi_for_saju_year(saju_year: int) -> str:
    offset = saju_year - 4
    stem = STEMS[offset % 10]
    branch = BRANCHES[offset % 12]
    return f"{stem}{branch}"


def month_ganzhi_for_year_stem(year_stem: str, term_id: str) -> str:
    if year_stem not in STEMS:
        raise ValueError(f"Unsupported year stem: {year_stem}")
    if term_id not in MONTH_OFFSET_BY_TERM_ID:
        raise ValueError(f"Unsupported Jie term id for month pillar: {term_id}")

    year_stem_index = STEMS.index(year_stem)
    first_stem_at_yin = ((year_stem_index % 5) * 2 + 2) % 10
    month_stem = STEMS[(first_stem_at_yin + MONTH_OFFSET_BY_TERM_ID[term_id]) % 10]
    month_branch = BRANCHES[MONTH_BRANCH_INDEX_BY_TERM_ID[term_id]]
    return f"{month_stem}{month_branch}"


def _xun(gan_zhi: str) -> str:
    return LunarUtil.getXun(gan_zhi) or ""


def _xun_kong(gan_zhi: str) -> str:
    return LunarUtil.getXunKong(gan_zhi) or ""


def _twelve_fortune(*, day_stem: str, branch: str) -> str:
    if day_stem not in STEMS or branch not in BRANCHES:
        return ""
    offset = CHANG_SHENG_OFFSET.get(day_stem)
    if offset is None:
        return ""
    branch_index = BRANCHES.index(branch)
    day_stem_index = STEMS.index(day_stem)
    index = offset + (branch_index if day_stem_index % 2 == 0 else -branch_index)
    return EightChar.CHANG_SHENG[index % 12]


def _build_pillar_from_ganzhi(*, gan_zhi: str, day_stem: str) -> PillarData:
    stem = gan_zhi[:1]
    branch = gan_zhi[1:]
    hidden_stems = list(LunarUtil.ZHI_HIDE_GAN.get(branch, []))
    branch_ten_gods = [
        LunarUtil.SHI_SHEN.get(f"{day_stem}{hidden_stem}", "")
        for hidden_stem in hidden_stems
    ]
    stem_five_element = LunarUtil.WU_XING_GAN.get(stem, "")
    branch_five_element = LunarUtil.WU_XING_ZHI.get(branch, "")
    return PillarData(
        gan_zhi=gan_zhi,
        stem=stem,
        branch=branch,
        stem_five_element=stem_five_element,
        branch_five_element=branch_five_element,
        five_elements=f"{stem_five_element}{branch_five_element}",
        stem_ten_god=LunarUtil.SHI_SHEN.get(f"{day_stem}{stem}", ""),
        branch_ten_god=branch_ten_gods[0] if branch_ten_gods else "",
        branch_ten_gods=branch_ten_gods,
        hidden_stems=hidden_stems,
        twelve_fortune=_twelve_fortune(day_stem=day_stem, branch=branch),
        na_yin=LunarUtil.NAYIN.get(gan_zhi, ""),
        xun=_xun(gan_zhi),
        xun_kong=_xun_kong(gan_zhi),
    )


def _latest_month_boundary(
    birth_dt: datetime,
    *,
    timezone_id: str,
) -> Optional[SolarTermBoundary]:
    boundaries = list_jie_boundaries_for_years(
        (birth_dt.year - 1, birth_dt.year, birth_dt.year + 1),
        timezone_id=timezone_id,
    )
    candidates = [
        boundary
        for boundary in boundaries
        if _boundary_term_id(boundary) in MONTH_OFFSET_BY_TERM_ID
        and _boundary_datetime(boundary) <= birth_dt
    ]
    if not candidates:
        return None
    return max(candidates, key=_boundary_datetime)


def calculate_canonical_year_month(
    *,
    basis_datetime_text: str,
    timezone_id: Optional[str],
    day_stem: str,
    legacy_year_pillar: str,
    legacy_month_pillar: str,
    apply_to_primary: bool,
) -> CanonicalYearMonthResult:
    tzid = timezone_id or "Asia/Seoul"
    birth_dt = _parse_datetime(basis_datetime_text)
    year_boundary = find_jie_boundary_by_term(
        birth_dt.year,
        "ipchun",
        timezone_id=tzid,
    )
    month_boundary = _latest_month_boundary(birth_dt, timezone_id=tzid)

    base_context: Dict[str, object] = {
        "enabled": bool(apply_to_primary),
        "selected_basis_datetime": basis_datetime_text,
        "timezone_id": tzid,
        "year_pillar_source": "LUNAR_PYTHON_LEGACY",
        "month_pillar_source": "LUNAR_PYTHON_LEGACY",
        "legacy_year_pillar": legacy_year_pillar,
        "legacy_month_pillar": legacy_month_pillar,
    }
    if year_boundary is None or month_boundary is None:
        base_context.update(
            {
                "available": False,
                "error": "solar_term_boundary_unavailable",
                "year_boundary_available": year_boundary is not None,
                "month_boundary_available": month_boundary is not None,
            }
        )
        return CanonicalYearMonthResult(None, None, base_context)

    year_boundary_dt = _boundary_datetime(year_boundary)
    month_boundary_dt = _boundary_datetime(month_boundary)
    saju_year = birth_dt.year if birth_dt >= year_boundary_dt else birth_dt.year - 1
    canonical_year_pillar = year_ganzhi_for_saju_year(saju_year)
    canonical_year_stem = canonical_year_pillar[:1]
    month_term_id = _boundary_term_id(month_boundary)
    canonical_month_pillar = month_ganzhi_for_year_stem(canonical_year_stem, month_term_id)
    year_changed = canonical_year_pillar != legacy_year_pillar
    month_changed = canonical_month_pillar != legacy_month_pillar
    exact_boundary_applied = birth_dt in {year_boundary_dt, month_boundary_dt}
    year_provider_source = _provider_source(year_boundary)
    month_provider_source = _provider_source(month_boundary)
    provider_source = (
        year_provider_source
        if year_provider_source == month_provider_source
        else "MIXED"
    )

    context = {
        **base_context,
        "available": True,
        "applied_to_primary": bool(apply_to_primary),
        "year_pillar_source": (
            "CANONICAL_SOLAR_TERM" if apply_to_primary else "LUNAR_PYTHON_LEGACY"
        ),
        "month_pillar_source": (
            "CANONICAL_SOLAR_TERM" if apply_to_primary else "LUNAR_PYTHON_LEGACY"
        ),
        "year_boundary_term": "ipchun",
        "year_boundary_datetime": year_boundary.datetime_text,
        "year_boundary_instant_utc": _boundary_utc_text(year_boundary, tzid),
        "year_boundary_provider": year_boundary.provider,
        "year_boundary_provider_source": year_provider_source,
        "month_boundary_term": month_term_id,
        "month_boundary_datetime": month_boundary.datetime_text,
        "month_boundary_instant_utc": _boundary_utc_text(month_boundary, tzid),
        "month_boundary_provider": month_boundary.provider,
        "month_boundary_provider_source": month_provider_source,
        "solar_term_provider_source": provider_source,
        "exact_boundary_applied": exact_boundary_applied,
        "saju_year": saju_year,
        "canonical_year_pillar": canonical_year_pillar,
        "canonical_month_pillar": canonical_month_pillar,
        "year_pillar_changed": year_changed,
        "month_pillar_changed": month_changed,
        "year_boundary_evidence": asdict(year_boundary),
        "month_boundary_evidence": asdict(month_boundary),
    }
    return CanonicalYearMonthResult(
        year_pillar=_build_pillar_from_ganzhi(
            gan_zhi=canonical_year_pillar,
            day_stem=day_stem,
        ),
        month_pillar=_build_pillar_from_ganzhi(
            gan_zhi=canonical_month_pillar,
            day_stem=day_stem,
        ),
        context=context,
    )
