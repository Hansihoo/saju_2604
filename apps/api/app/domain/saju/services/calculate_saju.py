from app.domain.saju.adapters import LunarPythonSajuEngine
from app.domain.saju.engine import Gender, SajuCalculationResult


ENGINE = LunarPythonSajuEngine()


def calculate_saju(
    *,
    corrected_solar_datetime: str,
    gender: Gender,
) -> SajuCalculationResult:
    return ENGINE.calculate(
        corrected_solar_datetime=corrected_solar_datetime,
        gender=gender,
    )
