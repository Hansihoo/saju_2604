"""이 파일은 골든 케이스 답안 text를 파싱하는 로직을 담는다."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from app.domain.saju.golden import (
    GOLDEN_SPECIAL_STAR_ORDER,
    PILLAR_SORT_ORDER,
    GoldenBasicInfo,
    GoldenCaseInput,
    GoldenLuckCycleHeader,
    GoldenKnownAnswerCase,
    GoldenLuckCycleRow,
    GoldenPillarRow,
    GoldenSpecialStarRow,
    GoldenSnapshot,
    PILLAR_KEY_BY_LABEL,
    SUPPORTED_GOLDEN_SECTIONS,
    split_hidden_stems,
    to_korean_branch,
    to_korean_gan_zhi,
    to_korean_stem,
)
from app.domain.saju.region_repository import load_region_records


DATE_TIME_PATTERN = re.compile(
    r"(\d{4})\ub144\s*(\d{1,2})\uc6d4\s*(\d{1,2})\uc77c\s*(\d{1,2}:\d{2})"
)
OFFSET_PATTERN = re.compile(r"(\uc9c0\uc5ed\uc2dc|\uc11c\uba38\ud0c0\uc784)\s*([+-]?\d+)\ubd84")
FIELD_PATTERN = re.compile(r"^\*\*(.+?):\*\*\s*(.+)$")
LUCK_CYCLE_HEADER_PATTERN = re.compile(
    r"대운 분석\s*\(대운수:\s*(\d+)\s*,\s*([가-힣甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥]+)\s*\)"
)
SPECIAL_STAR_LINE_PATTERN = re.compile(r"\*\*신살:\*\*\s*(.+)")
GONGMANG_PATTERN = re.compile(r"공망\(일간\)\s*:?\s*(.+)")


SPECIAL_STAR_DEFINITIONS = [
    ("cheoneul-gwiin", "천을귀인", ["천을귀인"]),
    ("yangin", "양인", ["양인", "양인살"]),
    ("gwaegang", "괴강", ["괴강", "괴강살"]),
]

SPECIAL_STAR_ALIAS_TO_KEY = {
    alias: key
    for key, _label, aliases in SPECIAL_STAR_DEFINITIONS
    for alias in aliases
}

SPECIAL_STAR_LABEL_BY_KEY = {
    key: label for key, label, _aliases in SPECIAL_STAR_DEFINITIONS
}


def _trim_primary_text(text: str) -> str:
    """primary 텍스트을 다듬는다."""
    return text.split("```", 1)[0]


def _clean_markdown_cell(value: str) -> str:
    """마크다운 cell을 정리한다."""
    cleaned = re.sub(r"[*`_\\]", "", value)
    return re.sub(r"\s+", " ", cleaned).strip()


def _split_sections(text: str) -> Dict[str, str]:
    """섹션 목록을 분리한다."""
    sections: Dict[str, List[str]] = {}
    current_title: Optional[str] = None
    for raw_line in _trim_primary_text(text).splitlines():
        line = raw_line.rstrip()
        if line.startswith("### "):
            current_title = line[4:].strip()
            sections[current_title] = []
            continue
        if current_title:
            sections[current_title].append(line)
    return {title: "\n".join(lines).strip() for title, lines in sections.items()}


def _parse_datetime_to_minute(value: str) -> str:
    """시각 to minute를 파싱한다."""
    match = DATE_TIME_PATTERN.search(value)
    if not match:
        raise ValueError(f"Could not parse datetime from: {value}")
    year, month, day, time_value = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d} {time_value}"


def _parse_birth_info(value: str) -> Dict[str, object]:
    """출생 info를 파싱한다."""
    matches = DATE_TIME_PATTERN.findall(value)
    if len(matches) < 2:
        raise ValueError(f"Could not parse solar/lunar birth info from: {value}")
    solar = matches[0]
    lunar = matches[1]
    return {
        "solar_birth_datetime": f"{int(solar[0]):04d}-{int(solar[1]):02d}-{int(solar[2]):02d} {solar[3]}",
        "lunar_birth_datetime": f"{int(lunar[0]):04d}-{int(lunar[1]):02d}-{int(lunar[2]):02d} {lunar[3]}",
        "is_lunar_leap_month": "\uc724\ub2ec" in value,
    }


def _parse_markdown_table(section_text: str) -> List[List[str]]:
    """마크다운 표를 파싱한다."""
    table_lines: List[str] = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            table_lines.append(stripped)
        elif table_lines:
            break

    rows: List[List[str]] = []
    for line in table_lines:
        cells = [_clean_markdown_cell(cell) for cell in line.strip("|").split("|")]
        if cells and all(set(cell) <= {"-"} for cell in cells):
            continue
        rows.append(cells)
    return rows


def _parse_region_id(birth_place: str) -> str:
    """지역 ID를 파싱한다."""
    for region in load_region_records():
        if region.display_name == birth_place or region.city == birth_place:
            return region.id
    raise ValueError(f"Could not resolve region_id for birth place: {birth_place}")


def _parse_basic_info(section_text: str) -> Dict[str, object]:
    """basic info를 파싱한다."""
    parsed: Dict[str, object] = {}
    for line in section_text.splitlines():
        match = FIELD_PATTERN.match(line.strip())
        if not match:
            continue
        label, value = match.groups()
        if label == "\uc774\ub984":
            parsed["name"] = value.strip()
        elif label == "\uc0dd\ub144\uc6d4\uc77c":
            parsed.update(_parse_birth_info(value))
        elif label == "\uc131\ubcc4":
            parsed["gender_label"] = value.strip()
        elif label == "\ucd9c\uc0dd\uc9c0":
            parsed["birth_place"] = value.strip()
        elif label == "\ubcf4\uc815\uc2dc\uac04":
            parsed["corrected_datetime"] = _parse_datetime_to_minute(value)
            offsets = {kind: int(minutes) for kind, minutes in OFFSET_PATTERN.findall(value)}
            parsed["regional_time_offset_minutes"] = offsets.get("\uc9c0\uc5ed\uc2dc")
            parsed["daylight_saving_offset_minutes"] = offsets.get("\uc11c\uba38\ud0c0\uc784")
    return parsed


def _parse_pillar_table(section_text: str) -> Dict[str, GoldenPillarRow]:
    """기둥 표를 파싱한다."""
    rows = _parse_markdown_table(section_text)
    data_rows = rows[1:]
    pillars: Dict[str, GoldenPillarRow] = {}
    for row in data_rows:
        if len(row) < 8:
            continue
        label = row[0]
        pillar_key = PILLAR_KEY_BY_LABEL[label]
        stem = to_korean_stem(row[1])
        branch = to_korean_branch(row[3])
        pillars[pillar_key] = GoldenPillarRow(
            key=pillar_key,
            label=label,
            gan_zhi=stem + branch,
            stem=stem,
            stem_ten_god=row[2],
            branch=branch,
            branch_ten_god=row[4],
            hidden_stems=split_hidden_stems(row[5]),
            twelve_fortune=row[6],
            twelve_shinsal=row[7],
        )
    return pillars


def _parse_luck_cycles(section_text: str) -> List[GoldenLuckCycleRow]:
    """대운 대운 목록를 파싱한다."""
    rows = _parse_markdown_table(section_text)
    data_rows = rows[1:]
    cycles: List[GoldenLuckCycleRow] = []
    for row in data_rows:
        if len(row) < 4:
            continue
        age_text = re.sub(r"[^\d]", "", row[0])
        if not age_text:
            continue
        stem = to_korean_stem(row[2])
        branch = to_korean_branch(row[3])
        cycles.append(
            GoldenLuckCycleRow(
                start_age=int(age_text),
                gan_zhi=stem + branch,
                stem=stem,
                branch=branch,
            )
        )
    return cycles


def _parse_luck_cycle_header(section_title: str) -> GoldenLuckCycleHeader | None:
    """대운 대운 header를 파싱한다."""
    match = LUCK_CYCLE_HEADER_PATTERN.search(section_title)
    if not match:
        return None
    start_age_text, reference_pillar = match.groups()
    return GoldenLuckCycleHeader(
        start_age=int(start_age_text),
        reference_pillar=to_korean_gan_zhi(reference_pillar),
    )


def _normalize_special_star_key(value: str) -> str | None:
    """특수 신살 key를 정규화한다."""
    cleaned = value.strip()
    if not cleaned:
        return None
    return SPECIAL_STAR_ALIAS_TO_KEY.get(cleaned)


def _create_empty_special_star_rows() -> Dict[str, GoldenSpecialStarRow]:
    """empty 특수 신살 rows을 생성한다."""
    return {
        key: GoldenSpecialStarRow(key=key, label=label, active=False, matched_pillars=[])
        for key, label in SPECIAL_STAR_LABEL_BY_KEY.items()
    }


def _sort_pillar_keys(values: List[str]) -> List[str]:
    """기둥 keys을 정렬한다."""
    return sorted(values, key=lambda item: PILLAR_SORT_ORDER[item])


def _parse_special_star_rows(section_text: str) -> Dict[str, GoldenSpecialStarRow]:
    """특수 신살 rows를 파싱한다."""
    star_rows = _create_empty_special_star_rows()

    line_match = SPECIAL_STAR_LINE_PATTERN.search(section_text)
    if line_match:
        raw_values = [item.strip() for item in line_match.group(1).split(",")]
        for raw_value in raw_values:
            star_key = _normalize_special_star_key(raw_value)
            if star_key:
                star_rows[star_key].active = True

    rows = _parse_markdown_table(section_text)
    for row in rows[1:]:
        if len(row) < 5:
            continue
        pillar_key = PILLAR_KEY_BY_LABEL.get(row[0])
        if not pillar_key:
            continue
        for cell in [row[2], row[4]]:
            values = [item.strip() for item in cell.split(",") if item.strip()]
            for raw_value in values:
                star_key = _normalize_special_star_key(raw_value)
                if not star_key:
                    continue
                star_rows[star_key].active = True
                if pillar_key not in star_rows[star_key].matched_pillars:
                    star_rows[star_key].matched_pillars.append(pillar_key)

    return star_rows


def _parse_gongmang_matches(sections: Dict[str, str]) -> List[str]:
    """gongmang 매칭 목록를 파싱한다."""
    matches: List[str] = []

    for section_text in sections.values():
        for raw_line in section_text.splitlines():
            normalized_line = _clean_markdown_cell(raw_line)
            match = GONGMANG_PATTERN.search(normalized_line)
            if not match:
                continue
            values = [item.strip() for item in match.group(1).split(",") if item.strip()]
            for value in values:
                pillar_key = PILLAR_KEY_BY_LABEL.get(value)
                if pillar_key and pillar_key not in matches:
                    matches.append(pillar_key)

    return matches


def _parse_special_stars(
    *,
    sections: Dict[str, str],
) -> List[GoldenSpecialStarRow]:
    """특수 신살 목록를 파싱한다."""
    special_section = sections.get("신살과 길성")
    star_rows = (
        _parse_special_star_rows(special_section)
        if special_section
        else _create_empty_special_star_rows()
    )

    gongmang_matches = _parse_gongmang_matches(sections)
    if "gongmang" in star_rows and gongmang_matches:
        star_rows["gongmang"].active = True
        star_rows["gongmang"].matched_pillars = _sort_pillar_keys(gongmang_matches)

    for row in star_rows.values():
        row.matched_pillars = _sort_pillar_keys(row.matched_pillars)

    return [star_rows[key] for key, _label in GOLDEN_SPECIAL_STAR_ORDER]


def parse_golden_answer_text(
    *,
    case_id: str,
    source_name: str,
    source_file: str,
    text: str,
) -> GoldenKnownAnswerCase:
    """원본 golden 답안 텍스트를 구조화된 검증 케이스로 파싱한다."""
    sections = _split_sections(text)
    basic_info = _parse_basic_info(sections["\uae30\ubcf8\uc815\ubcf4"])
    birth_place = str(basic_info["birth_place"])
    region_id = _parse_region_id(birth_place)
    gender_label = str(basic_info["gender_label"])
    gender = "male" if gender_label == "\ub0a8\uc790" else "female"

    pillar_table = _parse_pillar_table(sections["\ucc9c\uac04\uacfc \uc9c0\uc9c0"])
    luck_section_title = next(
        (title for title in sections if title.startswith("\ub300\uc6b4 \ubd84\uc11d")),
        None,
    )
    luck_cycles = _parse_luck_cycles(sections[luck_section_title]) if luck_section_title else []
    luck_cycle_header = _parse_luck_cycle_header(luck_section_title) if luck_section_title else None
    special_stars = _parse_special_stars(sections=sections)

    unsupported_sections = [
        title
        for title in sections
        if title not in {"\uae30\ubcf8\uc815\ubcf4", "\ucc9c\uac04\uacfc \uc9c0\uc9c0", "\uc2e0\uc0b4\uacfc \uae38\uc131"}
        and not title.startswith("\ub300\uc6b4 \ubd84\uc11d")
    ]

    return GoldenKnownAnswerCase(
        input=GoldenCaseInput(
            case_id=case_id,
            source_name=source_name,
            source_file=source_file,
            calendar_type="solar",
            birth_date=str(basic_info["solar_birth_datetime"])[:10],
            birth_time=str(basic_info["solar_birth_datetime"])[11:16],
            gender=gender,
            region_id=region_id,
            is_lunar_leap_month=bool(basic_info["is_lunar_leap_month"]),
        ),
        expected=GoldenSnapshot(
            basic_info=GoldenBasicInfo(
                name=basic_info.get("name"),
                solar_birth_datetime=str(basic_info["solar_birth_datetime"]),
                lunar_birth_datetime=str(basic_info["lunar_birth_datetime"]),
                gender_label=gender_label,
                birth_place=birth_place,
                corrected_datetime=str(basic_info["corrected_datetime"]),
                regional_time_offset_minutes=int(basic_info["regional_time_offset_minutes"]),
                daylight_saving_offset_minutes=(
                    int(basic_info["daylight_saving_offset_minutes"])
                    if basic_info.get("daylight_saving_offset_minutes") is not None
                    else None
                ),
            ),
            pillar_table=pillar_table,
            luck_cycle_header=luck_cycle_header,
            luck_cycles=luck_cycles,
            special_stars=special_stars,
        ),
        supported_sections=list(SUPPORTED_GOLDEN_SECTIONS),
        unsupported_sections=unsupported_sections,
        raw_sections={title: sections[title] for title in unsupported_sections},
    )


def load_golden_answer_text(path: Path, *, case_id: str, source_name: str) -> GoldenKnownAnswerCase:
    """텍스트 파일을 읽어 golden 검증 케이스로 변환한다."""
    return parse_golden_answer_text(
        case_id=case_id,
        source_name=source_name,
        source_file=path.name,
        text=path.read_text(encoding="utf-8"),
    )
