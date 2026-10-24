# 053. Published reading and folded memos

작성일: 2026-10-09. 사용자 요청: 합의한 목차를 실제 서비스 결과에 적용하고 어려운 전문 용어는 기본 접힘으로 숨긴다.

## 목표와 범위

사주팔자와 으쓱 캐릭터 다음에 `내 사주의 특징 → 연애·결혼운 → 금전운 → 직장·직업운 → 지금부터 달라질 운`을 표시한다. 본문은 결론과 필요한 조건부터 읽고, 해당 장 아래의 지원 질문으로 이어진다. 한자·용어·위치·관법 차이·계산 기준은 작은 **풀이 메모**에 둔다. 계산의 실제 불확실성과 본문 주장의 조건은 밖에 남긴다.

작업 유형은 서버의 표시용 응답 투영, 작성 프롬프트, 기존 React 결과 화면, 검증 입력 및 에이전트 계약 보강이다. 계산 정책033·활성 판정 규칙·critical 전체 보류·미지원 사건 시기는 변경하지 않는다. 신규 판단을 문구 수정으로 위장하거나 용어 설명을 타고난 복으로 승인하는 것이 주요 위험이다.

## 소유권과 독립 버전

| 영역 | 소유 파일/버전 | 역할 |
| --- | --- | --- |
| 작성 체계 | `prompts/commercial_reading.py`, report promptv19 | 공급된 사실/판정만으로 친근한 반말, 결론 우선, 성격 대체·일반 숙제·미지원 시기 금지 |
| 표시 투영 | `reading_publication.py`, reading-publication-2026-10-09.3 | 실제 본문 blocks와 접힌 memo_body를 서버에서 조립; 새 판정은 하지 않음 |
| 응답 | category-reading-copy-2026-10-09.6 | 기존 category 계약에 선택적 publication 추가, 원본 body/information/provenance 보존 |
| 질문 문구 | question-copy-2026-10-09.2 | 지원되는 날짜/글자 위치 질문을 쉬운 문구로 표시; 질문 ID·규칙 불변 |
| 제품 계약 | reading_outline_design.2 / publication_presentation.3 | 구현된 표시와 아직 없는 종합 풀이를 구별 |

`publication.blocks`는 `interpretation`, `traditional_definition`, `calculation_summary`, `heading`, `availability_notice`로 구별한다. scope도 실제 보이는 종류에 따라 `supported_reading_excerpt`, `traditional_information`, `calculation_information`, `unavailable`로 나누며 critical은 항상 `provisional_information`이다. 글자 개수나 신살 정의만 있는 장을 개인별 종합 풀이로 기록하지 않는다.

프론트엔드는 이를 렌더링하며 계산/길흉/시기를 판단하지 않는다. `<details>`에 open 기본값을 주지 않고 trace/category 변경 시 닫힌 상태로 초기화한다. 강조는 다른 서체로 나누고 Markdown 강조는 React text/strong으로만 처리한다. HTML을 삽입하지 않는다. publication 없는 과거 저장 결과는 기존 렌더러로 복원한다. 과거 스냅샷을 최신 내용으로 덮어쓰지 않는다.

## 문구와 메모

- 전체 의미가 이해되는 쉬운 본문이 먼저다. ‘어떻게 읽을게’라는 절차 예고를 결과처럼 쓰지 않는다.
- 실제 발견한 신살만 쉬운 의미로 표시하고 원래 명칭/위치/기준은 메모에 보존한다. 비교 계산표 설명은 본문에서 제외한다.
- 원래의 고독·지연·압박 등 불리한 뜻을 장점으로 바꾸지 않는다. 해당 전통 뜻을 실제 사고·성격·이별·손실 판정으로 확장하지 않는다.
- 활성 core 카탈로그의 오행/성격 및051의 환경 조언을 타고난 복으로 재포장하지 않는다. 레거시 응답은 보존하되 publication 본문/메모에 이를 새 종합 풀이로 게시하지 않는다.
- 금전은 현재 위치·개수 정보 범위다. 만남/취업 시기와 원국 종합 길흉·대운 우열 판정은 필요한 규칙 없이 추가하지 않는다.
- critical에서는 개인 해석을 해제하지 않는다. 선택한 명식의 잠정 정보와 실제 보류 안내만 공급한다.

## 검증

네 사례(한국어 일반/영어 일반/제천23:30 경계/시간 미상)의 실제 fallback ASGI 응답을 동결한다. `verify_category_reading`은 원본의 숨은 특징이 아니라 **publication 본문**을 검토 입력으로 투영한다. 숨긴 legacy traits가 `interpretation_rules_applied=true`나 효용 PASS를 만들지 않도록 보이는 block 종류에서 메타데이터를 정한다.

질문자/답변자/감독관은 별도 job에서 검토하며 코드 PASS와 콘텐츠 유익성 승인을 구별한다. 역할 prompt/rubric 의미는 유지하고 새 snapshot/job hash를 사용한다. 실제 흥미·예측 정확도·전문가 승인은 이 검증의 대상 인증이 아니다. 유료 provider는 검증에 호출하지 않는다.

검증 기록은 등록된 `.dev-runtime/question-flow-20261008/phase053-*`와 `publication-jobs-r*-20261009/`에 보존한다. 새 실제 결과 URL은 `.dev-runtime/local-results`의 신규 임의 ID를 사용하며 기존052 결과를 덮어쓰지 않는다.

첫 전체 API 실행503개에서 구버전 copy/prompt 기대값2건·current_flow 계약1건과 harness 전역 로그 비활성화에 따른 로그 검사2건이 실패했다. 버전 기대값을 동기화하고 current_flow의 기존 범위 계약을 복원했으며 전역 로그 비활성화 없이 재실행한다. 기존 fallback 사용자 시나리오 **456 PASS / 3 WARN / 음력30일 1 FAIL**은 유지한다.

## 남은 내용 과제

표시 구조를 구현한 것과 상용 수준의 사주 내용이 완성된 것은 다르다. 원국의 분야별 복/불리함 종합, 정도의 근거, 기간별 도움/방해와 만남/취업 시기를 답할 규칙은 미완료다. 이 조건을 지키며 정의·위치·일반 조건문만 남는 장은 효용 FAIL로 남긴다. 미래 질문의 제목만 추가하거나 미지원 결론을 Codex가 채우게 하지 않는다. 실사용자 검토와 별도 전문가 검토 이후 공개 완성도를 판단한다.

최종 실행/브라우저/역할 결과는 `docs/PROJECT_STATUS.md`와 `docs/ai/WORK_LOG.md`에 동기화한다. 배포는 이번 범위가 아니다.

최종 기록: 전체 API503 checkpoint와 이후 관련80, 웹 타입/프로덕션 빌드/helper14/progress8 및 실제 fallback ASGI4사례가 통과했다. 독립 r1/r2 세 역할·종합 효용은 FAIL이다. r2에서 기술 메모 중복·미게시 특징 혼입·보류 불일치는 해소됐지만 원국/금전의 종합 결론과 사건 시기가 없다는 핵심 실패는 유지한다. r2 이후 두 소제목의 뜻을 원본에 맞췄고 금전 미판정 안내를 밖에 표시했으며 영어 hidden-stem 용어를 일반 단어로 바꿨다. 이것이 역할의 상용 콘텐츠 승인을 받은 것은 아니다.

브라우저는 실제 KO/EN/시간 미상/개인 결과, 메모 기본 접힘·펼침·닫힘, 지원 질문과 원래 분류 복귀를 확인했다. 처음에는 다른 탭을 관측해857px만 확인했으나, 이후 native 결과 탭의 실제390px에서 clientWidth=scrollWidth=375와 접힌/펼친 메모를 확인했다. 한국어 일반/영어/개인/시간 미상에 가로 넘침은 없었다. 요청한320px 제어는 실제390px로 남아320px 검증은 미완료다. 임시 설정은 reset했고 개인 결과 및 일반 예시 탭을 보존했다. 최초 browser skill의 native bridge 신뢰 오류 후 CUA 대체 경로를 사용했다. 최종 링크는 `phase053-result-links-r5.json`에 기록했다. live Codex 생성 호출은 테스트하지 않았고 기존6.1 Sol/xhigh 설정을 유지한다.

마지막 보강은 전문 이름을 비교하는 계산표 문구를 영어에서도 쉬운 위치 표현으로 바꾸고, 날짜 기준별 **계산된 명식만** core 메모에 복원했다. 거절된 특징/환경 해석은 다시 게시하지 않았다. 실제 개인 메모에서0시 기준 `戊辰 癸亥 己卯 丙子`가 보이고 본문에는 노출되지 않음을 확인했다. 이 두 교정 이후 최종 관련80과 fallback ASGI4사례가 통과했다. r2 역할 판정의 종합 효용 FAIL은 유지하며 신규 상용 승인으로 바꾸지 않는다.
