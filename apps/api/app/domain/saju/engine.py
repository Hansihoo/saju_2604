from dataclasses import dataclass
from typing import Dict, List, Literal, Protocol


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


@dataclass
class SajuCalculationResult:
    pillars: Dict[str, PillarData]
    element_counts: Dict[str, int]
    ten_god_stems: Dict[str, str]
    luck_cycles: List[LuckCycle]
    supplementary_positions: Dict[str, SupplementaryPosition]
    meta: Dict[str, str]


class SajuEngine(Protocol):
    def calculate(
        self,
        *,
        corrected_solar_datetime: str,
        gender: Gender,
    ) -> SajuCalculationResult:
        ...
