"""이 파일은 lunar_python 라이브러리를 내부 사주 엔진 interface에 맞게 감싼다."""

from datetime import datetime
from typing import Dict, List, Optional

from lunar_python import Solar

from app.domain.saju.engine import (
    Gender,
    PillarData,
    SajuCalculationResult,
    SupplementaryPosition,
)
from app.domain.saju.services.calculate_luck_cycles import calculate_luck_cycles
from app.domain.saju.services.canonical_year_month import calculate_canonical_year_month
from app.domain.saju.services.day_pillar_reference import (
    get_day_pillar_reference_date,
    resolve_day_pillar_reference,
)
from app.domain.saju.time_correction import STANDARD_OFFSET_BY_TZ


ELEMENT_KEY_BY_CHAR = {
    "木": "wood",
    "火": "fire",
    "土": "earth",
    "金": "metal",
    "水": "water",
}


class SajuCalculationError(ValueError):
    def __init__(self, *, error_code: str, message: str, meta: Dict[str, str]) -> None:
        """해당 오류 유형에 필요한 정보를 저장하도록 객체를 초기화한다."""
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.meta = meta


class LunarPythonSajuEngine:
    def calculate(
        self,
        *,
        corrected_solar_datetime: str,
        gender: Gender,
        tzid: Optional[str] = None,
        day_pillar_basis_datetime: Optional[str] = None,
        use_canonical_year_month_pillars: bool = False,
    ) -> SajuCalculationResult:
        """lunar_python 엔진으로 사주를 계산하고 내부 모델로 변환한다."""
        try:
            dt = datetime.strptime(corrected_solar_datetime, "%Y-%m-%d %H:%M:%S")
        except ValueError as exc:
            raise SajuCalculationError(
                error_code="INVALID_CORRECTED_SOLAR_DATETIME",
                message="The corrected solar datetime must use YYYY-MM-DD HH:MM:SS format.",
                meta={"corrected_solar_datetime": corrected_solar_datetime},
            ) from exc
        day_pillar_lookup_dt = dt
        if day_pillar_basis_datetime:
            try:
                day_pillar_lookup_dt = datetime.strptime(
                    day_pillar_basis_datetime,
                    "%Y-%m-%d %H:%M:%S",
                )
            except ValueError as exc:
                raise SajuCalculationError(
                    error_code="INVALID_DAY_PILLAR_BASIS_DATETIME",
                    message="The day-pillar basis datetime must use YYYY-MM-DD HH:MM:SS format.",
                    meta={"day_pillar_basis_datetime": day_pillar_basis_datetime},
                ) from exc
        day_time_dt = (
            day_pillar_lookup_dt
            if get_day_pillar_reference_date(day_pillar_lookup_dt, 1)
            != get_day_pillar_reference_date(dt, 1)
            else dt
        )

        try:
            solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            lunar = solar.getLunar()
            eight_char = lunar.getEightChar()
            # Use the late-zi-day-switch convention expected by the current
            # golden answers: day pillar changes after 23:00.
            eight_char.setSect(1)
            day_time_solar = Solar.fromYmdHms(
                day_time_dt.year,
                day_time_dt.month,
                day_time_dt.day,
                day_time_dt.hour,
                day_time_dt.minute,
                day_time_dt.second,
            )
            day_time_eight_char = day_time_solar.getLunar().getEightChar()
            day_time_eight_char.setSect(1)
        except Exception as exc:
            raise SajuCalculationError(
                error_code="SAJU_ENGINE_CALCULATION_ERROR",
                message="The saju engine could not calculate the normalized input.",
                meta={
                    "corrected_solar_datetime": corrected_solar_datetime,
                    "gender": gender,
                },
            ) from exc

        pillars = {
            "year": self._build_pillar(
                gan_zhi=eight_char.getYear(),
                stem=eight_char.getYearGan(),
                branch=eight_char.getYearZhi(),
                five_elements=eight_char.getYearWuXing(),
                stem_ten_god=eight_char.getYearShiShenGan(),
                branch_ten_gods=eight_char.getYearShiShenZhi(),
                hidden_stems=eight_char.getYearHideGan(),
                twelve_fortune=eight_char.getYearDiShi(),
                na_yin=eight_char.getYearNaYin(),
                xun=eight_char.getYearXun(),
                xun_kong=eight_char.getYearXunKong(),
            ),
            "month": self._build_pillar(
                gan_zhi=eight_char.getMonth(),
                stem=eight_char.getMonthGan(),
                branch=eight_char.getMonthZhi(),
                five_elements=eight_char.getMonthWuXing(),
                stem_ten_god=eight_char.getMonthShiShenGan(),
                branch_ten_gods=eight_char.getMonthShiShenZhi(),
                hidden_stems=eight_char.getMonthHideGan(),
                twelve_fortune=eight_char.getMonthDiShi(),
                na_yin=eight_char.getMonthNaYin(),
                xun=eight_char.getMonthXun(),
                xun_kong=eight_char.getMonthXunKong(),
            ),
            "day": self._build_pillar(
                gan_zhi=day_time_eight_char.getDay(),
                stem=day_time_eight_char.getDayGan(),
                branch=day_time_eight_char.getDayZhi(),
                five_elements=day_time_eight_char.getDayWuXing(),
                stem_ten_god=day_time_eight_char.getDayShiShenGan(),
                branch_ten_gods=day_time_eight_char.getDayShiShenZhi(),
                hidden_stems=day_time_eight_char.getDayHideGan(),
                twelve_fortune=day_time_eight_char.getDayDiShi(),
                na_yin=day_time_eight_char.getDayNaYin(),
                xun=day_time_eight_char.getDayXun(),
                xun_kong=day_time_eight_char.getDayXunKong(),
            ),
            "time": self._build_pillar(
                gan_zhi=day_time_eight_char.getTime(),
                stem=day_time_eight_char.getTimeGan(),
                branch=day_time_eight_char.getTimeZhi(),
                five_elements=day_time_eight_char.getTimeWuXing(),
                stem_ten_god=day_time_eight_char.getTimeShiShenGan(),
                branch_ten_gods=day_time_eight_char.getTimeShiShenZhi(),
                hidden_stems=day_time_eight_char.getTimeHideGan(),
                twelve_fortune=day_time_eight_char.getTimeDiShi(),
                na_yin=day_time_eight_char.getTimeNaYin(),
                xun=day_time_eight_char.getTimeXun(),
                xun_kong=day_time_eight_char.getTimeXunKong(),
            ),
        }
        day_reference = resolve_day_pillar_reference(
            input_dt=day_pillar_lookup_dt,
            sect=1,
            lunar_python_gan_zhi=pillars["day"].gan_zhi,
        )
        pillars["day"].gan_zhi = day_reference.gan_zhi
        pillars["day"].stem = day_reference.stem
        pillars["day"].branch = day_reference.branch
        year_month_context = calculate_canonical_year_month(
            basis_datetime_text=corrected_solar_datetime,
            timezone_id=tzid,
            day_stem=pillars["day"].stem,
            legacy_year_pillar=pillars["year"].gan_zhi,
            legacy_month_pillar=pillars["month"].gan_zhi,
            apply_to_primary=use_canonical_year_month_pillars,
        )
        if (
            use_canonical_year_month_pillars
            and year_month_context.year_pillar is not None
            and year_month_context.month_pillar is not None
        ):
            pillars["year"] = year_month_context.year_pillar
            pillars["month"] = year_month_context.month_pillar

        luck_cycles = calculate_luck_cycles(
            gender=gender,
            normalized_birth_dt=dt,
            year_pillar=pillars["year"].gan_zhi,
            month_pillar=pillars["month"].gan_zhi,
            day_pillar=pillars["day"].gan_zhi,
            cycle_count=10,
            target_standard_offset_minutes=STANDARD_OFFSET_BY_TZ.get(tzid) if tzid else None,
            timezone_id=tzid,
        )
        first_luck_cycle = luck_cycles[0] if luck_cycles else None

        return SajuCalculationResult(
            pillars=pillars,
            element_counts=self._count_elements(pillars),
            ten_god_stems={
                "year": pillars["year"].stem_ten_god,
                "month": pillars["month"].stem_ten_god,
                "day": pillars["day"].stem_ten_god,
                "time": pillars["time"].stem_ten_god,
            },
            luck_cycles=luck_cycles,
            supplementary_positions={
                "tai_yuan": SupplementaryPosition(
                    gan_zhi=eight_char.getTaiYuan(),
                    na_yin=eight_char.getTaiYuanNaYin(),
                ),
                "ming_gong": SupplementaryPosition(
                    gan_zhi=eight_char.getMingGong(),
                    na_yin=eight_char.getMingGongNaYin(),
                ),
                "shen_gong": SupplementaryPosition(
                    gan_zhi=eight_char.getShenGong(),
                    na_yin=eight_char.getShenGongNaYin(),
                ),
                "tai_xi": SupplementaryPosition(
                    gan_zhi=eight_char.getTaiXi(),
                    na_yin=eight_char.getTaiXiNaYin(),
                ),
            },
            meta={
                "corrected_solar_datetime": corrected_solar_datetime,
                "gender": gender,
                "day_master": pillars["day"].stem,
                "day_time_basis_datetime": day_time_dt.strftime("%Y-%m-%d %H:%M:%S"),
                "civil_date": day_reference.civil_date,
                "day_pillar_rule": day_reference.rule,
                "day_pillar_basis_date": day_reference.day_pillar_basis_date,
                "iljin_query_date": day_reference.iljin_query_date,
                "day_pillar_source": day_reference.source,
                "day_pillar_reference_date": day_reference.reference_date,
                "day_pillar_reference_matched_lunar_python": day_reference.matched_lunar_python,
                "luck_cycle_start_date": (
                    first_luck_cycle.month_boundary_datetime[:10]
                    if first_luck_cycle and first_luck_cycle.month_boundary_datetime
                    else ""
                ),
                "luck_cycle_boundary_datetime": (
                    first_luck_cycle.month_boundary_datetime if first_luck_cycle else ""
                ),
                "luck_cycle_direction": first_luck_cycle.direction if first_luck_cycle else "",
                "luck_cycle_exact_start_age_years": (
                    f"{first_luck_cycle.exact_start_age_years:.6f}"
                    if first_luck_cycle and first_luck_cycle.exact_start_age_years is not None
                    else ""
                ),
                "luck_cycle_precise_start_age_years": (
                    f"{first_luck_cycle.precise_start_age_years:.6f}"
                    if first_luck_cycle and first_luck_cycle.precise_start_age_years is not None
                    else ""
                ),
            },
            year_month_boundary_context=year_month_context.context,
        )

    def _build_pillar(
        self,
        *,
        gan_zhi: str,
        stem: str,
        branch: str,
        five_elements: str,
        stem_ten_god: str,
        branch_ten_gods: List[str],
        hidden_stems: List[str],
        twelve_fortune: str,
        na_yin: str,
        xun: str,
        xun_kong: str,
    ) -> PillarData:
        """기둥을 조립한다."""
        stem_five_element = five_elements[0] if len(five_elements) >= 1 else ""
        branch_five_element = five_elements[1] if len(five_elements) >= 2 else ""
        return PillarData(
            gan_zhi=gan_zhi,
            stem=stem,
            branch=branch,
            stem_five_element=stem_five_element,
            branch_five_element=branch_five_element,
            five_elements=five_elements,
            stem_ten_god=stem_ten_god,
            branch_ten_god=branch_ten_gods[0] if branch_ten_gods else "",
            branch_ten_gods=list(branch_ten_gods),
            hidden_stems=list(hidden_stems),
            twelve_fortune=twelve_fortune,
            na_yin=na_yin,
            xun=xun,
            xun_kong=xun_kong,
        )

    def _count_elements(self, pillars: Dict[str, PillarData]) -> Dict[str, int]:
        """오행 목록를 센다."""
        counts = {key: 0 for key in ELEMENT_KEY_BY_CHAR.values()}
        for pillar in pillars.values():
            for char in pillar.five_elements:
                if char in ELEMENT_KEY_BY_CHAR:
                    counts[ELEMENT_KEY_BY_CHAR[char]] += 1
        return counts
