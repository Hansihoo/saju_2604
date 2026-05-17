# Manse Schema 014

## 목적
- M1 단계에서 사용할 `만세력 응답 스키마`를 확정한다.
- 백엔드와 프런트가 같은 구조를 기준으로 구현되도록 한다.
- 시간 미상 정책까지 포함한 API 계약을 문서로 남긴다.

## 설계 원칙
- 스키마는 `명시형`으로 유지한다.
- 고정 키가 있는 영역은 `dict` 대신 `명시된 객체`를 사용한다.
- 사용자용 화면에 필요한 필드와 개발 검증에 필요한 필드를 같이 담되, LLM 해석 문장은 포함하지 않는다.
- 시간 미상일 때는 내부 계산과 사용자 노출을 분리한다.

## 최상위 구조

```json
{
  "trace_id": "string",
  "pipeline_status": {},
  "region": {},
  "time_correction": {},
  "calendar_normalization": {},
  "manse": {},
  "result": {},
  "debug_trace": {}
}
```

`manse`는 LLM 이전 단계에서 검증 가능한 “계산 결과 자체”를 뜻한다.

## `manse` 스키마

```json
{
  "meta": {
    "schema_version": "v1",
    "day_master": "갑",
    "pillar_order": ["year", "month", "day", "time"],
    "visible_pillar_keys": ["year", "month", "day", "time"],
    "hour_pillar_enabled": true
  },
  "pillars": {
    "year": {},
    "month": {},
    "day": {},
    "time": {}
  },
  "table_rows": [],
  "elements": {
    "wood": 0,
    "fire": 0,
    "earth": 0,
    "metal": 0,
    "water": 0
  },
  "luck_cycles_enabled": true,
  "luck_cycles": [],
  "supplementary_positions": {
    "tai_yuan": {},
    "ming_gong": {},
    "shen_gong": {},
    "tai_xi": {}
  },
  "notes": []
}
```

## `meta`

### 필드
- `schema_version`
  - 현재 고정값: `v1`
- `day_master`
  - 일간
- `pillar_order`
  - 표와 UI에서 기둥을 어떤 순서로 보여줄지 정의
- `visible_pillar_keys`
  - 현재 사용자에게 보여줄 수 있는 기둥 목록
- `hour_pillar_enabled`
  - 시주 노출 가능 여부

## `pillars`

`year`, `month`, `day`, `time`는 고정 키다.

### 각 기둥 객체 구조

```json
{
  "key": "year",
  "label": "년주",
  "enabled": true,
  "gan_zhi": "갑진",
  "stem": "갑",
  "branch": "진",
  "stem_element": "목",
  "branch_element": "토",
  "stem_ten_god": "비견",
  "branch_ten_god": "편재",
  "branch_ten_gods": ["편재", "정관", "상관"],
  "hidden_stems": ["무", "을", "계"],
  "twelve_fortune": "쇠",
  "twelve_shinsal": "화개",
  "na_yin": "복등화",
  "xun": "갑자",
  "xun_kong": "인묘"
}
```

### 의미
- `enabled`
  - 시간 미상처럼 정책상 비활성화된 기둥인지 표시
- `branch_ten_god`
  - 지지 십성 대표값
- `branch_ten_gods`
  - 지지에 포함된 십성 전체 목록
- `hidden_stems`
  - 지장간
- `twelve_fortune`
  - 12운성
- `twelve_shinsal`
  - 12신살
- `na_yin`
  - 납음
- `xun`, `xun_kong`
  - 순, 공망

## `table_rows`

표 렌더링을 쉽게 하기 위한 전개형 구조다.

```json
{
  "label": "천간",
  "year": "갑",
  "month": "병",
  "day": "갑",
  "time": "기"
}
```

### 기본 행 목록
- 천간
- 천간 십성
- 지지
- 지지 십성
- 지장간
- 12운성
- 12신살
- 납음
- 공망

## `elements`

오행 카운트는 고정 키를 사용한다.

```json
{
  "wood": 3,
  "fire": 2,
  "earth": 3,
  "metal": 0,
  "water": 0
}
```

이 구조를 쓰는 이유:
- 프런트에서 차트나 막대를 그리기 쉽다.
- `dict[str, int]`보다 계약이 덜 흔들린다.

## `luck_cycles`

```json
{
  "index": 1,
  "gan_zhi": "정묘",
  "start_year": 2032,
  "end_year": 2041,
  "start_age": 9,
  "end_age": 18,
  "start_age_years": 8,
  "start_age_months": 7,
  "start_age_total_months": 103,
  "change_age_years": 18,
  "change_age_months": 7,
  "change_age_total_months": 223,
  "start_datetime": "2032-01-06 11:31:58",
  "change_datetime": "2042-01-05 21:39:38"
}
```

### 관련 필드
- `luck_cycles_enabled`
  - 시주 정책상 대운을 노출 가능한지 여부
- `start_age`
  - 하위 호환을 위해 유지하는 legacy 표시 나이
- `start_age_years`, `start_age_months`, `start_age_total_months`
  - `start_datetime` 기준의 완료 년/개월 나이. 반올림하지 않는다.
- `change_age_years`, `change_age_months`, `change_age_total_months`
  - `change_datetime` 기준의 다음 대운 교체 시점 완료 년/개월 나이. 반올림하지 않는다.

## `supplementary_positions`

고정 키:
- `tai_yuan`
- `ming_gong`
- `shen_gong`
- `tai_xi`

각 항목 구조:

```json
{
  "key": "tai_yuan",
  "label": "태원",
  "gan_zhi": "정사",
  "na_yin": "사중토"
}
```

## `notes`

사용자에게 보여줄 제한/정책 메모다.

예:

```json
[
  "출생시간 미상으로 시주와 시주 기반 대운 정보는 비활성화되었습니다."
]
```

## 시간 미상 규칙

### 내부 계산
- 입력값은 `00:00`으로 계산한다.

### 사용자 노출
- `meta.hour_pillar_enabled = false`
- `visible_pillar_keys = ["year", "month", "day"]`
- `pillars.time.enabled = false`
- `table_rows[*].time = ""`
- `luck_cycles_enabled = false`
- `luck_cycles = []`
- `notes`에 제한 문구 추가

## 현재 코드 반영 위치
- API 모델: [schemas.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/schemas.py)
- 만세력 조립: [build_manse.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/build_manse.py)
- 프런트 계약: [contracts.ts](D:/5_project/SaJu(2)/apps/web/src/shared/api/contracts.ts)

## 다음 작업
1. 사용자 결과 화면에 `table_rows`를 어떻게 보여줄지 정한다.
2. 대운 노출 범위를 전부 보여줄지 일부만 보여줄지 정한다.
3. `{지역, 경도}`가 준비되면 시간 보정 결과가 `meta`에 더 들어갈지 검토한다.
## 2026-04-09 Analysis Schema Addendum

The `manse` object now also includes an `analysis` block for deterministic summary values.

### Included fields
- `visible_element_total`
- `imbalance_gap`
- `element_percentages`
- `visible_ten_god_distribution`
- `balance_score`
- `internal_grade`
- `charm_score`
- `wealth_score`
- `career_score`
- `leadership_score`
- `first_luck_cycle_direction`
- `first_luck_cycle_exact_start_age_years`
- `first_luck_cycle_precise_start_age_years`
- `first_luck_cycle_boundary_datetime`

### Intent
- `elements` remains the raw count block.
- `analysis` becomes the reusable reasoning block for diagnostics and future interpretation.
