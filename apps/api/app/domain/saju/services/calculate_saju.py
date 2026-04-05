from app.domain.saju.adapters import LunarPythonSajuEngine
from app.domain.saju.calendar_normalization import CalendarNormalizationResult
from app.domain.saju.engine import Gender, SajuCalculationResult


ENGINE = LunarPythonSajuEngine()


def calculate_saju(
    *,
    calendar_normalization: CalendarNormalizationResult,
    gender: Gender,
) -> SajuCalculationResult:
    return ENGINE.calculate(
        normalized_solar_datetime=calendar_normalization.normalized_solar_datetime,
        gender=gender,
    )
