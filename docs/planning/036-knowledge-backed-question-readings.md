# 036. Knowledge-backed question readings

## Decision

말투 조정만으로 새 질문을 답하지 않는다. 기존 계산 → 공급 사실 → 출처와 조건을 가진 지식 규칙 → 질문별 읽기 plan → 표현/UI 순서로 분리한다. 에이전트 작업 규약은 [SAJU_READING_AGENT.md](../ai/SAJU_READING_AGENT.md)에 고정하고 루트 `AGENTS.md`에서 필수 문서로 연결한다.

새 DB나 벡터 검색을 도입하기 전, 기존 Python/Pydantic·Git 배포 구조에서 엄격한 JSON 카탈로그로 시작한다. 문장 변경과 계산 변경의 영향 범위를 분리할 수 있고, 배포마다 같은 규칙 버전으로 재현 가능하다. 지금의 21개 규칙은 프로젝트 정책의 정리이며 외부 문헌이나 전문가 검증으로 포장하지 않는다.

## Contract

`saju-knowledge-v1`는 source, rule, question policy를 담는다. 규칙은 feature/value, 제외 조건, claim scope, 활성 상태, 두 언어의 문장을 갖는다. 규칙 ID/version, bundle knowledge version, copy version, format version을 분리한다.

`question-reading-v1`는 question과 answer/scene/tradeoff/action 네 block, analysis_note를 담는다. 각 block은 rule/fact를 참조한다. 예시는 illustration, 행동은 advice, 나머지는 interpretation이다. 계산 사실은 fact의 값/경로로 별도 저장한다. 공통 API 필드도 보존하여 UI와 공유는 같은 질문과 강조 문장을 사용한다. 분석 노트는 같은 rule의 문구 템플릿과 동일 facts로 생성하며 카드의 basis_explanation/basis_line과 대조한다. 구형 오행 부족 해석이나 다음 대운 비교를 현재 규칙의 근거로 섞지 않는다.

fallback 카드에만 `server_project_policy` marker를 붙이고, 공급자 JSON에서 서버 metadata를 받아들이지 않는다. 검증기는 원 payload로 plan을 다시 만들어 값/규칙/문구 연결을 비교한다. 서버 fallback 상세의 성격·연애·직장·현재 대운도 같은 네 block으로 렌더링한다. 글자 수를 맞추기 위한 반복 확장 대신 최소 내용과 역할을 확인한다.

## Questions and research queue

| ID | 질문 | 상태 / 다음 조건 |
| --- | --- | --- |
| love.meeting_window | 연인을 만날 기회는 언제 커질까? | Needs review: 원국/대운/세운/월운의 만남 관련 규칙과 예외를 전문가 검토한다. |
| career.entry_window | 좋은 일자리를 얻는 시점은? | Needs review: 취업 규칙·시기 데이터·사용자 목표를 구분한다. |
| career.recognition_window | 직장에서 인정받는 시점은? | Needs review: 책임 증가와 평가/직급 상승을 구분한다. |
| career.reward_window | 대우·보상이 나아지는 시점은? | Needs review: 책임과 보상을 구분하고 목표 정보를 정의한다. |
| fortune.population_comparison | 타인보다 운세가 얼마나 좋을까? | Needs reference population: 비교 지표·모집단·표본·시점이 필요하다. |

현재 rule 기반 출력은 확률·순위·사건 발생일을 제공하지 않는다. 장래 시기 분석을 추가해도 먼저 ‘현재 본인의 기간끼리 해석상 비교’로 범위를 정의한다. 실제 확률은 관측 결과와 보정 평가가 있어야 별도로 지원할 수 있다. 기능 활성화 전에 구체적인 규칙과 검증 표본을 검토한다.

## Follow-up boundaries

독립 wealth 상세·hero 전체·today/month·선택형 타이밍 상세는 기존 경로를 유지하며 모두 같은 문장 추적 계약으로 이관된 것은 아니다. 사용자 행동을 관찰한 예시가 아니므로 scene에 예시임을 표시한다. regex는 알려진 보장형 표현을 거부하지만 모델의 모든 의미를 판단하지 않는다. 실사용자 흥미는 자동 테스트 통과로 주장하지 않는다.

## Verification

단위 검증은 규칙 충돌/출처 누락/언어/치환/반대 사실/비활성·미상·stale cycle/사실 및 문장·노트 동시 변조/공급자 marker 주입/짧은 결과와 상세 정합성을 확인한다. fallback-only HTTP 검증에는 trace와 미지원 질문 상태, 공개 계산값/카탈로그와 분석 노트 대조를 추가한다. 실제 부산 today 검증으로 발견한 `七杀/七殺→편관` 표기 누락을 수정했으며 미등록 기간 십성은 비견으로 대체하지 않는다. 기존 유효 음력 2/30 입력 실패와 인간 흥미/live-provider 검토 WARN은 그대로 추적한다. 최종 실행 결과는 `docs/ai/USER_STORY_VERIFICATION.md`, 진행 상태는 `docs/PROJECT_STATUS.md`에 기록한다.
