# 061. 프로젝트 내부 런타임 검증 스킬

2026-10-10. 사용자 요청: “제대로, 쉽게 이해할 수 있는 문구인가?”, “궁금증을 채울 수 있는 내용인가?”, “추가 질문에 대해서 흥미를 유발하면서 추가 질문을 유도할 수 있게 되어있나?”를 함께 검증하고 프로젝트 내부 스킬로 실행한다.

## 범위와 소유권

프로젝트 스킬은 [.agents/skills/saju-runtime-verification/SKILL.md](../../.agents/skills/saju-runtime-verification/SKILL.md)이며 root AGENTS가 “런타임 검증해줘” 요청을 연결한다. 일반 서버 건강 확인과 구별한다. 기존060의 C01~C06을 반복 정의하거나 새 명리 판정법을 만들지 않는다.

평가의 단일 기준은 [runtime_reading_rubric.json](../../apps/api/app/tools/data/runtime_reading_rubric.json)이고 버전은 `runtime-reading-rubric-2026-10-10.1`이다. 독자 역할은 question_fit/clarity/curiosity_satisfaction/followup_interest, 근거 역할은 fact_fidelity/reasoning/note_consistency/followup_delivery를 담당한다. 대상 job에는 사례별 적용 기준과 실제 자료만 공급하며 예상 판정 예시는 전달하지 않는다. 별도 calibration 예시는 기준 설계/계약 시험에만 사용한다. 이름·출현 횟수·길이 대신 실제 결론과 조건, 독자가 얻은 새 정보와 다음 질문의 약속을 평가한다.

## 실행 연결

- `capture_runtime_reading`: 격리 fallback-only preflight 후 기존 ASGI category 캡처를 재사용하고 공개된 모든 질문의 실제 선택 답을 캡처한다. 선택 후 같은 분야에 표시되는 남은 질문도 동결한다.
- `runtime_reading_reviews prepare`: 기존 snapshot의 facts/source 경계를 검증한 뒤 별도 reader/evidence job을 만든다. reader는 실제 보이는 본문/질문/답만 받고 계산 원본·접힌 메모·작성자 평가를 받지 않는다.
- 독립 에이전트가 각 job을 검토한다. 각 작업은 단독 실행 가능하며 서로/모델/provider를 호출하는 transport는 새 모듈에 넣지 않는다.
- `evaluate`: 같은 snapshot/rubric/job hash의 검토만 합친다. 모든 사례·적용 기준, 실제 인용과 메뉴 질문 선택을 검사한다. 미실행/fixture는 HOLD, 사실·기능/내용 실패는 다른 PASS로 상쇄하지 않는다.

독자의 재서술, 질문 충족 정도, 실제로 고른 후속 질문 ID/새로 알 기대 내용과 수정 위치를 필수 기록한다. 정직한 한계 설명의 적절성과 요청 정보 미충족을 구별한다. 수정 요청을 받았을 때만 원인을 수정하고 새 snapshot/job으로 최대2회 재검토하며 첫 실패를 보존한다.

기존 question_flow_reviews/agent_verification의 스키마·prompt/rubric·과거 결과는 유지한다. 새 검증 prompt `runtime-reading-prompts-2026-10-10.2`, review/job/report `runtime-reading-review-v1`, capture `runtime-capture-2026-10-10.1`은 독립이다. .2는 독립 행동 시험에서 발견한 예상 판정 예시 노출을 제거한다. 계산·명리 규칙·프로덕션 문구·UI·공유·provider 선택과 critical 보류를 바꾸지 않는다.

## 검증 경계

스킬 자동 선택/AGENTS 연결, 계약 테스트와 실제 fallback ASGI 캡처/prepare/evaluate, 독립 에이전트 행동 시험을 확인한다. 새 검증기 통과를 서비스 콘텐츠 통과로 보고하지 않는다. 실제 브라우저 검증과 전문가·실사용자 흥미·예측 정확도는 별도다. 새 스킬의 검토는 input_blind_only이며 도구까지 차단한 맹검이 아니다.

상세 실행 절차는 [스킬 workflow](../../.agents/skills/saju-runtime-verification/references/workflow.md), 현재 결과는 [PROJECT_STATUS](../PROJECT_STATUS.md)와 [WORK_LOG](../ai/WORK_LOG.md)에 유지한다.

2026-10-10 구현 검증: 관련 계약85개, 웹 보조14개, 스킬 형식·UTF-8·링크·버전 검사 통과. 별도 오케스트레이터와 새 독자/근거 에이전트로 제공된 합성2사례를 두 차례 검토해 내용 부족·추가 질문 연결 부족·접힌 근거 누락을 감지했다. 첫 회차의 예상 판정 예시 노출/dispatch 차이는 보존하고 .2에서는 전체 역할job을 편집 없이 전달했다. 세부 판정 편차는 새 독립 검토의 편차이며 내용 개선 효과가 아니다.

실제 fallback ASGI 캡처7사례의 코드 검사는 통과했다. 미실행 독립 역할은 HOLD, 시간미상 사례의 용어 설명 중심 본문은 별도 내용 gate에서 FAIL이다. 기본 사용자 시나리오는456 PASS/3 WARN/기존 음력30일 FAIL1을 유지했다. 생성provider 호출0, 브라우저/실사용자 흥미 검증 없음. 평가 보고서의 frozen_content와 공급 source_provenance는 실제 API/UI 실행 인증이 아니며 캡처 실행 증거와 함께 해석한다. 비공개 증거는 등록된 ignored root에 보존했다.

## 062 후속 실행 확장

[임의 사주5개 검증](062-five-chart-runtime-reinforcement.md)에서 capture.2의 birth-only 입력, prompt.4의 최초 역할 job 로딩과 cohort별 독립 실행을 추가했다. 비공개 과거 템플릿의 투영 제외는 원본 snapshot/계산 facts/실제 적용 규칙과 함께 기록한다. 위 최초 구현.1의 변경 경계와 결과는 과거 기록이다. 후속062는 별도로 버전 관리한 서비스 문구·질문 맥락을 보강하며, 기존 rubric.1/계약v1과 종합 판단·시기 공백 및 critical 보류는 유지한다.
