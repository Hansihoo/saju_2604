"""이 파일은 양력과 음력 입력을 공통 계산 형식으로 정규화한다."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Literal, Optional

from lunar_python import Lunar, Solar


CalendarType = Literal["solar", "lunar"]


class CalendarNormalizationError(ValueError):
    def __init__(self, *, error_code: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        """해당 오류 유형에 필요한 정보를 저장하도록 객체를 초기화한다."""
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.meta = meta or {}


@dataclass
class CalendarNormalizationResult:
    calendar_type: CalendarType
    is_lunar_leap_month: bool
    input_date: str
    input_time: str
    normalized_solar_datetime: str
    normalized_lunar_datetime: str
    solar_year: int
    solar_month: int
    solar_day: int
    solar_hour: int
    solar_minute: int
    lunar_year: int
    lunar_month: int
    lunar_day: int


def _format_lunar_datetime(lunar: Lunar) -> str:
    """음력 시각을 포맷한다."""
    return (
        f"{lunar.getYear():04d}-{abs(lunar.getMonth()):02d}-{lunar.getDay():02d} "
        f"{lunar.getHour():02d}:{lunar.getMinute():02d}:{lunar.getSecond():02d}"
    )


def normalize_calendar(
    *,
    calendar_type: CalendarType,
    birth_date: date,
    birth_time: str,
    is_lunar_leap_month: bool,
) -> CalendarNormalizationResult:
    """양력 또는 음력 입력을 공통 계산 형식으로 정규화한다."""
    try:
        hour_str, minute_str = birth_time.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError as exc:
        raise CalendarNormalizationError(
            error_code="INVALID_BIRTH_TIME",
            message="Birth time must use HH:mm format.",
            meta={"birth_time": birth_time},
        ) from exc

    try:
        if calendar_type == "solar":
            solar = Solar.fromYmdHms(
                birth_date.year,
                birth_date.month,
                birth_date.day,
                hour,
                minute,
                0,
            )
            lunar = solar.getLunar()
        else:
            lunar_month = -birth_date.month if is_lunar_leap_month else birth_date.month
            lunar = Lunar.fromYmdHms(
                birth_date.year,
                lunar_month,
                birth_date.day,
                hour,
                minute,
                0,
            )
            solar = lunar.getSolar()
    except Exception as exc:
        raise CalendarNormalizationError(
            error_code="CALENDAR_NORMALIZATION_ERROR",
            message="The calendar input could not be normalized.",
            meta={
                "calendar_type": calendar_type,
                "birth_date": birth_date.isoformat(),
                "birth_time": birth_time,
                "is_lunar_leap_month": is_lunar_leap_month,
            },
        ) from exc

    return CalendarNormalizationResult(
        calendar_type=calendar_type,
        is_lunar_leap_month=is_lunar_leap_month,
        input_date=birth_date.isoformat(),
        input_time=birth_time,
        normalized_solar_datetime=solar.toYmdHms(),
        normalized_lunar_datetime=_format_lunar_datetime(lunar),
        solar_year=solar.getYear(),
        solar_month=solar.getMonth(),
        solar_day=solar.getDay(),
        solar_hour=solar.getHour(),
        solar_minute=solar.getMinute(),
        lunar_year=lunar.getYear(),
        lunar_month=lunar.getMonth(),
        lunar_day=lunar.getDay(),
    )
