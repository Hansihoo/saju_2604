# Development Backlog Through Manse 012

## 목적
- 현재 프로젝트의 남은 업무를 다시 정리한다.
- 다음 개발 마일스톤을 `만세력 계산 완료`로 한정한다.
- `LLM을 통한 사주풀이`는 그 다음 단계로 분리한다.
- 지금까지 진행한 구현 상태와 아직 끝나지 않은 개발 단계를 한 문서에서 볼 수 있게 만든다.

## 이번 정리의 핵심 결정
- 한국 지역 데이터는 당분간 `하드코딩된 정적 데이터셋`으로 운영한다.
- 지역 기반 보정은 추후 `{지역, 경도}` 데이터셋을 직접 수집한 뒤 붙인다.
- 현재 우선 목표는 `정확한 만세력 생성`이다.
- `LLM 요약/해석/사주풀이`는 만세력 완료 이후 별도 단계로 진행한다.

## 현재 구현 상태

### 완료된 것
- 프런트/백엔드 monorepo 구조 정리
- 사용자 화면과 개발자 화면 분리
- 입력 폼 기본 UX 구현
- 지역 자동완성 기본 흐름 구현
- `trace_id`, debug trace, pipeline status 구조 구현
- 시간 보정 기본 모듈 구현
- 양력/음력 정규화 기본 구현
- `lunar-python` 기반 사주 계산 adapter 연결
- 출생시간 미상 `00:00` 정책과 시주 비활성화 규칙 구현
- 기본 분석 엔진 골격 구현
- 백엔드 테스트와 프런트 빌드 검증 흐름 정리

### 부분 완료
- 지역 자동완성 데이터
  - 현재는 한국 주요 시 단위 정적 데이터로 운영 중
  - 검색 품질 개선 작업은 진행 중
  - 아직 공식 코드/좌표/경도 기준 데이터셋으로 확정되지 않음
- 시간 보정
  - `tzid` 기반의 일반 시간 보정은 있음
  - 지역 경도 기반 보정은 아직 없음
- 만세력 데이터
  - 엔진에서 가져오는 기본 값은 있음
  - 어떤 항목을 최종 만세력 출력 표준으로 삼을지 아직 확정되지 않음

### 아직 하지 않은 것
- `{지역, 경도}` 데이터셋 확정
- 지역 경도 기반 보정 로직
- 만세력 표준 응답 스키마 확정
- 만세력 전용 결과 화면
- 절기/경계 시각 golden test 확대
- LLM 기반 사주풀이

## 현재 기준으로 남아 있는 개발 단계

### 1. 지역 데이터 기준 확정
상태: 미완료

해야 할 일:
- 한국 MVP용 지역 데이터 구조 확정
- 필수 필드 정의
  - `id`
  - `display_name`
  - `province`
  - `city`
  - `tzid`
  - `longitude`
  - 필요시 `latitude`
  - `aliases`
- 초기 버전은 하드코딩 데이터로 운영
- 추후 공식 소스로 교체 가능한 구조 유지

완료 기준:
- 백엔드가 선택 가능한 지역을 정적 데이터로 안정적으로 제공
- 자동완성 검색과 계산 입력이 같은 데이터 모델을 사용

검증:
- region search unit test
- 대표 한글/영문 검색 테스트
- 선택 필수 validation 확인

## 2. 지역 기반 시간 보정 확장
상태: 미완료

해야 할 일:
- 현재 `tzid` 기반 보정 흐름에 `longitude` 보정 단계를 추가할 수 있게 설계
- 한국 MVP용 보정 공식 정의
- 추후 수집할 경도 데이터가 들어오면 바로 연결 가능하도록 인터페이스 분리

완료 기준:
- 시간 보정 단계가 `표준시 보정`과 `지역 경도 보정`을 구분해서 다룰 수 있음
- 경도 데이터가 없을 때와 있을 때 동작 규칙이 명확함

검증:
- 보정 함수 unit test
- 대표 지역 경도 샘플 비교
- debug trace에 보정 단계 기록 확인

## 3. 입력 정규화와 정책 고정
상태: 부분 완료

해야 할 일:
- `양력/음력`, `윤달`, `HH:mm`, `시간 모름`, `성별`, `지역 선택` 정책을 최종 고정
- 지역을 직접 입력 텍스트로 제출할 수 없도록 유지
- 출생시간 미상일 때 만세력 노출 규칙을 다시 점검

완료 기준:
- 입력 정책이 코드, 스키마, UI에서 모두 일치
- 잘못된 입력이 조용히 통과하지 않음

검증:
- schema test
- form validation test
- API integration test

## 4. 사주 계산 결과를 만세력 표준 구조로 정리
상태: 미완료

해야 할 일:
- 현재 엔진 결과를 그대로 넘기지 않고, 우리 서비스 표준 구조로 변환
- 최소 출력 항목 확정
  - 사주팔자
  - 천간/지지
  - 오행 분포
  - 십성
  - 대운
  - 메타 정보
- 출생시간 미상 시 비활성화되는 필드 정의

완료 기준:
- API가 일관된 만세력 응답을 반환
- 프런트가 엔진 구현 세부사항을 몰라도 렌더링 가능

검증:
- adapter unit test
- preview/manse response shape test
- golden sample 비교

## 5. 만세력 전용 API 응답 설계
상태: 미완료

해야 할 일:
- 현재 preview 응답에서 `사주 요약`과 `만세력 데이터`를 분리
- LLM 없이도 확인 가능한 응답 구조 설계
- 사용자용과 개발자용에서 각각 어떤 데이터를 볼지 정의

완료 기준:
- 만세력 데이터만으로도 값 검증이 가능
- 개발자 화면에서 raw 데이터 확인 가능
- 사용자 화면에서는 필요한 범위만 노출

검증:
- response schema test
- `/dev` 화면에서 구조 확인
- API 문서 검토

## 6. 만세력 결과 화면
상태: 미완료

해야 할 일:
- 사용자 화면에서 입력 후 만세력 중심 결과를 보여주는 화면 구성
- 우선순위:
  - 사주팔자
  - 오행
  - 십성
  - 대운
- 과한 해석 문장 없이 계산 결과 중심으로 보여주기

완료 기준:
- 사용자가 입력 후 만세력 데이터를 확인할 수 있음
- 시간 미상 시 비활성화 항목이 UI에서도 명확함

검증:
- 프런트 빌드
- 수동 브라우저 확인
- 입력 -> 결과 흐름 E2E 확인

## 7. 만세력 검증용 테스트 세트 확대
상태: 미완료

해야 할 일:
- 대표 샘플 케이스 수집
- 절기 경계 케이스 추가
- 자시 경계 케이스 추가
- 양력/음력/윤달 케이스 추가
- 지역별 대표 샘플 추가

완료 기준:
- 만세력 계산이 바뀌었을 때 회귀 여부를 바로 확인 가능
- 최소한의 한국 대표 샘플 세트가 있음

검증:
- golden test
- regression test
- 수동 비교 기록

## 이번 마일스톤의 완료 정의

### 마일스톤 이름
- `M1. 만세력 계산 완료`

### 완료로 보기 위한 조건
- 입력 폼에서 출생 정보를 넣을 수 있음
- 지역 선택이 안정적으로 동작함
- 시간 보정 단계가 파이프라인에 포함됨
- 양력/음력 정규화가 일관되게 동작함
- 사주팔자와 만세력 핵심 항목이 API에서 반환됨
- 만세력 결과를 사용자 화면에서 볼 수 있음
- 대표 golden test 세트가 존재함

### 아직 완료로 보지 않는 것
- 자연어 사주풀이
- LLM 요약/조언
- 고급 분석 문장
- 유료화/저장/질문 기능

## 마일스톤 이후 다음 단계

### M2. LLM 기반 사주풀이
- 만세력 데이터를 입력으로 사용
- LLM은 판단이 아니라 표현만 담당
- 출력 예:
  - 전체 흐름
  - 강점
  - 주의
  - 연애
  - 직업
  - 금전
  - 행동 조언

### M2 시작 전 선행 조건
- 만세력 응답 구조 확정
- 점수/등급/근거 구조 확정
- 비활성화 규칙 확정
- golden test로 계산 신뢰도 확보

## 당장 다음 작업 추천
1. 만세력 표준 응답 스키마 설계
2. 엔진 결과 -> 만세력 변환기 구현
3. 만세력 결과 화면 초안 구현
4. 지역/경도 데이터 하드코딩용 스키마 정의
5. golden test 케이스 1차 수집

## 참고 문서
- [005-development-phases-and-test-strategy.md](/D:/5_project/SaJu(2)/docs/planning/005-development-phases-and-test-strategy.md)
- [007-engine-selection-and-calculation-strategy.md](/D:/5_project/SaJu(2)/docs/planning/007-engine-selection-and-calculation-strategy.md)
- [008-detailed-development-execution-and-diagnostics.md](/D:/5_project/SaJu(2)/docs/planning/008-detailed-development-execution-and-diagnostics.md)
- [009-development-rules-and-maintainability-guide.md](/D:/5_project/SaJu(2)/docs/planning/009-development-rules-and-maintainability-guide.md)
- [011-region-data-sources-and-korean-search.md](/D:/5_project/SaJu(2)/docs/planning/011-region-data-sources-and-korean-search.md)
- [013-manse-data-source-mapping.md](/D:/5_project/SaJu(2)/docs/planning/013-manse-data-source-mapping.md)
- [014-manse-schema.md](/D:/5_project/SaJu(2)/docs/planning/014-manse-schema.md)
