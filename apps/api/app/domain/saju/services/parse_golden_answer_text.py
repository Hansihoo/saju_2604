from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional

from app.domain.saju.golden import (
    GoldenBasicInfo,
    GoldenCaseInput,
    GoldenLuckCycleHeader,
    GoldenKnownAnswerCase,
    GoldenLuckCycleRow,
    GoldenPillarRow,
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


def _trim_primary_text(text: str) -> str:
    return text.split("```", 1)[0]


def _clean_markdown_cell(value: str) -> str:
    cleaned = re.sub(r"[*`_\\]", "", value)
    return re.sub(r"\s+", " ", cleaned).strip()


def _split_sections(text: str) -> Dict[str, str]:
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
    match = DATE_TIME_PATTERN.search(value)
    if not match:
        raise ValueError(f"Could not parse datetime from: {value}")
    year, month, day, time_value = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d} {time_value}"


def _parse_birth_info(value: str) -> Dict[str, object]:
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
    for region in load_region_records():
        if region.display_name == birth_place or region.city == birth_place:
            return region.id
    raise ValueError(f"Could not resolve region_id for birth place: {birth_place}")


def _parse_basic_info(section_text: str) -> Dict[str, object]:
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
    match = LUCK_CYCLE_HEADER_PATTERN.search(section_title)
    if not match:
        return None
    start_age_text, reference_pillar = match.groups()
    return GoldenLuckCycleHeader(
        start_age=int(start_age_text),
        reference_pillar=to_korean_gan_zhi(reference_pillar),
    )


def parse_golden_answer_text(
    *,
    case_id: str,
    source_name: str,
    source_file: str,
    text: str,
) -> GoldenKnownAnswerCase:
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

    unsupported_sections = [
        title
        for title in sections
        if title not in {"\uae30\ubcf8\uc815\ubcf4", "\ucc9c\uac04\uacfc \uc9c0\uc9c0"}
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
        ),
        supported_sections=list(SUPPORTED_GOLDEN_SECTIONS),
        unsupported_sections=unsupported_sections,
        raw_sections={title: sections[title] for title in unsupported_sections},
    )


def load_golden_answer_text(path: Path, *, case_id: str, source_name: str) -> GoldenKnownAnswerCase:
    return parse_golden_answer_text(
        case_id=case_id,
        source_name=source_name,
        source_file=path.name,
        text=path.read_text(encoding="utf-8"),
    )
