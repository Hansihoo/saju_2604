# Development Rules And Maintainability Guide 009

## 목적
- 개발 전에 유지보수하기 좋은 구조를 고정한다.
- Python과 React를 잘 몰라도 "어디에 무엇을 넣어야 하는지" 헷갈리지 않게 한다.
- 이후 모든 구현은 이 문서를 기본 규칙으로 삼는다.

## 이 문서의 역할
- 기능 명세 문서가 아니다.
- 코드를 어떻게 나눌지, 어떤 패턴을 피할지, 어떤 테스트와 로그를 기본으로 가져갈지에 대한 개발 규칙 문서다.
- 나중에 프로젝트를 다시 시작해도 이 문서만 보면 구조와 기준을 빠르게 복원할 수 있어야 한다.

## 핵심 철학
- 복잡한 로직은 한 곳에만 둔다.
- 계산과 표현을 분리한다.
- 프런트는 보여주고 입력받는 역할에 집중한다.
- 백엔드는 검증, 계산, 분석, 추적의 중심이다.
- 오픈소스는 직접 퍼뜨리지 말고 adapter 뒤에 숨긴다.
- 디버그 가능한 코드가 유지보수 가능한 코드다.

## 가장 중요한 규칙

### 1. 계산 로직은 프런트에 두지 않는다
- React는 입력 UI, 결과 표시, 단계적 공개 UX만 담당한다.
- 사주 계산, 점수 계산, 등급 계산, 시간 보정은 모두 백엔드에서 한다.
- 프런트에서 계산 규칙을 복제하면 나중에 서로 다른 결과가 나와 유지보수가 어려워진다.

### 2. 라우트는 얇게 유지한다
- FastAPI route 함수에는 비즈니스 로직을 많이 넣지 않는다.
- route는 다음만 한다:
  - 요청 받기
  - schema 검증
  - service 호출
  - 응답 반환
- 계산, 정책, 변환은 service/domain 계층으로 보낸다.

### 3. 오픈소스 엔진은 adapter 뒤에 숨긴다
- 서비스 코드 곳곳에서 `lunar-python`을 직접 import하지 않는다.
- 오픈소스 변경이나 교체가 필요할 때 adapter만 수정할 수 있게 만든다.
- 우리 프로젝트의 계산 인터페이스가 먼저고, 오픈소스는 그 구현체다.

### 4. debug와 trace는 처음부터 넣는다
- 나중에 붙이면 빠뜨리는 정보가 많다.
- 각 요청은 `trace_id`를 가져야 한다.
- 단계별 상태와 에러 코드는 구조화 로그로 남겨야 한다.

### 5. 파일은 "한 가지 이유로만 변경"되게 나눈다
- 한 파일이 여러 책임을 가지면 수정할 때 사이드 이펙트를 만들기 쉽다.
- 입력 검증, 시간 보정, 엔진 호출, 점수 계산, LLM 표현은 파일을 분리한다.

## 추천 폴더 구조

```text
apps/
  api/
    app/
      api/
        routes.py
        errors.py
      domain/
        saju/
          schemas.py
          time_correction.py
          calendar_normalization.py
          policies.py
          analysis.py
          adapters/
            lunar_python_engine.py
            sxtwl_verifier.py
          services/
            calculate_saju.py
            build_reading.py
      infrastructure/
        settings.py
        logging.py
        region_repository.py
      main.py
  web/
    src/
      app/
      features/
        saju-input/
        saju-result/
      shared/
        api/
        ui/
        utils/
```

## 계층별 역할

### `api/`
- HTTP 요청과 응답 처리
- route, request parsing, response mapping
- 절대 계산 핵심 로직을 길게 넣지 않는다

### `domain/saju/`
- 서비스의 핵심 규칙이 모이는 곳
- 시간 보정
- 달력 정규화
- 사주 계산 결과 정규화
- 분석 엔진
- 정책 처리

### `adapters/`
- 외부 엔진과의 연결 계층
- `lunar-python`, `sxtwl` 같은 외부 의존성을 감싼다

### `services/`
- 여러 domain/adapters를 조합하는 orchestration 계층
- "입력 -> 보정 -> 계산 -> 분석 -> 응답용 결과" 흐름을 구성한다

### `infrastructure/`
- 설정
- 로깅
- 데이터소스 접근
- 지역 데이터셋 로딩

### `web/features/`
- 화면 기능 단위로 쪼갠다
- 입력 기능과 결과 기능을 분리한다

### `web/shared/`
- 공통 API 클라이언트
- 공통 UI 컴포넌트
- 공통 유틸리티

## Python 규칙

### 타입을 기본으로 쓴다
- 함수 입력과 반환 타입을 가능한 한 명시한다.
- `dict` 하나로 다 넘기지 말고 schema나 typed model을 쓴다.

### schema를 먼저 만든다
- FastAPI 요청/응답은 Pydantic 모델로 고정한다.
- 내부 계산 결과도 가능하면 구조화된 모델로 관리한다.

### pure function을 선호한다
- 시간 보정, 점수 계산, 등급 계산처럼 규칙 기반 로직은 가능한 한 순수 함수로 만든다.
- 순수 함수는 테스트하기 쉽고 디버그가 쉽다.

### 예외를 통제한다
- `raise Exception(...)` 같은 광범위한 예외 남용을 피한다.
- 표준 에러 코드와 커스텀 예외 클래스를 둔다.

### 설정은 코드에 박지 않는다
- API 키, debug 여부, timeout, 로그 레벨은 설정 파일과 환경 변수로 분리한다.

### route에서 DB/엔진 직접 호출 금지
- route -> service -> domain/adapter 흐름을 유지한다.

## React 규칙

### 컴포넌트를 크게 만들지 않는다
- 페이지 하나에 모든 상태와 UI를 몰지 않는다.
- 입력 폼, 지역 자동완성, 결과 요약, 상세 아코디언을 분리한다.

### 프런트는 비즈니스 계산을 하지 않는다
- 프런트는 서버가 준 값을 보기 좋게 정리하고 상태를 관리할 뿐이다.
- 점수 계산, 등급 판정, 시주 제한 판단은 백엔드에서 한다.

### API 호출 코드를 UI에 섞지 않는다
- `fetch`를 페이지 컴포넌트 여기저기에 직접 쓰지 않는다.
- `shared/api/`에 API 클라이언트를 두고 재사용한다.

### 상태는 기능 단위로 관리한다
- 입력 폼 상태와 결과 상태를 분리한다.
- debug 패널 상태도 일반 사용자 UI 상태와 분리한다.

### 화면 구조는 "요약 우선"을 유지한다
- 기본 화면은 이해하기 쉬운 요약만 보여준다.
- 오행, 십성, 대운은 펼쳐보기 구조로 둔다.

## 이름 규칙

### 코드 식별자
- 파일명, 함수명, 변수명은 영어로 작성한다.
- 문서 설명과 사용자 문구는 한국어로 작성한다.

### 파일명
- 역할이 드러나게 짓는다.
- `utils.py` 같은 큰 잡동사니 파일은 가능한 피한다.
- 예:
  - `time_correction.py`
  - `calendar_normalization.py`
  - `analysis.py`
  - `build_reading.py`

### 에러 코드
- 모두 대문자 스네이크 케이스
- 예:
  - `INVALID_TIMEZONE`
  - `ENGINE_VALUE_ERROR`
  - `LLM_OUTPUT_PARSE_ERROR`

## 금지 패턴

### 백엔드
- route 함수에 50줄이 넘는 계산 로직 넣기
- schema 없이 `dict`를 계속 넘기기
- 오픈소스 엔진을 route나 UI 근처에서 직접 호출하기
- 실패 시 조용한 fallback으로 틀린 값을 반환하기
- 로깅 없이 복잡한 변환 수행하기

### 프런트
- 페이지 파일 하나에 입력/결과/에러/debug를 다 몰아넣기
- 백엔드 계산 로직을 프런트에서 다시 구현하기
- API 응답 shape를 컴포넌트마다 제각각 해석하기
- 지역명을 자유 입력 그대로 제출하기

## 유지보수하기 좋은 코드의 기준

### 읽었을 때 흐름이 보인다
- 파일명만 봐도 어디서 무엇을 하는지 감이 와야 한다.

### 수정 범위가 예측 가능하다
- 시간 보정 수정이면 `time_correction.py` 근처만 보면 된다.
- 점수 규칙 수정이면 `analysis.py` 근처만 보면 된다.

### 테스트가 빠르게 깨진다
- 문제가 생기면 unit, integration, golden 중 어디에서 깨졌는지 바로 보여야 한다.

### 로그로 재현이 가능하다
- `trace_id` 하나로 요청 흐름을 재구성할 수 있어야 한다.

## 테스트 규칙

### unit test
- 규칙 함수 중심
- 시간 보정
- 양력/음력 정규화
- 시주 제한 정책
- 점수/등급 계산

### integration test
- 계층 연결 확인
- 입력 -> 시간 보정 -> 계산 -> 분석 -> 응답

### golden test
- 대표 샘플을 고정해 회귀 확인
- 절기 경계
- 자시 경계
- 음력/윤달 샘플
- 한국 대표 케이스

### e2e test
- 실제 사용자 흐름 검증
- 지역 자동완성
- 정상 조회
- 시간 미상 흐름
- 상세 펼침

### manual verification
- 결과 문장 톤
- 과장 여부
- 제한 안내 문구
- 모바일/데스크톱 시인성

## 로그와 디버그 규칙

### 기본 로그
- JSON 구조화 로그를 기본으로 한다.
- 필수 필드:
  - `trace_id`
  - `stage`
  - `event`
  - `duration_ms`
  - `error_code`

### 단계 로그
- 최소한 아래 단계 로그를 남긴다.
  - `input_validation`
  - `region_resolution`
  - `time_correction`
  - `calendar_normalization`
  - `saju_calculation`
  - `analysis_engine`
  - `llm_formatting`

### debug 옵션
- `SAJU_DEBUG=1`
- `SAJU_TRACE_PAYLOADS=1`
- `SAJU_TRACE_LLM=1`
- `SAJU_FAIL_FAST=1`
- `SAJU_LOG_LEVEL=DEBUG`

### 주의
- 운영 환경에서 민감한 원본 입력을 그대로 로그에 남기지 않는다.
- 필요 시 마스킹한다.

## 구현 순서 규칙
- 무조건 UI부터 화려하게 만들지 않는다.
- 아래 순서를 지킨다:
  1. 계약과 trace 구조
  2. 지역 정규화
  3. 시간 보정
  4. 양력/음력 정규화
  5. 사주 계산 adapter
  6. 시주 제한 정책
  7. 분석 엔진
  8. LLM 표현
  9. 결과 UI
  10. CI와 회귀 검증

## 코드 리뷰 기준
- 이 로직이 있어야 할 위치에 있는가
- 동일 규칙이 프런트와 백엔드에 중복되지 않는가
- 테스트가 추가되었는가
- trace/logging이 충분한가
- 실패 시 조용히 넘어가지 않는가
- 다음 사람이 읽어도 목적이 분명한가

## 나중에 프로젝트를 다시 시작할 때 보는 순서
1. 이 문서
2. 엔진 선정 문서
3. 세부 개발/진단 문서
4. 기능 명세 문서
5. 실제 코드

## 관련 문서
- `docs/planning/007-engine-selection-and-calculation-strategy.md`
- `docs/planning/008-detailed-development-execution-and-diagnostics.md`

## 이번 결정
- 앞으로 구현은 이 문서의 구조 규칙을 기준으로 진행한다.
- 유지보수성과 디버그 가능성을 기능 구현과 같은 우선순위로 둔다.
- Python과 React를 잘 몰라도 파일 위치와 책임만 보면 수정 경로를 찾을 수 있게 만든다.
