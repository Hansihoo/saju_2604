"""이 파일은 양력과 음력 입력을 공통 계산 형식으로 정규화한다."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Literal, Optional

from korean_lunar_calendar import KoreanLunarCalendar

from app.domain.saju.reference_calendar import (
    LunarReferenceRecord,
    lookup_lunar_reference_by_lunar_date,
    lookup_lunar_reference_by_solar_date,
)


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


def _format_solar_datetime(calendar: KoreanLunarCalendar, *, hour: int, minute: int) -> str:
    """양력 시각을 포맷한다."""
    return f"{calendar.solarYear:04d}-{calendar.solarMonth:02d}-{calendar.solarDay:02d} {hour:02d}:{minute:02d}:00"


def _format_lunar_datetime(calendar: KoreanLunarCalendar, *, hour: int, minute: int) -> str:
    """음력 시각을 포맷한다."""
    return f"{calendar.lunarYear:04d}-{calendar.lunarMonth:02d}-{calendar.lunarDay:02d} {hour:02d}:{minute:02d}:00"


def _result_from_reference_record(
    *,
    calendar_type: CalendarType,
    input_date: str,
    input_time: str,
    record: LunarReferenceRecord,
    hour: int,
    minute: int,
) -> CalendarNormalizationResult:
    return CalendarNormalizationResult(
        calendar_type=calendar_type,
        is_lunar_leap_month=record.is_lunar_leap_month,
        input_date=input_date,
        input_time=input_time,
        normalized_solar_datetime=(
            f"{record.solar_year:04d}-{record.solar_month:02d}-{record.solar_day:02d} "
            f"{hour:02d}:{minute:02d}:00"
        ),
        normalized_lunar_datetime=(
            f"{record.lunar_year:04d}-{record.lunar_month:02d}-{record.lunar_day:02d} "
            f"{hour:02d}:{minute:02d}:00"
        ),
        solar_year=record.solar_year,
        solar_month=record.solar_month,
        solar_day=record.solar_day,
        solar_hour=hour,
        solar_minute=minute,
        lunar_year=record.lunar_year,
        lunar_month=record.lunar_month,
        lunar_day=record.lunar_day,
    )


def _set_solar_date(calendar: KoreanLunarCalendar, *, year: int, month: int, day: int) -> None:
    if calendar.setSolarDate(year, month, day):
        return
    raise CalendarNormalizationError(
        error_code="UNSUPPORTED_SOLAR_DATE",
        message="The solar date is outside the supported Korean lunar calendar range.",
        meta={"birth_date": f"{year:04d}-{month:02d}-{day:02d}"},
    )


def _set_lunar_date(
    calendar: KoreanLunarCalendar,
    *,
    year: int,
    month: int,
    day: int,
    is_lunar_leap_month: bool,
) -> None:
    if calendar.setLunarDate(year, month, day, is_lunar_leap_month):
        return
    raise CalendarNormalizationError(
        error_code="UNSUPPORTED_LUNAR_DATE",
        message="The lunar date is outside the supported Korean lunar calendar range.",
        meta={
            "birth_date": f"{year:04d}-{month:02d}-{day:02d}",
            "is_lunar_leap_month": is_lunar_leap_month,
        },
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

    if calendar_type == "solar":
        reference_record = lookup_lunar_reference_by_solar_date(birth_date)
    else:
        reference_record = lookup_lunar_reference_by_lunar_date(
            lunar_year=birth_date.year,
            lunar_month=birth_date.month,
            lunar_day=birth_date.day,
            is_lunar_leap_month=is_lunar_leap_month,
        )

    if reference_record is not None:
        return _result_from_reference_record(
            calendar_type=calendar_type,
            input_date=birth_date.isoformat(),
            input_time=birth_time,
            record=reference_record,
            hour=hour,
            minute=minute,
        )

    try:
        calendar = KoreanLunarCalendar()
        if calendar_type == "solar":
            _set_solar_date(
                calendar,
                year=birth_date.year,
                month=birth_date.month,
                day=birth_date.day,
            )
        else:
            _set_lunar_date(
                calendar,
                year=birth_date.year,
                month=birth_date.month,
                day=birth_date.day,
                is_lunar_leap_month=is_lunar_leap_month,
            )
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
        is_lunar_leap_month=bool(calendar.isIntercalation),
        input_date=birth_date.isoformat(),
        input_time=birth_time,
        normalized_solar_datetime=_format_solar_datetime(calendar, hour=hour, minute=minute),
        normalized_lunar_datetime=_format_lunar_datetime(calendar, hour=hour, minute=minute),
        solar_year=calendar.solarYear,
        solar_month=calendar.solarMonth,
        solar_day=calendar.solarDay,
        solar_hour=hour,
        solar_minute=minute,
        lunar_year=calendar.lunarYear,
        lunar_month=calendar.lunarMonth,
        lunar_day=calendar.lunarDay,
    )
