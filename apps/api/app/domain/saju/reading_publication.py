"""Publish supplied readings; never derive a fortune verdict or event window.

The legacy report and calculation information stay intact. This projection owns
plain wording, conclusion order and folded technical material only.
"""
import re

from app.domain.saju.question_schemas import PublishedChapter, PublishedReadingBlock
from app.domain.saju.reading_information import load_information_catalog


PUBLICATION_VERSION = "reading-publication-2026-10-23.1"
PLAIN_TERMS = {
    "일간": "사주를 읽는 기준 글자", "십성": "글자 사이의 관계", "지장간": "안쪽에 든 글자",
    "재성": "돈과 보상의 표시", "관성": "책임과 평가의 표시", "인성": "배움과 도움의 표시",
    "식상": "만들고 표현하는 표시", "비겁": "동료와 경쟁의 표시", "신살": "전통적인 보조 표시",
    "정재": "재산과 보상의 표시", "편재": "거래와 자원 운용의 표시",
    "정관": "역할과 기준의 표시", "편관": "부담과 책임의 표시",
    "정인": "배움과 지원의 표시", "편인": "탐구와 준비의 표시",
    "식신": "만들고 생산하는 표시", "상관": "표현과 변화의 표시",
    "비견": "동료와 자기 몫의 표시", "겁재": "경쟁과 나눠 갖는 몫의 표시",
    "배우자궁": "관계를 읽는 자리", "대운": "긴 운의 구간", "세운": "해마다 들어오는 운",
    "월운": "달마다 들어오는 운", "천간": "위쪽 글자", "지지": "아래쪽 글자",
}
TERM_RE = re.compile(r"(?<![가-힣])(" + "|".join(sorted(PLAIN_TERMS, key=len, reverse=True)) +
                     r")(?=$|[\s·,.;:()\[\]‘’'\"]|은|는|이|가|을|를|의|와|과|에|로|으|도|만)")
TECHNICAL_PROSE_RE = re.compile(
    r"[一-龥]|월령|신강|신약|격국|용신|희신|기신|조후|통근|투간|월간|월지|연간|연지|년간|년지|일지|시지|시주|일주|삼합|육합|형충|합충|"
    r"\b(?:day master|ten[- ]gods?|hidden stems?|month stem|month branch|spouse palace)\b", re.IGNORECASE)
STAR_TITLES = {
    "hamji": ("사람들의 시선이 머무는 표시", "A symbol of social attention"),
    "wangji": ("사람들의 관심과 연결되는 표시", "A symbol of attention and connection"),
    "mokyok": ("인연과 감정 표현의 표시", "A symbol of connection and expression"),
    "hongyeom": ("이성의 관심과 연결되는 표시", "A symbol of romantic attention"),
    "cheoneul": ("막힐 때 도움을 뜻하는 표시", "A traditional symbol of help"),
    "woldeok": ("어려움을 누그러뜨리는 표시", "A traditional symbol of relief"),
    "cheondeok": ("보호와 완화를 뜻하는 표시", "A traditional symbol of protection"),
    "munchang": ("글과 배움에 연결되는 표시", "A symbol of writing and learning"),
    "munguok": ("예술과 표현에 연결되는 표시", "A symbol of art and expression"),
    "taegeuk": ("깊이 배우고 탐구하는 표시", "A symbol of deep study"),
    "yeokma": ("이동과 변화에 연결되는 표시", "A symbol of movement and change"),
    "hwagae": ("깊이 파는 힘, 함께 따라오는 고독", "Depth of study, with a solitude theme"),
    "jangseong": ("역할과 권한에 연결되는 표시", "A symbol of roles and authority"),
    "hakdang": ("배움에 연결되는 표시", "A symbol of learning"),
    "sagwan": ("공적인 역할에 연결되는 표시", "A symbol of public roles"),
    "yangin": ("밀어붙이는 힘과 압박의 표시", "A symbol of drive and pressure"),
    "gwaegang": ("단단함과 결단을 읽는 표시", "A symbol of resolve and decisiveness"),
    "gongmang": ("기대와 체감 사이의 빈틈", "A traditional symbol of gaps and delays"),
    "wonjin": ("관계에서 감정이 엇갈리는 표시", "A symbol of emotional friction"),
    "gwimungwan": ("몰입과 집착, 양쪽을 함께 읽는 표시", "A symbol of focus and fixation"),
    "hyeonchim": ("날카로움에 연결되는 표시", "A traditional sharpness symbol"),
    "baekho_classic": ("사주에서 확인된 전통 표시", "A traditional symbol in this chart"),
    "gojin": ("관계에서 거리를 뜻하는 표시", "A traditional symbol of distance"),
    "guasuk": ("고독과 거리를 뜻하는 표시", "A traditional symbol of solitude"),
}
PLAIN_STAR_COPY = {
    "woldeok": "어려움을 누그러뜨리고 회복하는 쪽에 연결해 읽는 표시야.",
    "cheondeok": "난관이 누그러지는 것과 보호를 함께 뜻하는 표시야.",
    "munguok": "문학·예술·표현에 연결해 읽는 표시야.",
    "gwaegang": "단단함과 결단을 함께 뜻하는 표시야.",
    "cheonmun": "연구·분석·철학에 연결해 읽는 표시야.",
    "wangji": "사람들의 관심과 호감에 연결해 읽는 표시야. 여기서는 관계가 실제로 생겼다는 뜻보다, 사람들의 시선과 연결되는 전통적인 의미로 읽어.",
    "mokyok": "인연과 감정 표현을 함께 읽는 표시야. 연애 풀이에서 참고하지만, 인연이 들어오는 날짜를 뜻하는 표시는 아니야.",
    "hongyeom": "이성의 관심과 매력에 연결해 읽는 표시야. 사람들의 시선에 관한 다른 표시와는 찾는 기준이 달라서 따로 읽어.",
    "gongmang": "전통적으로 지연이나 기대와 체감의 차이, 효력이 약해지는 쪽에 연결해 읽어. 일이 바로 손에 잡히지 않는다는 상징이지, 돈이나 인연이 전부 사라진다는 뜻은 아니야.",
}
PLAIN_STAR_COPY_EN = {
    "wangji": "A traditional symbol of attention and attraction. It does not establish that a relationship exists.",
    "mokyok": "A traditional symbol of emotional expression and social attention. It does not specify when a relationship will begin.",
    "hongyeom": "A traditional symbol associated with romantic attention and attraction.",
    "woldeok": "A traditional symbol of relief from difficulty and recovery.",
    "cheondeok": "A traditional symbol of protection and relief from difficulty.",
    "munguok": "A traditional symbol associated with literature, art and expression.",
    "gwaegang": "A traditional symbol of resolve and decisiveness.",
    "gongmang": "Traditionally associated with gaps, delays and a difference between expectation and experience. It does not establish the loss of money or a relationship.",
    "cheonmun": "A traditional symbol associated with research, analysis and philosophy.",
}


def plain_wording(text, locale):
    # Replace terms, never substring matches such as '상관없이'. Keep originals in memo.
    if locale != "ko":
        text = re.sub(r"\bvisible stem position(s?)\b", r"visible position\1", text, flags=re.IGNORECASE)
        text = re.sub(r"\bhidden stems? position(s?)\b", r"inner position\1", text, flags=re.IGNORECASE)
        return re.sub(r"\bhidden stems?\b", "inner characters", text, flags=re.IGNORECASE)
    return TERM_RE.sub(lambda match: PLAIN_TERMS[match.group(1)], text)


def model_main_parts(body, locale):
    """Apply exactly the same main/memo projection for validation and display."""
    body = re.sub(r"(?m)^#{1,6}\s+(핵심 결론|쉽게 풀어보면|조언|Core conclusion|Plain reading|Advice)\s*\n?", "", body)
    main, memo = [], []
    for part in re.split(r"\n\s*\n", body):
        part = part.strip()
        if not part:
            continue
        plain = plain_wording(part, locale)
        (memo if TECHNICAL_PROSE_RE.search(plain) else main).append(part if TECHNICAL_PROSE_RE.search(plain) else plain)
    return main, memo


def publish_chapter(*, section, report, locale, calculation_memo="", distinctive=None, natal=None):
    ko = locale == "ko"
    opening = []
    if section.id == "core" and natal is not None and natal.status in {"available", "conditional"}:
        # The existing selected conclusion owns the metaphor and its evidence.
        # Do not infer a personality, success guarantee or whole-chart verdict.
        primary = next((c for c in natal.conclusions if c.id == "primary_with_support"), None)
        if primary is not None and primary.one_line:
            prefix = ("선택한 명식으로 보면, " if ko else "Under the selected chart, ") if natal.status == "conditional" else ""
            opening = [PublishedReadingBlock(id="natal.one_line", kind="structural_reading",
                text="**" + prefix + primary.one_line + "**")]
    from app.domain.saju.publication_writing import WRITING_VERSION
    if (report is not None and report.provider in {"openai", "codex"}
            and getattr(report, "publication_writing_version", None) == WRITING_VERSION
            and natal is not None and natal.status == "available"
            and section.status != "blocked_calculation"):
        # Only this validated, server-selected expression contract can replace
        # deterministic prose. Legacy arbitrary provider text keeps its guards.
        main, extra_memo = model_main_parts(section.body, locale)
        blocks = opening + [PublishedReadingBlock(id=f"model.{index}",
            kind="structural_reading" if section.id == "core" else
                 "calculation_summary" if section.id == "wealth" else "interpretation", text=part)
            for index, part in enumerate(main)]
        applied_memos = ([natal.memo_body] if section.id == "core" else [])
        if distinctive is not None:
            applied_memos.extend(t.memo_body for t in distinctive.themes if t.category == section.id)
        return PublishedChapter(version=PUBLICATION_VERSION,
            scope="natal_structure" if section.id == "core" else
                  "calculation_information" if section.id == "wealth" else "supported_reading_excerpt",
            blocks=blocks,
            memo_body="\n\n".join(p for p in [section.memo_body, *applied_memos, calculation_memo, *extra_memo] if p),
            notice=("돈과 관련된 구조의 뜻을 읽은 내용이야. 수입·축적·손실의 길흉 판정은 포함하지 않았어." if ko else
                    "This explains money-related chart meanings, without an earning, saving or loss verdict.") if section.id == "wealth" else "")
    if section.id == "core" and natal is not None and natal.status in {"available", "conditional"}:
        # Structural rules own the main narrative. A brief eligible theme context
        # connects its actual follow-ups without a standalone glossary heading.
        memo = [natal.memo_body]
        selected = natal.conclusions or natal.blocks  # Compatibility for saved/older natal contracts.
        blocks = opening + [PublishedReadingBlock(id="natal." + b.id, kind="structural_reading", title=b.title, text=b.text)
                  for b in selected]
        if distinctive is not None:
            memo.extend(t.memo_body for t in distinctive.themes if t.category == "core")
            from app.domain.saju.distinctive_reading import catalog
            rules = {r["id"]: r for r in catalog()["rules"]}
            for theme in distinctive.themes:
                if theme.category != "core" or not theme.question_ids:
                    continue
                context = rules.get(theme.rule_id, {}).get("reading_context", {}).get(locale)
                if context:
                    blocks.append(PublishedReadingBlock(id="theme.context." + theme.id,
                        kind="traditional_theme", text=context))
        return PublishedChapter(version=PUBLICATION_VERSION,
            scope="conditional_natal_structure" if natal.status == "conditional" else "natal_structure",
            blocks=blocks,
            memo_body="\n\n".join(memo), notice=natal.assumption)
    # The legacy memo already appends information-only memos. Reconstruct that
    # tail once with its complete fact/definition text instead of repeating it.
    information_tail = "\n\n".join(f"### {item.title}\n{item.memo_body}" for item in section.information)
    base_memo = section.memo_body
    if information_tail and base_memo.endswith(information_tail):
        base_memo = base_memo[:-len(information_tail)].strip()
    themes = [t for t in distinctive.themes if t.category == section.id] if distinctive is not None else []
    if section.id == "core" and natal is not None:
        # Missing structural inputs must not silently restore a star-only core.
        themes = []
    blocks, memo = [], ([] if section.id == "core" or themes else [base_memo])
    if calculation_memo and not themes:
        memo.append(calculation_memo)
    technical = [f"### {item.title}\n{item.body}\n\n{item.memo_body}" for item in section.information]
    # A selected theme owns its actual evidence. Unapplied legacy definitions
    # can use a different source tradition and must not masquerade as its basis.
    if not themes:
        memo.extend(technical)
    for theme in themes:
        blocks.append(PublishedReadingBlock(id="theme." + theme.id, kind="traditional_theme", title=theme.title, text=theme.body))
        memo.append(theme.memo_body)
    if section.id == "core" and distinctive is not None and distinctive.comparisons:
        from app.domain.saju.distinctive_reading import comparison_memo
        memo.append(comparison_memo(distinctive, locale))
    if not themes and section.status != "blocked_calculation":
        # The active core rule catalog still supplies element/personality themes.
        # Preserve the legacy response, but do not publish rejected themes as
        # natal fortune, including inside a supposedly technical memo.
        if section.id != "core":
            body = section.body
            # The money body is already factual, not a wealth verdict.
            body = re.sub(r"(?m)^#{1,6}\s+(쉽게 풀어보면|조언|Plain reading|Advice)\s*\n?", "", body)
            for index, part in enumerate(re.split(r"\n\s*\n", body)):
                part = part.strip()
                if not part:
                    continue
                if TECHNICAL_PROSE_RE.search(plain_wording(part, locale)):
                    memo.append(part)
                    continue
                if part.startswith("#"):
                    # Preserve useful headings but omit compatibility labels.
                    heading, _, remainder = part.partition("\n")
                    heading = re.sub(r"^#{1,6}\s+", "", heading)
                    blocks.append(PublishedReadingBlock(id=f"heading.{index}", kind="heading", text=plain_wording(heading, locale)))
                    if remainder.strip():
                        blocks.append(PublishedReadingBlock(id=f"reading.{index}", kind=("calculation_summary" if section.status == "needs_rule_review" else "interpretation"), text=plain_wording(remainder, locale)))
                else:
                    blocks.append(PublishedReadingBlock(id=f"reading.{index}", kind=("calculation_summary" if section.status == "needs_rule_review" else "interpretation"), text=plain_wording(part, locale)))
    entries = {entry["id"]: entry for entry in load_information_catalog()["entries"]}
    for item in section.information:
        # Actual category responses now select supported contextual themes.
        # Keep all detected glossary data in the memo, never an automatic list.
        # None is reserved for backwards-compatible callers of this projection.
        if distinctive is not None:
            continue
        if item.kind != "traditional_term_definition":
            continue
        star_id = item.id.split(".", 1)[-1]
        entry = entries.get(star_id)
        if entry is None:
            continue
        # These entries describe a calculation label but supply no personal
        # meaning beyond a prohibition on accident/illness predictions.
        # Preserve their actual matches in the memo rather than pad the reading.
        if star_id in {"hyeonchim", "baekho_classic", "baekho_modern"}:
            continue
        title = STAR_TITLES.get(star_id, ("사주에서 확인된 보조 표시", "A traditional symbol in this chart"))[0 if ko else 1]
        meaning = plain_wording((PLAIN_STAR_COPY if ko else PLAIN_STAR_COPY_EN).get(star_id, entry["meaning_" + locale]), locale)
        if ko:
            for name in sorted({e["ko"] for e in entries.values()}, key=len, reverse=True):
                meaning = meaning.replace(name, "이 표시")
        if re.search(r"[一-龥]", meaning):
            continue
        blocks.append(PublishedReadingBlock(id=item.id, kind="traditional_definition", title=title, text=meaning))
    if section.id == "luck_flow":
        for item in section.information:
            if item.id in {"cycle.current", "cycle.next", "cycle.comparison"}:
                blocks.append(PublishedReadingBlock(id=item.id, kind="calculation_summary",
                    title=(("지금 지나가는 구간" if item.id == "cycle.current" else "다음 구간") if ko else
                           ("Current period" if item.id == "cycle.current" else "Next period")) if item.id != "cycle.comparison" else item.title,
                    text=plain_wording(item.body, locale)))
    if not blocks:
        message = ("계산 기준이 달라지는 부분이 있어 이 분야의 종합 풀이는 보류했어." if ko else
                   "This chapter's interpretation is withheld because the calculation is uncertain.") if section.status == "blocked_calculation" else (
                   "현재 자료로 이 분야의 좋고 나쁨을 판단할 만큼 충분한 풀이가 나오지 않았어." if ko else
                   "The supplied rules do not support a favorable or adverse conclusion for this chapter yet.")
        blocks.append(PublishedReadingBlock(id="availability", kind="availability_notice", text=message))
    kinds = {block.kind for block in blocks}
    scope = (("conditional_traditional_themes" if distinctive.status == "conditional" else "traditional_themes") if themes else
             "provisional_information" if section.status == "blocked_calculation" else
             "supported_reading_excerpt" if "interpretation" in kinds else
             "calculation_information" if "calculation_summary" in kinds else
             "traditional_information" if "traditional_definition" in kinds else "unavailable")
    notice = (distinctive.assumption if themes and distinctive.status == "conditional" else
              "" if themes else
              ("선택한 기준의 잠정 정보야. 이 분야의 해석은 보류 중이야." if ko else
              "Provisional information under the selected convention; this chapter's interpretation is withheld.") if section.status == "blocked_calculation" else (
              "현재는 돈과 관련된 표시만 확인할 수 있어. 벌고 모으는 운의 좋고 나쁨을 판정한 결과는 아니야." if ko else
              "Only money-related chart symbols are available here; this is not a favorable or adverse money verdict.") if section.status == "needs_rule_review" else "")
    return PublishedChapter(version=PUBLICATION_VERSION, scope=scope, blocks=blocks,
        memo_body="\n\n".join(dict.fromkeys(part.strip() for part in memo if part.strip())),
        notice=notice)
