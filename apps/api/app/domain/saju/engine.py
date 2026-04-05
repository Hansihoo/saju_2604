from dataclasses import dataclass
from typing import Dict, List, Literal, Protocol


Gender = Literal["male", "female"]


@dataclass
class PillarData:
    gan_zhi: str
    stem: str
    branch: str
    five_elements: str
    stem_ten_god: str
    branch_ten_gods: List[str]
    hidden_stems: List[str]


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
    meta: Dict[str, str]


class SajuEngine(Protocol):
    def calculate(
        self,
        *,
        normalized_solar_datetime: str,
        gender: Gender,
    ) -> SajuCalculationResult:
        ...
