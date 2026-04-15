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
) -> SajuCalculationResult:
    """등록된 사주 엔진을 호출해 계산 결과를 반환한다."""
    return ENGINE.calculate(
        corrected_solar_datetime=corrected_solar_datetime,
        gender=gender,
        tzid=tzid,
    )
