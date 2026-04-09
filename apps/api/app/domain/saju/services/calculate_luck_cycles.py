from __future__ import annotations

from datetime import datetime, timedelta
from math import floor
from typing import List, Literal

from lunar_python import Solar
from lunar_python.util import LunarUtil

from app.domain.saju.engine import Gender, LuckCycle


LuckDirection = Literal["forward", "backward"]

YANG_STEMS = {"甲", "丙", "戊", "庚", "壬"}
SEXAGENARY_CYCLE = tuple(LunarUtil.JIA_ZI)
LUNAR_ENGINE_STANDARD_OFFSET_MINUTES = 480
TROPICAL_YEAR_DAYS = 365.2422
LUCK_CYCLE_YEAR_TO_DAY_FACTOR = 120.0


def is_yang_stem(stem: str) -> bool:
    return stem in YANG_STEMS


def get_luck_direction(year_stem: str, gender: Gender) -> LuckDirection:
    if (gender == "male" and is_yang_stem(year_stem)) or (
        gender == "female" and not is_yang_stem(year_stem)
    ):
        return "forward"
    return "backward"


def get_adjacent_month_boundary(
    normalized_birth_dt: datetime,
    direction: LuckDirection,
    target_standard_offset_minutes: int | None = None,
) -> datetime:
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
    del direction  # Kept to make the helper interface explicit for tests/debugging.
    delta_days = abs((boundary_dt - birth_dt).total_seconds()) / 86400
    precise_start_age_years = delta_days * LUCK_CYCLE_YEAR_TO_DAY_FACTOR / TROPICAL_YEAR_DAYS
    return floor(precise_start_age_years + 0.5)


def shift_ganzhi(pillar: str, steps: int) -> str:
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
) -> List[LuckCycle]:
    del day_pillar  # Reserved for downstream rule extensions and debug reporting.

    year_stem = year_pillar[:1]
    direction = get_luck_direction(year_stem, gender)
    boundary_dt = get_adjacent_month_boundary(
        normalized_birth_dt,
        direction,
        target_standard_offset_minutes=target_standard_offset_minutes,
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
    for index in range(cycle_count):
        pillar = shift_ganzhi(first_pillar, index * step_sign)
        start_age = display_start_age + (10 * index)
        start_year = normalized_birth_dt.year + start_age
        luck_cycles.append(
            LuckCycle(
                index=index + 1,
                gan_zhi=pillar,
                start_year=start_year,
                end_year=start_year + 9,
                start_age=start_age,
                end_age=start_age + 9,
                direction=direction,
                exact_start_age_years=exact_start_age_years,
                precise_start_age_years=precise_start_age_years,
                month_boundary_datetime=boundary_dt.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    return luck_cycles
