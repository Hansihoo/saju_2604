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

        try:
            solar = Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
            lunar = solar.getLunar()
            eight_char = lunar.getEightChar()
            # Use the late-zi-day-switch convention expected by the current
            # golden answers: day pillar changes after 23:00.
            eight_char.setSect(1)
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
                gan_zhi=eight_char.getDay(),
                stem=eight_char.getDayGan(),
                branch=eight_char.getDayZhi(),
                five_elements=eight_char.getDayWuXing(),
                stem_ten_god=eight_char.getDayShiShenGan(),
                branch_ten_gods=eight_char.getDayShiShenZhi(),
                hidden_stems=eight_char.getDayHideGan(),
                twelve_fortune=eight_char.getDayDiShi(),
                na_yin=eight_char.getDayNaYin(),
                xun=eight_char.getDayXun(),
                xun_kong=eight_char.getDayXunKong(),
            ),
            "time": self._build_pillar(
                gan_zhi=eight_char.getTime(),
                stem=eight_char.getTimeGan(),
                branch=eight_char.getTimeZhi(),
                five_elements=eight_char.getTimeWuXing(),
                stem_ten_god=eight_char.getTimeShiShenGan(),
                branch_ten_gods=eight_char.getTimeShiShenZhi(),
                hidden_stems=eight_char.getTimeHideGan(),
                twelve_fortune=eight_char.getTimeDiShi(),
                na_yin=eight_char.getTimeNaYin(),
                xun=eight_char.getTimeXun(),
                xun_kong=eight_char.getTimeXunKong(),
            ),
        }

        luck_cycles = calculate_luck_cycles(
            gender=gender,
            normalized_birth_dt=dt,
            year_pillar=pillars["year"].gan_zhi,
            month_pillar=pillars["month"].gan_zhi,
            day_pillar=pillars["day"].gan_zhi,
            cycle_count=10,
            target_standard_offset_minutes=STANDARD_OFFSET_BY_TZ.get(tzid) if tzid else None,
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
