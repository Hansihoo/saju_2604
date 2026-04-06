from typing import List, Optional


def _make_region(
    region_id: str,
    province: str,
    city: str,
    *,
    english_name: Optional[str] = None,
    aliases: Optional[List[str]] = None,
) -> dict:
    alias_values = [
        city,
        province,
        f"{province} {city}",
        f"{province}{city}",
        f"{city} {province}",
    ]
    if english_name:
        alias_values.append(english_name)
    if aliases:
        alias_values.extend(aliases)

    deduped_aliases: List[str] = []
    for alias in alias_values:
        normalized = alias.strip()
        if normalized and normalized not in deduped_aliases:
            deduped_aliases.append(normalized)

    return {
        "id": region_id,
        "display_name": f"{city}, {province}",
        "country": "대한민국",
        "city": city,
        "tzid": "Asia/Seoul",
        "aliases": deduped_aliases,
    }


REGION_OPTIONS = [
    _make_region("kr-seoul-special", "서울특별시", "서울특별시", english_name="Seoul", aliases=["서울"]),
    _make_region("kr-busan-metropolitan", "부산광역시", "부산광역시", english_name="Busan", aliases=["부산"]),
    _make_region("kr-incheon-metropolitan", "인천광역시", "인천광역시", english_name="Incheon", aliases=["인천"]),
    _make_region("kr-daegu-metropolitan", "대구광역시", "대구광역시", english_name="Daegu", aliases=["대구"]),
    _make_region("kr-daejeon-metropolitan", "대전광역시", "대전광역시", english_name="Daejeon", aliases=["대전"]),
    _make_region("kr-gwangju-metropolitan", "광주광역시", "광주광역시", english_name="Gwangju", aliases=["광주"]),
    _make_region("kr-ulsan-metropolitan", "울산광역시", "울산광역시", english_name="Ulsan", aliases=["울산"]),
    _make_region("kr-sejong-special", "세종특별자치시", "세종특별자치시", english_name="Sejong", aliases=["세종"]),
    _make_region("kr-gyeonggi-suwon", "경기도", "수원시"),
    _make_region("kr-gyeonggi-seongnam", "경기도", "성남시"),
    _make_region("kr-gyeonggi-goyang", "경기도", "고양시"),
    _make_region("kr-gyeonggi-yongin", "경기도", "용인시"),
    _make_region("kr-gyeonggi-bucheon", "경기도", "부천시"),
    _make_region("kr-gyeonggi-ansan", "경기도", "안산시"),
    _make_region("kr-gyeonggi-anyang", "경기도", "안양시"),
    _make_region("kr-gyeonggi-namyangju", "경기도", "남양주시"),
    _make_region("kr-gyeonggi-hwaseong", "경기도", "화성시"),
    _make_region("kr-gyeonggi-pyeongtaek", "경기도", "평택시"),
    _make_region("kr-gyeonggi-uijeongbu", "경기도", "의정부시"),
    _make_region("kr-gyeonggi-siheung", "경기도", "시흥시"),
    _make_region("kr-gyeonggi-paju", "경기도", "파주시"),
    _make_region("kr-gyeonggi-gwangmyeong", "경기도", "광명시"),
    _make_region("kr-gyeonggi-gimpo", "경기도", "김포시"),
    _make_region("kr-gyeonggi-gunpo", "경기도", "군포시"),
    _make_region("kr-gyeonggi-osan", "경기도", "오산시"),
    _make_region("kr-gyeonggi-icheon", "경기도", "이천시"),
    _make_region("kr-gyeonggi-anseong", "경기도", "안성시"),
    _make_region("kr-gyeonggi-guri", "경기도", "구리시"),
    _make_region("kr-gyeonggi-pocheon", "경기도", "포천시"),
    _make_region("kr-gyeonggi-yangju", "경기도", "양주시"),
    _make_region("kr-gyeonggi-dongducheon", "경기도", "동두천시"),
    _make_region("kr-gyeonggi-gwacheon", "경기도", "과천시"),
    _make_region("kr-gangwon-chuncheon", "강원특별자치도", "춘천시"),
    _make_region("kr-gangwon-wonju", "강원특별자치도", "원주시"),
    _make_region("kr-gangwon-gangneung", "강원특별자치도", "강릉시"),
    _make_region("kr-gangwon-donghae", "강원특별자치도", "동해시"),
    _make_region("kr-gangwon-taebaek", "강원특별자치도", "태백시"),
    _make_region("kr-gangwon-sokcho", "강원특별자치도", "속초시"),
    _make_region("kr-gangwon-samcheok", "강원특별자치도", "삼척시"),
    _make_region("kr-chungbuk-cheongju", "충청북도", "청주시"),
    _make_region("kr-chungbuk-chungju", "충청북도", "충주시"),
    _make_region("kr-chungbuk-jecheon", "충청북도", "제천시"),
    _make_region("kr-chungnam-cheonan", "충청남도", "천안시"),
    _make_region("kr-chungnam-gongju", "충청남도", "공주시"),
    _make_region("kr-chungnam-boryeong", "충청남도", "보령시"),
    _make_region("kr-chungnam-asan", "충청남도", "아산시"),
    _make_region("kr-chungnam-seosan", "충청남도", "서산시"),
    _make_region("kr-chungnam-nonsan", "충청남도", "논산시"),
    _make_region("kr-chungnam-gyeryong", "충청남도", "계룡시"),
    _make_region("kr-chungnam-dangjin", "충청남도", "당진시"),
    _make_region("kr-jeonbuk-jeonju", "전라북도", "전주시"),
    _make_region("kr-jeonbuk-gunsan", "전라북도", "군산시"),
    _make_region("kr-jeonbuk-iksan", "전라북도", "익산시"),
    _make_region("kr-jeonbuk-jeongeup", "전라북도", "정읍시"),
    _make_region("kr-jeonbuk-namwon", "전라북도", "남원시"),
    _make_region("kr-jeonbuk-gimje", "전라북도", "김제시"),
    _make_region("kr-jeonnam-mokpo", "전라남도", "목포시"),
    _make_region("kr-jeonnam-yeosu", "전라남도", "여수시"),
    _make_region("kr-jeonnam-suncheon", "전라남도", "순천시"),
    _make_region("kr-jeonnam-naju", "전라남도", "나주시"),
    _make_region("kr-jeonnam-gwangyang", "전라남도", "광양시"),
    _make_region("kr-gyeongbuk-pohang", "경상북도", "포항시"),
    _make_region("kr-gyeongbuk-gyeongju", "경상북도", "경주시"),
    _make_region("kr-gyeongbuk-gimcheon", "경상북도", "김천시"),
    _make_region("kr-gyeongbuk-andong", "경상북도", "안동시"),
    _make_region("kr-gyeongbuk-gumi", "경상북도", "구미시"),
    _make_region("kr-gyeongbuk-yeongju", "경상북도", "영주시"),
    _make_region("kr-gyeongbuk-yeongcheon", "경상북도", "영천시"),
    _make_region("kr-gyeongbuk-sangju", "경상북도", "상주시"),
    _make_region("kr-gyeongbuk-mungyeong", "경상북도", "문경시"),
    _make_region("kr-gyeongbuk-gyeongsan", "경상북도", "경산시"),
    _make_region("kr-gyeongnam-changwon", "경상남도", "창원시"),
    _make_region("kr-gyeongnam-jinju", "경상남도", "진주시"),
    _make_region("kr-gyeongnam-tongyeong", "경상남도", "통영시"),
    _make_region("kr-gyeongnam-sacheon", "경상남도", "사천시"),
    _make_region("kr-gyeongnam-gimhae", "경상남도", "김해시"),
    _make_region("kr-gyeongnam-miryang", "경상남도", "밀양시"),
    _make_region("kr-gyeongnam-geoje", "경상남도", "거제시"),
    _make_region("kr-gyeongnam-yangsan", "경상남도", "양산시"),
    _make_region("kr-jeju-jeju", "제주특별자치도", "제주시"),
    _make_region("kr-jeju-seogwipo", "제주특별자치도", "서귀포시"),
]

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
