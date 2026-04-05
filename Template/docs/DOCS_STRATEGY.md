# DOCS_STRATEGY

## 목적
이 문서는 이 템플릿에서 Markdown 문서를 어떤 역할로 나누고, 각 문서에 무엇을 넣어야 하는지 정리한다.

## 기본 원칙
- 짧은 시작 문서는 빠르게 방향을 잡게 한다.
- 긴 설명은 별도 문서로 분리한다.
- 단계 진행 문서는 "이번 회차에서 무엇을 했는가"를 보여준다.
- 기준 문서는 변하지 않는 규칙과 선택 기준을 담는다.

## 문서 분리 기준
- `README`가 생긴다면: 왜 이 프로젝트가 유용한지, 무엇을 할 수 있는지, 어떻게 시작하는지
- `START_HERE`: 처음 들어온 사람이 지금 무엇부터 해야 하는지
- `PROJECT_PROFILE`: 현재 프로젝트의 확정값, 기본값, placeholder
- `QUESTIONNAIRE`: 미확정 항목을 채우기 위한 질문
- `PLANNING_STAGES`: 기획을 여러 회차로 나누어 진행하는 방법
- `FEATURE_SPEC_TEMPLATE`: 기획 결과를 기능 명세로 정리하는 방법
- `IMPLEMENTATION_HANDOFF_TEMPLATE`: 개발 시작 전에 읽는 전달 문서
- `DEVELOPMENT_CHECKLIST`: 개발 회차에서 확인해야 하는 항목
- `DELIVERY_LOOP`: 개발을 작은 반복 단위로 진행하는 방법
- `WORKFLOWS`: 업무 종류별 표준 흐름
- `COMMANDS`: Codex에 바로 말할 명령과 이어서 진행할 프롬프트
- `CODE_STYLE`, `CI_CD`: 실행 규칙과 운영 기준

## Markdown 문서에 공통으로 들어가야 할 것
- 문서의 목적
- 언제 읽어야 하는지
- 입력 정보
- 단계 또는 체크리스트
- 산출물 또는 기대 결과
- 미확정 시 어떻게 처리하는지
- 다음에 이어서 무엇을 해야 하는지

## README가 생길 때의 기본안
- 프로젝트가 왜 유용한지
- 사용자가 무엇을 할 수 있는지
- 가장 빠른 시작 방법
- 상세 설명이 있는 문서 링크
- 기여 또는 작업 방식 링크

## 권장 문서 유형
Diataxis 관점에서 이 템플릿의 문서를 아래처럼 분리한다.

- Tutorial 성격:
  - `START_HERE`
  - 새 프로젝트 시작 순서를 익히게 한다.
- How-to 성격:
  - `PLANNING_STAGES`
  - `FEATURE_SPEC_TEMPLATE`
  - `IMPLEMENTATION_HANDOFF_TEMPLATE`
  - `DEVELOPMENT_CHECKLIST`
  - `DELIVERY_LOOP`
  - `WORKFLOWS`
  - 특정 작업을 어떻게 진행할지 단계로 안내한다.
- Reference 성격:
  - `PROJECT_PROFILE`
  - `COMMANDS`
  - `CODE_STYLE`
  - `CI_CD`
  - 기준값, 명령, 규칙을 빠르게 찾게 한다.
- Explanation 성격:
  - `ARCHITECTURE_TEMPLATE`
  - 왜 이런 구조와 원칙을 쓰는지 설명한다.

## 대화형 진행을 위한 문서 규칙
- 각 회차는 한 가지 목표만 가진다.
- 각 회차 문서에는 반드시 `이번 회차 결정`, `남은 질문`, `다음 회차 시작점`이 있어야 한다.
- 기획 문서는 사용자 가치와 사용 사례에서 출발하고, 구현 세부로 바로 뛰지 않는다.
- 개발 문서는 구현 내역뿐 아니라 검증 명령과 로그 확인 결과를 함께 남긴다.
- 사용자에게 보이는 문구는 내부 용어보다 쉬운 한국어를 우선 사용한다.
- 개발자는 기획 문서만이 아니라 기능 명세와 개발 전달 문서를 보고 작업을 시작할 수 있어야 한다.

## GitHub 템플릿 연계 원칙
- 반복되는 협업 입력은 `.github/ISSUE_TEMPLATE`로 구조화한다.
- PR에서 항상 확인해야 하는 것은 `.github/PULL_REQUEST_TEMPLATE.md`로 고정한다.
- 긴 설명을 PR 본문에 몰아넣지 말고 관련 문서로 링크한다.

## TODO(USER)
- 실제 프로젝트에서 README를 둘 경우 이 문서의 분리 기준을 README에도 반영
- 팀이 사용하는 프로젝트 관리 도구와 이 문서 체계를 어떻게 연결할지 결정
