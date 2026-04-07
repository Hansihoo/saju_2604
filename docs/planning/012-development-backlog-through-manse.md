# Development Backlog Through Manse 012

## 목적
- 현재 프로젝트의 개발 상태를 다시 정리한다.
- `만세력 계산과 검증`까지를 현재 핵심 마일스톤으로 둔다.
- `LLM 기반 사주풀이`는 다음 마일스톤으로 분리한다.
- 다음에 프로젝트를 다시 열어도 무엇부터 해야 하는지 바로 알 수 있게 만든다.

## 현재 기준 결론
- 사주 4주(year/month/day/time)는 golden 정답 케이스와 모두 일치한다.
- 12신살은 현재 정답지 기준과 맞췄다.
- 현재 가장 큰 남은 이슈는 `대운(luck_cycles)`이다.
- 지역 `{지역, 경도}` 데이터는 아직 하드코딩/정적 데이터셋 기반으로 운영한다.
- LLM 해석은 아직 시작하지 않는다.

## 지금부터의 작업 순서
1. `대운(luck_cycles)` 규칙을 정답지 기준으로 맞춘다.
2. `corrected_datetime`, `regional_time_offset_minutes` 같은 지역 보정 표시 규칙을 정리한다.
3. 현재 하드코딩 지역 데이터 구조를 공식 데이터셋으로 교체 가능한 형태로 고정한다.
4. 사용자 결과 화면에 만세력 표를 붙이고, 개발자 화면에는 raw JSON과 diff 확인 흐름을 유지한다.
5. 위 4개가 안정화되면 `M1. 만세력 계산과 검증 완료`로 닫는다.
6. 그 다음에만 `M2. LLM 기반 사주풀이`로 넘어간다.

## 현재 구현 상태

### 완료
- 프론트/백엔드 monorepo 구조 정리
- 사용자 화면과 개발자 화면 분리
- 입력 폼, 지역 자동완성, 기본 검증
- 시간 보정 기본 흐름
- 양력/음력 정규화
- `lunar-python` 기반 사주 계산 adapter
- 만세력 기본 스키마
- 경도 기반 지역시 보정 반영
- 정답지 txt -> canonical JSON 변환 도구
- 실제 출력 -> canonical JSON 추출 도구
- golden diff 리포트 시스템
- 사주 4주 일치 검증
- 12신살 검증

### 부분 완료
- 지역 데이터셋
  - 한국 주요 지역은 들어가 있음
  - 공식 기준 데이터셋으로 확정되지는 않음
- 지역시 보정
  - 경도 기반 보정은 붙음
  - 일부 표시 규칙은 정답지와 1분 차이 가능
- 만세력 결과 화면
  - API와 개발 검증용 구조는 있음
  - 사용자 화면에서 만세력 전체 표를 완성도 높게 보여주지는 않음

### 미완료
- 대운 규칙 완전 일치
- 지역 데이터 공식화
- 만세력 사용자 결과 화면 고도화
- LLM 기반 사주풀이
- 운영용 CI에 golden validation 고정 편입

## 최신 검증 상태
- 기준 문서: [016-golden-answer-validation-system.md](/D:/5_project/SaJu(2)/docs/planning/016-golden-answer-validation-system.md)
- 최신 golden validation 기준:
  - 총 mismatch: `42`
  - 사주 4주 mismatch: `0`
  - 12신살 mismatch: `0`
  - 남은 주요 mismatch: `luck_cycles`
  - 자동 진단:
    - `regional_display_rounding_mismatch`: `1`
    - `luck_cycle_progression_rule_mismatch`: `3`
    - `expected_luck_cycle_unparseable`: `2`
    - `expected_luck_cycle_tail_anomaly`: `1`
- 진행 로그: [003-m1-manse-progress-log.md](/D:/5_project/SaJu(2)/docs/delivery/003-m1-manse-progress-log.md)

## 현재 남은 핵심 업무 우선순위

### 1. 대운 규칙 정리
상태: 진행 중

해야 할 일:
- `luck_cycles.start_age` 규칙을 정답지 기준으로 확정
- `luck_cycles.gan_zhi`, `luck_cycles.branch`가 어긋나는 케이스 원인 확인
- `aru`, `gomaebi`처럼 정답지 자체에 비표준 60갑자 표기가 포함된 케이스를 별도로 분석
- `pororo` 마지막 대운 `신축` 표기가 표준 규칙과 왜 다른지 확인

현재 메모:
- `lunar-python` 기본 `DaYun` 규칙은 월주 기준 순행/역행으로 간지를 이동한다.
- 기본 `getDaYun()`은 빈 `index=0`을 포함한 10개를 반환해 실제 표시용으로는 9칸만 남는다.
- 현재 프로젝트는 `n=11`로 늘리고 빈 `index=0`을 숨겨 10칸을 비교할 수 있게 바꿨다.
- 그 결과 `lee-hyeonjin`, `okji`는 해결됐고, `aru`, `gomaebi`, `pororo`만 규칙 차이로 남았다.
- golden 비교기는 이제 `expected_luck_cycle_unparseable`과 `expected_luck_cycle_tail_anomaly`도 자동으로 식별한다.
- 현재 `aru`, `gomaebi`는 엔진 오차 이전에 정답지 대운 간지 중 일부가 표준 60갑자로 파싱되지 않는 상태다.

완료 기준:
- golden summary에서 남은 mismatch가 대운 기준으로 더 줄어듦
- 최소 5개 정답 케이스에서 대운 규칙이 설명 가능해야 함

검증:
- `python -m app.tools.run_golden_validation`
- `apps/api/tests/golden_reports/latest/summary.json`
- 케이스별 `diff/*.report.json`

### 2. 지역 보정 표시 규칙 정리
상태: 진행 중

해야 할 일:
- `corrected_datetime`
- `regional_time_offset_minutes`
표시 규칙을 정답지와 맞출지, 내부 계산값과 분리할지 결정

완료 기준:
- `basic_info.corrected_datetime`
- `basic_info.regional_time_offset_minutes`
남은 오차를 정책적으로 설명 가능

검증:
- golden diff 비교
- 대표 지역 샘플 수기 검토

### 3. 지역 데이터셋 공식화 준비
상태: 미완료

해야 할 일:
- 현재 정적 CSV 구조 유지
- 추후 공식 데이터 전환 가능한 필드 구조 유지
- `{id, province, city, tzid, longitude, aliases}`를 기준 구조로 확정

완료 기준:
- 지역 검색과 시간 보정이 같은 데이터 구조를 사용
- 나중에 공식 소스로 교체해도 서비스 코드 수정이 최소화됨

검증:
- 지역 검색 테스트
- 지역 선택 후 계산 파이프라인 테스트

### 4. 만세력 결과 화면 정리
상태: 미완료

해야 할 일:
- 사용자 결과 화면에 만세력 표를 어떤 위계로 보여줄지 정리
- 요약과 raw 만세력 표를 분리
- 개발자 화면에서는 raw JSON과 diff를 쉽게 볼 수 있게 유지

완료 기준:
- 사용자가 사주 4주, 오행, 대운을 확인 가능
- 개발자는 같은 데이터의 raw 구조를 바로 점검 가능

검증:
- 프런트 빌드
- 브라우저 수동 확인
- API 응답 구조 확인

## 이번 마일스톤 완료 조건

### 마일스톤 이름
- `M1. 만세력 계산과 검증 완료`

### 완료로 보는 조건
- 입력 -> 시간 보정 -> 사주 계산 -> 만세력 생성이 안정적으로 동작
- 사주 4주가 golden 정답과 일치
- 12신살이 golden 정답과 일치
- 대운 오차가 허용 가능한 수준까지 줄거나, 남은 차이에 대한 규칙 설명이 문서화됨
- golden validation 도구로 회귀 검증 가능

## 다음 마일스톤

### M2. LLM 기반 사주풀이
- 만세력과 분석 엔진 결과를 입력으로 사용
- LLM은 판단이 아니라 표현만 담당
- 출력:
  - 전체 흐름
  - 강점
  - 주의
  - 연애
  - 직업
  - 금전
  - 행동 조언

### M2 시작 조건
- 만세력 응답 구조 안정화
- 대운 규칙 정리
- 점수/등급/근거 구조 정리
- golden validation 기반 회귀 검증 체계 유지

## 지금 바로 해야 할 일
1. `aru`, `gomaebi` 정답지 대운표의 비표준 간지 표기 확인
2. `pororo` 마지막 대운 `신축` 표기가 규칙 차이인지 정답지 이상인지 확인
3. 지역 보정 표시 규칙 결정
4. 사용자 결과 화면에 만세력 표 초안 반영

## 참고 문서
- [005-development-phases-and-test-strategy.md](/D:/5_project/SaJu(2)/docs/planning/005-development-phases-and-test-strategy.md)
- [007-engine-selection-and-calculation-strategy.md](/D:/5_project/SaJu(2)/docs/planning/007-engine-selection-and-calculation-strategy.md)
- [008-detailed-development-execution-and-diagnostics.md](/D:/5_project/SaJu(2)/docs/planning/008-detailed-development-execution-and-diagnostics.md)
- [009-development-rules-and-maintainability-guide.md](/D:/5_project/SaJu(2)/docs/planning/009-development-rules-and-maintainability-guide.md)
- [013-manse-data-source-mapping.md](/D:/5_project/SaJu(2)/docs/planning/013-manse-data-source-mapping.md)
- [014-manse-schema.md](/D:/5_project/SaJu(2)/docs/planning/014-manse-schema.md)
- [015-region-longitude-and-solar-time-application.md](/D:/5_project/SaJu(2)/docs/planning/015-region-longitude-and-solar-time-application.md)
- [016-golden-answer-validation-system.md](/D:/5_project/SaJu(2)/docs/planning/016-golden-answer-validation-system.md)
