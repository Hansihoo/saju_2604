import { Locale } from "../../shared/copy";

const STEM_MAP: Record<string, { ko: string; en: string }> = {
  甲: { ko: "갑", en: "Gap" },
  乙: { ko: "을", en: "Eul" },
  丙: { ko: "병", en: "Byeong" },
  丁: { ko: "정", en: "Jeong" },
  戊: { ko: "무", en: "Mu" },
  己: { ko: "기", en: "Gi" },
  庚: { ko: "경", en: "Gyeong" },
  辛: { ko: "신", en: "Sin" },
  壬: { ko: "임", en: "Im" },
  癸: { ko: "계", en: "Gye" },
};

const BRANCH_MAP: Record<string, { ko: string; en: string }> = {
  子: { ko: "자", en: "Ja" },
  丑: { ko: "축", en: "Chuk" },
  寅: { ko: "인", en: "In" },
  卯: { ko: "묘", en: "Myo" },
  辰: { ko: "진", en: "Jin" },
  巳: { ko: "사", en: "Sa" },
  午: { ko: "오", en: "O" },
  未: { ko: "미", en: "Mi" },
  申: { ko: "신", en: "Sin" },
  酉: { ko: "유", en: "Yu" },
  戌: { ko: "술", en: "Sul" },
  亥: { ko: "해", en: "Hae" },
};

function isHanCharacter(char: string): boolean {
  const codePoint = char.codePointAt(0);
  if (!codePoint) {
    return false;
  }

  return (
    (codePoint >= 0x3400 && codePoint <= 0x4dbf) ||
    (codePoint >= 0x4e00 && codePoint <= 0x9fff) ||
    (codePoint >= 0xf900 && codePoint <= 0xfaff)
  );
}

function shouldFormatAsGanZhi(value: string): boolean {
  let hasGanZhiChar = false;

  for (const char of value) {
    if (STEM_MAP[char] || BRANCH_MAP[char]) {
      hasGanZhiChar = true;
      continue;
    }

    if (isHanCharacter(char)) {
      return false;
    }
  }

  return hasGanZhiChar;
}

function convertGanZhi(value: string, locale: Locale): string {
  if (value.length >= 2 && STEM_MAP[value[0]] && BRANCH_MAP[value[1]]) {
    const stem = STEM_MAP[value[0]][locale];
    const branch = BRANCH_MAP[value[1]][locale];
    return locale === "ko" ? `${stem}${branch}` : `${stem}-${branch}`;
  }

  let converted = "";
  let changed = false;
  for (const char of value) {
    const mapped = STEM_MAP[char]?.[locale] ?? BRANCH_MAP[char]?.[locale];
    if (mapped) {
      converted += mapped;
      changed = true;
    } else {
      converted += char;
    }
  }

  return changed ? converted : value;
}

export function formatManseText(value: string | null | undefined, locale: Locale): string {
  if (!value) {
    return "-";
  }

  if (!shouldFormatAsGanZhi(value)) {
    return value;
  }

  return convertGanZhi(value, locale);
}

export function formatManseList(values: string[], locale: Locale): string {
  if (!values.length) {
    return "-";
  }

  return values.map((value) => formatManseText(value, locale)).join(", ");
}

export function formatManseJsonValue(value: unknown, locale: Locale): unknown {
  if (typeof value === "string") {
    return formatManseText(value, locale);
  }

  if (Array.isArray(value)) {
    return value.map((item) => formatManseJsonValue(item, locale));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        formatManseJsonValue(item, locale),
      ]),
    );
  }

  return value;
}
