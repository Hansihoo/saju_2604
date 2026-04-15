"""이 파일은 CSV 시드 데이터를 읽어 지역 목록으로 변환한다."""

import csv
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DATA_PATH = Path(__file__).resolve().parent / "data" / "korea_city_longitudes_for_saju.csv"

PROVINCE_ALIASES: Dict[str, List[str]] = {
    "서울특별시": ["서울", "서울시"],
    "부산광역시": ["부산", "부산시"],
    "인천광역시": ["인천", "인천시"],
    "대구광역시": ["대구", "대구시"],
    "대전광역시": ["대전", "대전시"],
    "광주광역시": ["광주", "광주시"],
    "울산광역시": ["울산", "울산시"],
    "세종특별자치시": ["세종", "세종시"],
    "경기도": ["경기"],
    "강원특별자치도": ["강원"],
    "충청북도": ["충북"],
    "충청남도": ["충남"],
    "전북특별자치도": ["전북", "전라북도"],
    "전라남도": ["전남"],
    "경상북도": ["경북"],
    "경상남도": ["경남"],
    "제주특별자치도": ["제주"],
}

REGION_ID_BY_LOCALITY: Dict[Tuple[str, str], str] = {
    ("서울특별시", "서울특별시"): "kr-seoul-special",
    ("부산광역시", "부산광역시"): "kr-busan-metropolitan",
    ("인천광역시", "인천광역시"): "kr-incheon-metropolitan",
    ("대구광역시", "대구광역시"): "kr-daegu-metropolitan",
    ("대전광역시", "대전광역시"): "kr-daejeon-metropolitan",
    ("광주광역시", "광주광역시"): "kr-gwangju-metropolitan",
    ("울산광역시", "울산광역시"): "kr-ulsan-metropolitan",
    ("세종특별자치시", "세종특별자치시"): "kr-sejong-special",
    ("경기도", "수원시"): "kr-gyeonggi-suwon",
    ("경기도", "성남시"): "kr-gyeonggi-seongnam",
    ("경기도", "고양시"): "kr-gyeonggi-goyang",
    ("경기도", "용인시"): "kr-gyeonggi-yongin",
    ("경기도", "부천시"): "kr-gyeonggi-bucheon",
    ("경기도", "안산시"): "kr-gyeonggi-ansan",
    ("경기도", "안양시"): "kr-gyeonggi-anyang",
    ("경기도", "남양주시"): "kr-gyeonggi-namyangju",
    ("경기도", "화성시"): "kr-gyeonggi-hwaseong",
    ("경기도", "평택시"): "kr-gyeonggi-pyeongtaek",
    ("경기도", "의정부시"): "kr-gyeonggi-uijeongbu",
    ("경기도", "시흥시"): "kr-gyeonggi-siheung",
    ("경기도", "파주시"): "kr-gyeonggi-paju",
    ("경기도", "광명시"): "kr-gyeonggi-gwangmyeong",
    ("경기도", "김포시"): "kr-gyeonggi-gimpo",
    ("경기도", "군포시"): "kr-gyeonggi-gunpo",
    ("경기도", "오산시"): "kr-gyeonggi-osan",
    ("경기도", "이천시"): "kr-gyeonggi-icheon",
    ("경기도", "안성시"): "kr-gyeonggi-anseong",
    ("경기도", "구리시"): "kr-gyeonggi-guri",
    ("경기도", "포천시"): "kr-gyeonggi-pocheon",
    ("경기도", "양주시"): "kr-gyeonggi-yangju",
    ("경기도", "동두천시"): "kr-gyeonggi-dongducheon",
    ("경기도", "과천시"): "kr-gyeonggi-gwacheon",
    ("경기도", "의왕시"): "kr-gyeonggi-uiwang",
    ("경기도", "하남시"): "kr-gyeonggi-hanam",
    ("경기도", "광주시"): "kr-gyeonggi-gwangju",
    ("경기도", "여주시"): "kr-gyeonggi-yeoju",
    ("강원특별자치도", "춘천시"): "kr-gangwon-chuncheon",
    ("강원특별자치도", "원주시"): "kr-gangwon-wonju",
    ("강원특별자치도", "강릉시"): "kr-gangwon-gangneung",
    ("강원특별자치도", "동해시"): "kr-gangwon-donghae",
    ("강원특별자치도", "태백시"): "kr-gangwon-taebaek",
    ("강원특별자치도", "속초시"): "kr-gangwon-sokcho",
    ("강원특별자치도", "삼척시"): "kr-gangwon-samcheok",
    ("충청북도", "청주시"): "kr-chungbuk-cheongju",
    ("충청북도", "충주시"): "kr-chungbuk-chungju",
    ("충청북도", "제천시"): "kr-chungbuk-jecheon",
    ("충청남도", "천안시"): "kr-chungnam-cheonan",
    ("충청남도", "공주시"): "kr-chungnam-gongju",
    ("충청남도", "보령시"): "kr-chungnam-boryeong",
    ("충청남도", "아산시"): "kr-chungnam-asan",
    ("충청남도", "서산시"): "kr-chungnam-seosan",
    ("충청남도", "논산시"): "kr-chungnam-nonsan",
    ("충청남도", "계룡시"): "kr-chungnam-gyeryong",
    ("충청남도", "당진시"): "kr-chungnam-dangjin",
    ("전북특별자치도", "전주시"): "kr-jeonbuk-jeonju",
    ("전북특별자치도", "군산시"): "kr-jeonbuk-gunsan",
    ("전북특별자치도", "익산시"): "kr-jeonbuk-iksan",
    ("전북특별자치도", "정읍시"): "kr-jeonbuk-jeongeup",
    ("전북특별자치도", "남원시"): "kr-jeonbuk-namwon",
    ("전북특별자치도", "김제시"): "kr-jeonbuk-gimje",
    ("전라남도", "목포시"): "kr-jeonnam-mokpo",
    ("전라남도", "여수시"): "kr-jeonnam-yeosu",
    ("전라남도", "순천시"): "kr-jeonnam-suncheon",
    ("전라남도", "나주시"): "kr-jeonnam-naju",
    ("전라남도", "광양시"): "kr-jeonnam-gwangyang",
    ("경상북도", "포항시"): "kr-gyeongbuk-pohang",
    ("경상북도", "경주시"): "kr-gyeongbuk-gyeongju",
    ("경상북도", "김천시"): "kr-gyeongbuk-gimcheon",
    ("경상북도", "안동시"): "kr-gyeongbuk-andong",
    ("경상북도", "구미시"): "kr-gyeongbuk-gumi",
    ("경상북도", "영주시"): "kr-gyeongbuk-yeongju",
    ("경상북도", "영천시"): "kr-gyeongbuk-yeongcheon",
    ("경상북도", "상주시"): "kr-gyeongbuk-sangju",
    ("경상북도", "문경시"): "kr-gyeongbuk-mungyeong",
    ("경상북도", "경산시"): "kr-gyeongbuk-gyeongsan",
    ("경상남도", "창원시"): "kr-gyeongnam-changwon",
    ("경상남도", "진주시"): "kr-gyeongnam-jinju",
    ("경상남도", "통영시"): "kr-gyeongnam-tongyeong",
    ("경상남도", "사천시"): "kr-gyeongnam-sacheon",
    ("경상남도", "김해시"): "kr-gyeongnam-gimhae",
    ("경상남도", "밀양시"): "kr-gyeongnam-miryang",
    ("경상남도", "거제시"): "kr-gyeongnam-geoje",
    ("경상남도", "양산시"): "kr-gyeongnam-yangsan",
    ("제주특별자치도", "제주시"): "kr-jeju-jeju",
    ("제주특별자치도", "서귀포시"): "kr-jeju-seogwipo",
}

SPECIAL_LOCALITY_ALIASES: Dict[Tuple[str, str], List[str]] = {
    ("서울특별시", "서울특별시"): ["서울", "서울시"],
    ("부산광역시", "부산광역시"): ["부산", "부산시"],
    ("인천광역시", "인천광역시"): ["인천", "인천시"],
    ("대구광역시", "대구광역시"): ["대구", "대구시"],
    ("대전광역시", "대전광역시"): ["대전", "대전시"],
    ("광주광역시", "광주광역시"): ["광주", "광주시"],
    ("울산광역시", "울산광역시"): ["울산", "울산시"],
    ("세종특별자치시", "세종특별자치시"): ["세종", "세종시"],
}

ENGLISH_ALIASES: Dict[Tuple[str, str], List[str]] = {
    ("서울특별시", "서울특별시"): ["Seoul"],
    ("부산광역시", "부산광역시"): ["Busan"],
    ("인천광역시", "인천광역시"): ["Incheon"],
    ("대구광역시", "대구광역시"): ["Daegu"],
    ("대전광역시", "대전광역시"): ["Daejeon"],
    ("광주광역시", "광주광역시"): ["Gwangju"],
    ("울산광역시", "울산광역시"): ["Ulsan"],
    ("세종특별자치시", "세종특별자치시"): ["Sejong"],
}

LEGACY_REGION_ID_MAP = {
    "kr-seoul": "kr-seoul-special",
    "kr-busan": "kr-busan-metropolitan",
    "kr-incheon": "kr-incheon-metropolitan",
    "kr-daegu": "kr-daegu-metropolitan",
    "kr-daejeon": "kr-daejeon-metropolitan",
    "kr-gwangju": "kr-gwangju-metropolitan",
    "kr-ulsan": "kr-ulsan-metropolitan",
    "kr-jeju": "kr-jeju-jeju",
}

MANUAL_REGION_OVERRIDES: List[Dict[str, object]] = [
    {
        "id": "kr-gangwon-province",
        "display_name": "강원도",
        "country": "대한민국",
        "province": "강원특별자치도",
        "city": "강원도",
        "tzid": "Asia/Seoul",
        "longitude": 128.25,
        "regional_time_offset_minutes": -27.0,
        "correction_basis": "golden_override",
        "aliases": ["강원도", "강원", "강원특별자치도", "Gangwon"],
    },
]


def _display_name(province: str, city: str) -> str:
    """name 관련 값을 반환하거나 처리한다."""
    if province == city:
        return city
    return f"{city}, {province}"


def _fallback_region_id(province: str, city: str) -> str:
    """지역 ID 관련 값을 반환하거나 처리한다."""
    encoded = f"{province}-{city}".encode("utf-8").hex()
    return f"kr-{encoded}"


def _trim_locality_suffix(locality: str) -> Optional[str]:
    """locality suffix을 다듬는다."""
    for suffix in ("특별자치시", "특별시", "광역시", "특별자치도", "자치시", "시"):
        if locality.endswith(suffix) and len(locality) > len(suffix):
            return locality[: -len(suffix)]
    return None


def _make_aliases(province: str, city: str) -> List[str]:
    """aliases 관련 값을 반환하거나 처리한다."""
    province_aliases = [province, *PROVINCE_ALIASES.get(province, [])]
    city_aliases = [city, *SPECIAL_LOCALITY_ALIASES.get((province, city), [])]
    trimmed_city = _trim_locality_suffix(city)
    if trimmed_city:
        city_aliases.append(trimmed_city)

    alias_values = [
        *province_aliases,
        *city_aliases,
        f"{province} {city}",
        f"{province}{city}",
        f"{city} {province}",
    ]

    for province_alias in province_aliases:
        alias_values.append(f"{province_alias} {city}")
        alias_values.append(f"{province_alias}{city}")
        for city_alias in city_aliases:
            alias_values.append(f"{province_alias} {city_alias}")
            alias_values.append(f"{province_alias}{city_alias}")

    for city_alias in city_aliases:
        alias_values.append(city_alias)
        alias_values.append(f"{city_alias} {province}")

    alias_values.extend(ENGLISH_ALIASES.get((province, city), []))

    deduped_aliases: List[str] = []
    for alias in alias_values:
        normalized = alias.strip()
        if normalized and normalized not in deduped_aliases:
            deduped_aliases.append(normalized)
    return deduped_aliases


def _row_to_region(row: Dict[str, str]) -> Dict[str, object]:
    """to 지역 관련 값을 반환하거나 처리한다."""
    province = row["시도"].strip()
    city = row["시"].strip()
    region_id = REGION_ID_BY_LOCALITY.get((province, city), _fallback_region_id(province, city))
    return {
        "id": region_id,
        "display_name": _display_name(province, city),
        "country": "대한민국",
        "province": province,
        "city": city,
        "tzid": "Asia/Seoul",
        "longitude": float(row["경도"]),
        "regional_time_offset_minutes": float(row["지역시차_분"]),
        "correction_basis": row["산출방식"].strip(),
        "aliases": _make_aliases(province, city),
    }


@lru_cache(maxsize=1)
def load_region_options() -> List[Dict[str, object]]:
    """지역 options을 불러온다."""
    with DATA_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return [_row_to_region(row) for row in reader] + list(MANUAL_REGION_OVERRIDES)


REGION_OPTIONS = load_region_options()
