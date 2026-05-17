"""이 파일은 사주 엔진이 사용하는 내부 모델과 interface를 정의한다."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Protocol


Gender = Literal["male", "female"]


@dataclass
class PillarData:
    gan_zhi: str
    stem: str
    branch: str
    stem_five_element: str
    branch_five_element: str
    five_elements: str
    stem_ten_god: str
    branch_ten_god: str
    branch_ten_gods: List[str]
    hidden_stems: List[str]
    twelve_fortune: str
    na_yin: str
    xun: str
    xun_kong: str


@dataclass
class SupplementaryPosition:
    gan_zhi: str
    na_yin: str


@dataclass
class LuckCycle:
    index: int
    gan_zhi: str
    start_year: int
    end_year: int
    start_age: int
    end_age: int
    start_age_years: Optional[int] = None
    start_age_months: Optional[int] = None
    start_age_total_months: Optional[int] = None
    change_age_years: Optional[int] = None
    change_age_months: Optional[int] = None
    change_age_total_months: Optional[int] = None
    direction: Optional[Literal["forward", "backward"]] = None
    exact_start_age_years: Optional[float] = None
    precise_start_age_years: Optional[float] = None
    month_boundary_datetime: Optional[str] = None
    start_datetime: Optional[str] = None
    change_datetime: Optional[str] = None


@dataclass
class SajuCalculationResult:
    pillars: Dict[str, PillarData]
    element_counts: Dict[str, int]
    ten_god_stems: Dict[str, str]
    luck_cycles: List[LuckCycle]
    supplementary_positions: Dict[str, SupplementaryPosition]
    meta: Dict[str, str]
    year_month_boundary_context: Dict[str, object] = field(default_factory=dict)


class SajuEngine(Protocol):
    def calculate(
        self,
        *,
        corrected_solar_datetime: str,
        gender: Gender,
        tzid: Optional[str] = None,
        day_pillar_basis_datetime: Optional[str] = None,
        use_canonical_year_month_pillars: bool = False,
    ) -> SajuCalculationResult:
        """계산 결과를 반환한다."""
        ...
