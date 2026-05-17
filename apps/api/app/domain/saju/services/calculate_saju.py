"""이 파일은 사주를 계산하는 로직을 담는다."""

from typing import Optional

from app.domain.saju.adapters import LunarPythonSajuEngine
from app.domain.saju.engine import Gender, SajuCalculationResult


ENGINE = LunarPythonSajuEngine()


def calculate_saju(
    *,
    corrected_solar_datetime: str,
    gender: Gender,
    tzid: Optional[str] = None,
    day_pillar_basis_datetime: Optional[str] = None,
    use_canonical_year_month_pillars: bool = False,
) -> SajuCalculationResult:
    """등록된 사주 엔진을 호출해 계산 결과를 반환한다."""
    return ENGINE.calculate(
        corrected_solar_datetime=corrected_solar_datetime,
        gender=gender,
        tzid=tzid,
        day_pillar_basis_datetime=day_pillar_basis_datetime,
        use_canonical_year_month_pillars=use_canonical_year_month_pillars,
    )
