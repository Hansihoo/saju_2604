from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Dict, Optional, Tuple

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover - Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class TimeCorrectionError(ValueError):
    def __init__(self, *, error_code: str, message: str, meta: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.meta = meta or {}


@dataclass
class TimeCorrectionResult:
    tzid: str
    source_local_datetime: str
    normalized_local_datetime: str
    normalized_utc_datetime: str
    offset_minutes: int
    ambiguous: bool
    fold: int
    year: int
    month: int
    day: int
    hour: int
    minute: int


def _parse_birth_time(raw_time: str) -> time:
    try:
        hour_str, minute_str = raw_time.split(":")
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError as exc:
        raise TimeCorrectionError(
            error_code="INVALID_BIRTH_TIME",
            message="Birth time must use HH:mm format.",
            meta={"birth_time": raw_time},
        ) from exc

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise TimeCorrectionError(
            error_code="INVALID_BIRTH_TIME",
            message="Birth time must stay within 00:00 to 23:59.",
            meta={"birth_time": raw_time},
        )

    return time(hour=hour, minute=minute)


def _roundtrip_local(naive_local: datetime, zone: ZoneInfo, fold: int) -> Tuple[datetime, datetime]:
    aware_local = naive_local.replace(tzinfo=zone, fold=fold)
    utc_value = aware_local.astimezone(timezone.utc)
    local_roundtrip = utc_value.astimezone(zone).replace(tzinfo=None)
    return utc_value, local_roundtrip


def normalize_birth_datetime(*, birth_date: date, birth_time: str, tzid: str) -> TimeCorrectionResult:
    try:
        zone = ZoneInfo(tzid)
    except ZoneInfoNotFoundError as exc:
        raise TimeCorrectionError(
            error_code="INVALID_TIMEZONE",
            message="The selected timezone is not valid.",
            meta={"tzid": tzid},
        ) from exc

    parsed_time = _parse_birth_time(birth_time)
    naive_local = datetime.combine(birth_date, parsed_time)

    utc_fold0, roundtrip_fold0 = _roundtrip_local(naive_local, zone, 0)
    utc_fold1, roundtrip_fold1 = _roundtrip_local(naive_local, zone, 1)

    exists_fold0 = roundtrip_fold0 == naive_local
    exists_fold1 = roundtrip_fold1 == naive_local

    if not exists_fold0 and not exists_fold1:
        raise TimeCorrectionError(
            error_code="NON_EXISTENT_LOCAL_TIME",
            message="The local time does not exist in the selected timezone due to a DST transition.",
            meta={
                "tzid": tzid,
                "source_local_datetime": naive_local.isoformat(),
            },
        )

    ambiguous = exists_fold0 and exists_fold1 and utc_fold0 != utc_fold1
    chosen_fold = 1 if ambiguous else 0
    aware_local = naive_local.replace(tzinfo=zone, fold=chosen_fold)
    normalized_utc = aware_local.astimezone(timezone.utc)
    utcoffset = aware_local.utcoffset()
    offset_minutes = int((utcoffset.total_seconds() if utcoffset else 0) // 60)

    return TimeCorrectionResult(
        tzid=tzid,
        source_local_datetime=naive_local.isoformat(),
        normalized_local_datetime=aware_local.isoformat(),
        normalized_utc_datetime=normalized_utc.isoformat(),
        offset_minutes=offset_minutes,
        ambiguous=ambiguous,
        fold=chosen_fold,
        year=aware_local.year,
        month=aware_local.month,
        day=aware_local.day,
        hour=aware_local.hour,
        minute=aware_local.minute,
    )
