from __future__ import annotations

import re
from typing import Literal


OutputLocale = Literal["ko", "en"]


STEM_LABELS = {
    "甲": {"ko": "갑", "en": "Gap"},
    "乙": {"ko": "을", "en": "Eul"},
    "丙": {"ko": "병", "en": "Byeong"},
    "丁": {"ko": "정", "en": "Jeong"},
    "戊": {"ko": "무", "en": "Mu"},
    "己": {"ko": "기", "en": "Gi"},
    "庚": {"ko": "경", "en": "Gyeong"},
    "辛": {"ko": "신", "en": "Sin"},
    "壬": {"ko": "임", "en": "Im"},
    "癸": {"ko": "계", "en": "Gye"},
}

BRANCH_LABELS = {
    "子": {"ko": "자", "en": "Ja"},
    "丑": {"ko": "축", "en": "Chuk"},
    "寅": {"ko": "인", "en": "In"},
    "卯": {"ko": "묘", "en": "Myo"},
    "辰": {"ko": "진", "en": "Jin"},
    "巳": {"ko": "사", "en": "Sa"},
    "午": {"ko": "오", "en": "O"},
    "未": {"ko": "미", "en": "Mi"},
    "申": {"ko": "신", "en": "Sin"},
    "酉": {"ko": "유", "en": "Yu"},
    "戌": {"ko": "술", "en": "Sul"},
    "亥": {"ko": "해", "en": "Hae"},
}

TEN_GOD_CANONICAL = {
    "比肩": "비견",
    "劫財": "겁재",
    "劫财": "겁재",
    "食神": "식신",
    "傷官": "상관",
    "伤官": "상관",
    "偏財": "편재",
    "偏财": "편재",
    "正財": "정재",
    "正财": "정재",
    "偏官": "편관",
    "正官": "정관",
    "偏印": "편인",
    "正印": "정인",
    "비견": "비견",
    "겁재": "겁재",
    "식신": "식신",
    "상관": "상관",
    "편재": "편재",
    "정재": "정재",
    "편관": "편관",
    "정관": "정관",
    "편인": "편인",
    "정인": "정인",
    "日主": "일간",
}

TEN_GOD_ENGLISH = {
    "비견": "Peer",
    "겁재": "Rival",
    "식신": "Expression",
    "상관": "Output",
    "편재": "Indirect Wealth",
    "정재": "Direct Wealth",
    "편관": "Seven Killings",
    "정관": "Direct Officer",
    "편인": "Indirect Resource",
    "정인": "Direct Resource",
    "일간": "Day master",
}

PILLAR_LABELS = {
    "year": {"ko": "연주", "en": "Year pillar"},
    "month": {"ko": "월주", "en": "Month pillar"},
    "day": {"ko": "일주", "en": "Day pillar"},
    "time": {"ko": "시주", "en": "Time pillar"},
}

SPECIAL_STAR_LABELS = {
    "dohwa-year-branch": {"ko": "도화", "en": "Peach Blossom"},
    "dohwa-day-branch": {"ko": "도화", "en": "Peach Blossom"},
    "hongyeom": {"ko": "홍염", "en": "Red Charm"},
    "wangji-dohwa": {"ko": "왕지도화", "en": "Wangji Peach Blossom"},
    "mokyok-dohwa": {"ko": "목욕도화", "en": "Bath Peach Blossom"},
    "hamji-dohwa": {"ko": "함지도화", "en": "Hamji Peach Blossom"},
    "yeokma-year-branch": {"ko": "역마", "en": "Travel Star"},
    "yeokma-day-branch": {"ko": "역마", "en": "Travel Star"},
    "munchang-gwiin": {"ko": "문창귀인", "en": "Literary Star"},
    "hakdang": {"ko": "학당", "en": "Study Hall"},
    "hagwan": {"ko": "학관", "en": "Scholar Office"},
    "jangseong": {"ko": "장성", "en": "Leadership Star"},
    "yangin": {"ko": "양인", "en": "Yangin"},
    "gwaegang": {"ko": "괴강", "en": "Gwaegang"},
    "cheonmun-seong": {"ko": "천문성", "en": "Scholarly Star"},
    "cheoneul-gwiin": {"ko": "천을귀인", "en": "Heavenly Noble"},
    "woldeok-gwiin": {"ko": "월덕귀인", "en": "Monthly Virtue"},
    "gongmang": {"ko": "공망", "en": "Void"},
}

HANGUL_RE = re.compile(r"[\uac00-\ud7a3]")
HANJA_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


def contains_hangul(text: str) -> bool:
    return bool(HANGUL_RE.search(text))


def contains_hanja(text: str) -> bool:
    return bool(HANJA_RE.search(text))


def localize_stem(value: str, locale: OutputLocale) -> str:
    if not value:
        return ""
    if value in STEM_LABELS:
        return STEM_LABELS[value][locale]
    return value


def localize_branch(value: str, locale: OutputLocale) -> str:
    if not value:
        return ""
    if value in BRANCH_LABELS:
        return BRANCH_LABELS[value][locale]
    return value


def localize_ganzhi(value: str, locale: OutputLocale) -> str:
    if not value:
        return ""
    if len(value) >= 2 and value[0] in STEM_LABELS and value[1] in BRANCH_LABELS:
        stem = STEM_LABELS[value[0]][locale]
        branch = BRANCH_LABELS[value[1]][locale]
        return f"{stem}{branch}" if locale == "ko" else f"{stem}-{branch}"
    return value


def localize_ten_god(value: str, locale: OutputLocale) -> str:
    canonical = TEN_GOD_CANONICAL.get(value, value)
    if locale == "ko":
        return canonical
    return TEN_GOD_ENGLISH.get(canonical, canonical)


def localize_pillar_label(key: str, locale: OutputLocale) -> str:
    return PILLAR_LABELS.get(key, {}).get(locale, key)


def localize_special_star_label(key: str, fallback_label: str, locale: OutputLocale) -> str:
    return SPECIAL_STAR_LABELS.get(key, {}).get(locale, fallback_label)
