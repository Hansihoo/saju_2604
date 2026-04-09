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
    return ENGINE.calculate(
        corrected_solar_datetime=corrected_solar_datetime,
        gender=gender,
        tzid=tzid,
    )
