"""이 파일은 대운 대운 목록를 계산하는 로직을 담는다."""

from __future__ import annotations

from datetime import datetime, timedelta
from math import floor
from typing import List, Literal

from lunar_python import Solar
from lunar_python.util import LunarUtil

from app.domain.saju.engine import Gender, LuckCycle
from app.domain.saju.services.solar_term_boundaries import find_adjacent_jie_boundary


LuckDirection = Literal["forward", "backward"]

YANG_STEMS = {"甲", "丙", "戊", "庚", "壬"}
SEXAGENARY_CYCLE = tuple(LunarUtil.JIA_ZI)
LUNAR_ENGINE_STANDARD_OFFSET_MINUTES = 480
TROPICAL_YEAR_DAYS = 365.2422
LUCK_CYCLE_YEAR_TO_DAY_FACTOR = 120.0


def is_yang_stem(stem: str) -> bool:
    """yang stem 여부를 판별한다."""
    return stem in YANG_STEMS


def get_luck_direction(year_stem: str, gender: Gender) -> LuckDirection:
    """대운 방향을 반환한다."""
    if (gender == "male" and is_yang_stem(year_stem)) or (
        gender == "female" and not is_yang_stem(year_stem)
    ):
        return "forward"
    return "backward"


def get_adjacent_month_boundary(
    normalized_birth_dt: datetime,
    direction: LuckDirection,
    target_standard_offset_minutes: int | None = None,
    timezone_id: str | None = None,
) -> datetime:
    """adjacent month 경계을 반환한다."""
    if timezone_id:
        reference_boundary = find_adjacent_jie_boundary(
            normalized_birth_dt,
            direction,
            timezone_id=timezone_id,
        )
        if reference_boundary is not None and reference_boundary.provider in {
            "solar_term_reference_table",
            "skyfield",
        }:
            return datetime.strptime(reference_boundary.datetime_text, "%Y-%m-%d %H:%M:%S")

    solar = Solar.fromYmdHms(
        normalized_birth_dt.year,
        normalized_birth_dt.month,
        normalized_birth_dt.day,
        normalized_birth_dt.hour,
        normalized_birth_dt.minute,
        normalized_birth_dt.second,
    )
    lunar = solar.getLunar()
    boundary = lunar.getNextJie() if direction == "forward" else lunar.getPrevJie()
    boundary_solar = boundary.getSolar()
    boundary_dt = datetime(
        boundary_solar.getYear(),
        boundary_solar.getMonth(),
        boundary_solar.getDay(),
        boundary_solar.getHour(),
        boundary_solar.getMinute(),
        boundary_solar.getSecond(),
    )
    if target_standard_offset_minutes is None:
        return boundary_dt

    offset_delta_minutes = target_standard_offset_minutes - LUNAR_ENGINE_STANDARD_OFFSET_MINUTES
    return boundary_dt + timedelta(minutes=offset_delta_minutes)


def get_display_start_age(
    birth_dt: datetime,
    boundary_dt: datetime,
    direction: LuckDirection,
) -> int:
    """표시용 start age을 반환한다."""
    del direction  # Kept to make the helper interface explicit for tests/debugging.
    delta_days = abs((boundary_dt - birth_dt).total_seconds()) / 86400
    precise_start_age_years = delta_days * LUCK_CYCLE_YEAR_TO_DAY_FACTOR / TROPICAL_YEAR_DAYS
    return floor(precise_start_age_years + 0.5)


def get_completed_age_months(birth_dt: datetime, target_dt: datetime) -> int:
    """Return completed age months without rounding."""
    total_months = (target_dt.year - birth_dt.year) * 12 + (target_dt.month - birth_dt.month)
    target_marker = (
        target_dt.day,
        target_dt.hour,
        target_dt.minute,
        target_dt.second,
        target_dt.microsecond,
    )
    birth_marker = (
        birth_dt.day,
        birth_dt.hour,
        birth_dt.minute,
        birth_dt.second,
        birth_dt.microsecond,
    )
    if target_marker < birth_marker:
        total_months -= 1
    return max(total_months, 0)


def get_age_year_month_components(total_months: int) -> tuple[int, int]:
    """Split completed age months into years and remaining months."""
    return total_months // 12, total_months % 12


def shift_ganzhi(pillar: str, steps: int) -> str:
    """ganzhi을 이동한다."""
    if pillar not in SEXAGENARY_CYCLE:
        raise ValueError(f"Unsupported pillar for sexagenary shift: {pillar}")
    index = SEXAGENARY_CYCLE.index(pillar)
    return SEXAGENARY_CYCLE[(index + steps) % len(SEXAGENARY_CYCLE)]


def calculate_luck_cycles(
    *,
    gender: Gender,
    normalized_birth_dt: datetime,
    year_pillar: str,
    month_pillar: str,
    day_pillar: str | None = None,
    cycle_count: int = 10,
    target_standard_offset_minutes: int | None = None,
    timezone_id: str | None = None,
) -> List[LuckCycle]:
    """대운 방향과 시작 나이를 계산해 대운 목록을 만든다."""
    del day_pillar  # Reserved for downstream rule extensions and debug reporting.

    year_stem = year_pillar[:1]
    direction = get_luck_direction(year_stem, gender)
    boundary_dt = get_adjacent_month_boundary(
        normalized_birth_dt,
        direction,
        target_standard_offset_minutes=target_standard_offset_minutes,
        timezone_id=timezone_id,
    )

    if direction == "forward":
        delta = boundary_dt - normalized_birth_dt
        first_pillar = shift_ganzhi(month_pillar, 1)
        step_sign = 1
    else:
        delta = normalized_birth_dt - boundary_dt
        first_pillar = shift_ganzhi(month_pillar, -1)
        step_sign = -1

    delta_days = delta.total_seconds() / 86400
    exact_start_age_years = delta_days / 3.0
    precise_start_age_years = (
        delta_days * LUCK_CYCLE_YEAR_TO_DAY_FACTOR / TROPICAL_YEAR_DAYS
    )
    display_start_age = get_display_start_age(
        normalized_birth_dt,
        boundary_dt,
        direction,
    )

    luck_cycles: List[LuckCycle] = []
    first_cycle_start_dt = normalized_birth_dt + timedelta(
        days=delta_days * LUCK_CYCLE_YEAR_TO_DAY_FACTOR
    )
    decade_duration = timedelta(days=TROPICAL_YEAR_DAYS * 10)
    for index in range(cycle_count):
        pillar = shift_ganzhi(first_pillar, index * step_sign)
        start_age = display_start_age + (10 * index)
        start_year = normalized_birth_dt.year + start_age
        cycle_start_dt = first_cycle_start_dt + timedelta(days=TROPICAL_YEAR_DAYS * 10 * index)
        cycle_change_dt = cycle_start_dt + decade_duration
        start_age_total_months = get_completed_age_months(normalized_birth_dt, cycle_start_dt)
        start_age_years, start_age_months = get_age_year_month_components(start_age_total_months)
        change_age_total_months = get_completed_age_months(normalized_birth_dt, cycle_change_dt)
        change_age_years, change_age_months = get_age_year_month_components(change_age_total_months)
        luck_cycles.append(
            LuckCycle(
                index=index + 1,
                gan_zhi=pillar,
                start_year=start_year,
                end_year=start_year + 9,
                start_age=start_age,
                end_age=start_age + 9,
                start_age_years=start_age_years,
                start_age_months=start_age_months,
                start_age_total_months=start_age_total_months,
                change_age_years=change_age_years,
                change_age_months=change_age_months,
                change_age_total_months=change_age_total_months,
                direction=direction,
                exact_start_age_years=exact_start_age_years,
                precise_start_age_years=precise_start_age_years,
                month_boundary_datetime=boundary_dt.strftime("%Y-%m-%d %H:%M:%S"),
                start_datetime=cycle_start_dt.strftime("%Y-%m-%d %H:%M:%S"),
                change_datetime=cycle_change_dt.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    return luck_cycles
