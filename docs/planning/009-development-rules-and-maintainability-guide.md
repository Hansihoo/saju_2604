# Development Rules And Maintainability Guide 009

## 목적
- 이 문서는 사주 서비스의 코드 구조를 오래 유지보수 가능한 형태로 고정하기 위한 기준 문서다.
- 구현이 늘어나도 어디에 어떤 책임을 둬야 하는지 빠르게 판단할 수 있도록 한다.
- 특히 프론트, 백엔드, 계산 엔진, 디버그 흐름이 섞이지 않게 만드는 것이 목표다.

## 핵심 원칙
- 계산과 판단은 백엔드에서만 한다.
- 프론트는 입력, 상태 표시, 결과 표현에 집중한다.
- 외부 사주 엔진은 adapter 뒤에 숨긴다.
- HTTP route는 얇게 유지하고, 실제 흐름은 orchestration service로 보낸다.
- 한 파일이 여러 책임을 동시에 갖기 시작하면 분리한다.
- 테스트와 trace는 기능만큼 중요하다.

## 현재 권장 구조

```text
apps/
  api/
    app/
      api/
        routes.py
      domain/
        saju/
          adapters/
            lunar_python_engine.py
          services/
            analyze_saju.py
            birth_time_policy.py
            build_preview_response.py
            calculate_saju.py
            preview_orchestrator.py
            region_catalog.py
          analysis.py
          calendar_normalization.py
          engine.py
          mock_data.py
          schemas.py
          time_correction.py
      config.py
      diagnostics.py
      main.py
    tests/
  web/
    src/
      features/
        dev/
          DeveloperPage.tsx
        service/
          ServicePage.tsx
          components/
            SajuForm.tsx
            SajuResultView.tsx
            ServiceHeader.tsx
      shared/
        api/
          contracts.ts
          saju.ts
        copy.ts
        navigation.ts
      App.tsx
      main.tsx
      styles.css
```

## 계층별 책임

### `apps/api/app/api`
- HTTP request/response 처리만 담당한다.
- request parsing, response model 지정, orchestration service 호출만 둔다.
- 시간 보정, 달력 정규화, 사주 계산, 분석 로직을 직접 넣지 않는다.

### `apps/api/app/domain/saju`
- 사주 도메인 규칙의 중심이다.
- 입력 정규화, 계산 결과 구조, 정책, 분석 규칙, 엔진 adapter를 둔다.

### `services/preview_orchestrator.py`
- preview 흐름의 유일한 조합 지점이다.
- `지역 확인 -> 시간 보정 -> 달력 정규화 -> 사주 계산 -> 분석 -> 응답 조립`
  순서를 가진다.
- route에서 직접 여러 서비스를 이어 붙이지 않도록 막는 역할을 한다.

### `services/region_catalog.py`
- 지역 검색과 선택 검증을 담당한다.
- UI 자동완성과 계산 입력 사이의 경계다.
- 검색용 alias와 최종 region id 확인 책임을 가진다.

### `services/build_preview_response.py`
- 계산과 분석 결과를 API 응답 구조로 바꾼다.
- 응답용 설명 텍스트, evidence section, debug checkpoint 조립을 맡는다.
- 계산 자체를 수행하지 않는다.

### `adapters/`
- 외부 오픈소스 엔진을 캡슐화한다.
- 현재는 `lunar_python_engine.py`가 여기에 해당한다.
- 나중에 엔진 교체가 필요해도 나머지 서비스 코드는 그대로 유지되는 것이 목표다.

### `apps/web/src/features`
- 화면 기능 단위로 나눈다.
- 사용자 화면과 개발자 화면을 분리한다.
- 한 페이지 파일이 너무 커지면 `components/`로 쪼갠다.

### `apps/web/src/shared`
- 공통 API 클라이언트, 타입, 문구, 경로 유틸리티를 둔다.
- UI 기능이 아닌 공통 자산만 둔다.

## 프론트 규칙

### `App.tsx`는 루트 조립만 한다
- 현재 모드 선택
- locale 상태
- 공통 health/result 상태
- 페이지 전환
- 페이지 내부 폼 로직과 렌더링 세부는 `features/` 아래로 보낸다.

### 페이지와 폼을 분리한다
- `ServicePage.tsx`는 서비스 화면 컨테이너 역할을 한다.
- `SajuForm.tsx`는 입력 폼 렌더링만 담당한다.
- `SajuResultView.tsx`는 결과 표현만 담당한다.
- `DeveloperPage.tsx`는 debug 결과만 표시한다.

### API 계약은 한 곳에서 관리한다
- 프론트 타입은 `shared/api/contracts.ts`에 둔다.
- `shared/api/saju.ts`는 fetch와 에러 파싱만 담당한다.
- 컴포넌트 안에서 직접 `fetch`를 반복하지 않는다.

### 프론트에서 금지할 것
- 사주 계산 규칙 구현
- 점수/등급 재계산
- route path 문자열과 API shape를 컴포넌트마다 각자 해석하는 방식
- 사용자 화면과 개발자 화면의 상태/UI를 한 파일에 모두 몰아넣는 방식

## 백엔드 규칙

### route는 얇게 유지한다
- 현재 `/saju/preview`는 orchestration service를 호출하는 구조로 유지한다.
- route 파일이 길어지기 시작하면 대부분 잘못된 신호다.

### 스키마는 먼저 고정한다
- request/response 구조는 `schemas.py`에서 관리한다.
- route와 service는 schema를 기준으로만 대화한다.

### 계산 엔진은 service가 아니라 adapter다
- `calculate_saju.py`는 adapter를 호출하는 얇은 진입점이어야 한다.
- `lunar_python`를 다른 파일 여기저기서 직접 import하지 않는다.

### 데이터셋과 정책은 분리한다
- 지역 데이터는 `mock_data.py` 같은 데이터 파일에 둔다.
- 검색과 검증은 `region_catalog.py`에 둔다.
- 출생시간 미상 정책은 `birth_time_policy.py`에 둔다.

### 백엔드에서 금지할 것
- route에서 시간 보정, 계산, 응답 조립을 모두 처리하는 방식
- 외부 엔진 직접 호출이 여러 파일에 흩어지는 구조
- 조용한 fallback으로 잘못된 결과를 반환하는 방식

## 테스트 규칙

### unit test
- 시간 보정
- 달력 정규화
- 출생시간 정책
- 분석 규칙
- 엔진 adapter

### integration test
- `/saju/preview` 전체 흐름
- 지역 선택에서 계산 결과 응답까지의 연결

### golden test
- 절기 경계
- 자시 경계
- 음력/윤달 대표 케이스
- 한국 주요 지역 샘플

### frontend verification
- 타입 검사
- 빌드 검증
- 실제 dev 서버에서 입력/결과 흐름 확인

## 구조가 무너질 때 보이는 신호
- `App.tsx`가 다시 모든 화면과 상태를 다 갖기 시작한다.
- route 파일이 150줄 이상 흐름 로직으로 채워진다.
- `mock`, `preview`, `result` 개념이 파일 이름과 실제 책임에서 어긋난다.
- 같은 API 타입이 여러 곳에서 중복 정의된다.
- 검색용 지역 데이터와 계산용 지역 메타데이터가 섞여 관리된다.

## 다음 구조 작업 우선순위
1. 프론트-백엔드 공통 계약을 `packages/contracts`로 올리는 작업 검토
2. 지역 데이터셋을 정적 샘플에서 공식 데이터 기반 구조로 교체
3. longitude 기반 지역 보정 모듈 추가
4. LLM formatter를 별도 service로 분리
5. frontend component test 추가
