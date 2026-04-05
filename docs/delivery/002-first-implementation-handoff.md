# First Implementation Handoff 002

## 1. 참조 기능 명세
- 문서 경로:
  - `docs/planning/006-feature-spec-mvp-personal-reading.md`

## 2. 이번 회차 목표
- 입력/응답 계약과 더미 파이프라인을 연결해, 프런트와 백엔드가 같은 구조로 대화할 수 있게 만든다.

## 3. 이번 회차 범위
- 포함:
  - 입력 스키마 정의
  - 결과 응답 스키마 정의
  - 더미 지역 검색 API
  - 더미 개인 해석 API
  - 프런트 입력 폼과 결과 화면 연결
- 제외:
  - 실제 시간 보정
  - 실제 사주 계산
  - 실제 분석 엔진
  - 실제 LLM 호출

## 4. 예상 변경 영역
- 프런트:
  - 입력 폼
  - 결과 렌더링
  - 지역 자동완성 UI
- 백엔드:
  - request/response schema
  - mock endpoint
- DB/인프라:
  - 없음
- 문서:
  - 실행 명령
  - 개발 회차 결과

## 5. 검증 방법
- build:
  - 프런트 build
- test:
  - 스키마 test
  - 폼 validation test
- lint:
  - 프런트/백엔드 lint
- typecheck:
  - 프런트 typecheck
  - 백엔드 typecheck
- 수동 확인:
  - 지역 검색 입력
  - 출생시간 미상 흐름
  - 더미 결과 렌더링

## 6. 로그 확인 포인트
- 어떤 로그를 볼지:
  - 입력 payload
  - 지역 검색 응답
  - 결과 생성 응답
- 실패 시 어디를 먼저 볼지:
  - 프런트 validation
  - API schema parsing
  - mock response shape

## 7. 보류 항목
- 실제 FortuneFlow 연결
- 시간 보정 모듈
- 점수/등급 엔진
- LLM 표현 생성

## 8. 다음 회차 시작점
- 다음 회차 추천 작업:
  - 시간 보정 모듈과 지역 정규화 구현
- 남은 질문:
  - 지역 데이터 소스
  - 양력/음력 변환 책임 계층

