# 064. 짧고 도움 없는 결과 보강

2026-10-11 사용자가 실제 local-result7e3ea8ec를 읽고 “너무 짧고 도움이 별 이야기가 없어”라고 지적했다.

## 목표와 영향

제한된 분석을 전체 사주풀이로 오인했던 문제를 기록하고, 이미 공급된 의미까지 절단되는 경로를 고친다. 백엔드 본문과 게시 선택의 변경이다. 계산033·공개 API 구조·전문 자료의 기본 접힘·기존 critical 보류는 유지한다.

실제 본문은 core 한 블록, 금전 개수 한 문장, 직업 두 문장이다. `select_conclusions`는 월/지원 설명의 첫 문단만 남겼다. fallback은 생활 상황을 가정하는 scene/action을 제거한 후 answer/tradeoff만 공급한다. 금전 판정기는 미구현이며 counts를 금전운으로 대신한다. 현재/다음 대운은 각각 나열할 뿐 공통점과 차이를 설명하지 않는다. Codex의 출력형식/근거ID 검증 실패는 별개이며 이것만 고쳐도 core/금전 공백은 해결되지 않는다.

## 작업 범위와 위험

기존 판정의 조건·반대 단서를 살려 읽을 수 있는 설명으로 연결하고, 금전의 실제 등록된 두 분류 의미와 기간의 기존 주제 차이를 풀이한다. 위치/출현을 수입·능력·직업 적합성·유리한 사건 시기로 승격하지 않는다. 없는 종합 판정을 긴 일반 조언이나 신살 목록으로 채우지 않는다. 새로운 종합 판단기의 구현 완료로 보고하지 않는다.

## 검증

지정 입력의 실제 원본을 보존하고 같은 입력의 before/after fallback ASGI 본문·표시 메뉴·실제 선택 답을 동결한다. 독립 reader/evidence job으로 쉬운 문구·궁금증 충족·후속 질문의 새 정보를 검토한다. 반대/누락/critical·KO/EN·출처 보존 단위 검사와 fallback-only 사용자 시나리오를 수행한다. 새 제품 모델 호출은 하지 않는다. UI 접근 실패는 HOLD로 남긴다.

## 진행

Needs review. 제한된 설명 보강은 적용됐으나 전체 사주풀이의 효용은 아직 실패다.

## 적용한 수정

- `natal_structure.select_conclusions`가 월/지원 설명의 전체 문단을 유지한다. 첫 문단 뒤의 조건과 반대 단서가 사라지지 않으며 중복된 인성/식상 문단 추가는 제거했다. 원본 facts·profile·규칙/적용 조건은 유지한다.
- 금전 본문은 실제 정재/편재/둘 다/부재에 맞춰 등록된 뜻을 설명한다. 기존 개수와 위치는 메모에 보존한다. 뜻 설명은 금전운의 유리함·수입·저축 판단이 아니며 기존 needs_rule_review를 유지한다.
- fallback 직업은 기존 answer/tradeoff에 해당 규칙의 의미 구별을 보충한다. 사용자의 생활 상황을 추측하는 scene/action은 복원하지 않는다. 별도 natal copy 자료를 사용해 legacy answer240자 계약과 역할을 유지했다.
- 현재/다음 대운의 실제 천간 관계를 비교한다. 같은 주제/비견·겁재 간 차이/다른 주제의 라벨 비교를 구별한다. critical/자료 미상에는 추가하지 않는다. 근거는 일간·현재·다음 천간의 실제 fact ID이며 원국·지지·세운·상호작용·길흉 비교를 구현한 것이 아니다.
- natal copy/selection, category copy, information rules/copy, publication은 각각2026-10-11.1이다. natal knowledge/rules와 legacy dokkaebi copy2026-10-10.1, primary033·API 응답 형식·기본 접힘·critical 제한은 유지한다.

## 실제 검증과 결과

등록된 `.dev-runtime/five-chart-runtime-20261010/`에 원본·before/after/final fallback ASGI captures, 독립 job과 검토, 테스트/실패 로그를 보존한다. 사용자에게 보인 실제7e3ea8ec 원본도 그대로 보존했다. 최종 snapshot의 natal/profile/facts와 원본 계산 사실이 일치하며 신규 제품 모델 호출은0이다.

before 독자는 문장 이해도/질문 연계는 PASS지만 본문의 궁금증 충족은 FAIL, 전체 요청은partial로 기록했다. 최종 reader/evidence는 별도 job만 보고 검토했다(`input_blind_only`, 기술적 도구 차단 없음). 실제 인용/hash 계약이 모두 유효하며, 최종 본문 쉬운가/후속 흥미/선택 답의 약속 이행과 근거 일치는 PASS다. 그러나 본문의 분야별 전체충족은partial, 선택 답은met이므로 evaluator의 최종 **code PASS / content FAIL**이다. 특히 금전·직업은 의미 구별 수준이며 충분한 개인별 종합 답으로 승인되지 않았다. 후기 PASS를 실제 사용자 만족이나 전문가/예측 정확도 승인으로 확대하지 않는다.

영향 API97개 PASS, 웹 helper14개 PASS. 격리 fallback 실제 loopback HTTP 사용자 시나리오는456 PASS/3 WARN/기존 유효음력30일 FAIL1이다. 서버 중단/외부 생성 호출 없이 별도 검사 서버를 시작·종료했다. 초기 실행의 fallback 설정 누락과 실제 EN answer240자 계약 실패는 보존한다. 설명을 별도 자료로 분리한 후 계약을 통과했으며 제한을 느슨하게 바꾸지 않았다. 최종 한국어 조사 한 곳 수정 후 새 snapshot/job으로 다시 독립 검토했다.

신규 결과 `/local-result/03e3ab65676443c1beb4955c8a763ddb`는 final ASGI 응답을 그대로 저장했고 served JSON 일치/no-store 및 문서 HTTP200을 확인했다. 브라우저 bridge trust 오류로 DOM/접힘/선택·복귀/시각 확인은 **HOLD**, 앱 열기는queued다. HTTP200을 UI 통과로 보고하지 않는다. API만 기존 Codex6.1 Sol/xhigh 설정으로 다시 시작해 코드 반영했고 provider가codex인 것을 확인했다. 기존 웹과 원본/수정 snapshot·이전 API 로그는 보존한다. 실제 모델 문장 재생성 검증은 수행하지 않았다.

## 남은 근본 문제

전체 명식의 조건·반대 작용을 종합해 돈의 벌이/축적/손실, 일자리/평가/보상, 인연과 기간별 도움·부담을 결론으로 만드는 판단 단계가 없다. 현재 수정은 이미 있는 설명을 잃지 않게 하고 분류의 뜻을 이해하도록 보강한 것이다. 057/060의 전체 종합 판정기·분야/기간 규칙·반대 사례 검증은 별도 구현이 필요하며 긴 정의/일반 조언이나 모델의 자의적 예측으로 대체하지 않는다. 기존 공개 내부점수 노출·음력30일·Codex 형식/근거ID 검증 실패도 이번 범위에서 해결하지 않았다.

## 추가 피드백: 본문4배 이상과 실제 모델 경로

2026-10-11 사용자: “실제 api로 해서 그래? 사주풀이 양이 지금보다 4개배 이상을 되어야해”, “모델 차이야? sol 6.1 xhight로는 이전처럼 자세히 나오는거야?”

요구를 product JSON `substantive_reading_feedback.2/main_reading_depth.1`에 보존한다. 기준은 현재03e3ab65의 항상 보이는 다섯 장 본문이며 접힌 근거·공지·제목을 제외한다. `publication.blocks[].text`에서 kind heading/availability_notice를 제외하고 공백과 마크다운 문자 `* #` 및 backtick을 제거해 집계하면 core230/love198/wealth164/career170/luck_flow341, 합계1103자다. 동일 기준으로 최소4배인4412자 이상이 요구다. 기존 고정 문단 수 금지보다 최신 직접 분량 요구가 우선하지만, 반복·용어 정의·한계 안내·허구 판단으로 길이를 채우는 것은 승인되지 않았다. critical 보류와 미지원 범위를 유지한다. **4배 본문 전달은 아직 구현·검증하지 않았다.**

현재03e3ab65는 실제 애플리케이션의 fallback ASGI 응답을 저장한 것으로 모델 호출0이다. 앞선7e3ea8ec는 실제 로컬 HTTP 요청에서 gpt-6.1-sol/xhigh를 호출했지만 제목·근거ID·요약 문장 검증 실패로 fallback으로 교체됐다. 실행 중 API provider는codex이며 새 모델 호출/모델 간 비교는 하지 않았다. 실제 HTTP/ASGI 여부와 생성 모델 성공 여부를 구별한다.

`category_reading`의 wealth는 provider와 관계없이 위치/의미 설명으로 교체되고, `reading_publication`의 core와 선택된 distinctive theme는 legacy 모델 본문을 게시하지 않는다. 따라서 모델이 장문을 생성해도 현재 화면이 장문으로 바뀐다는 보장은 없다. 현재 사례의 짧음으로 Sol6.1 자체의 한계나 모델 간 우열을 판정하지 않는다. 필요한 후속 작업은 공급된 판단의 깊이, 생성 계약과 검증 입력의 일치, 검증된 장문이 실제 게시되는 경로를 함께 구현하는 것이다. 검증을 느슨하게 해 알 수 없는 근거ID를 승인하거나 제한 없는 모델 판단을 게시하지 않는다.

OpenAI 공식 [reasoning effort와 verbosity 구별 예제](https://developers.openai.com/cookbook/examples/partners/aws/openai_models_with_amazon_bedrock#34-control-verbosity-from-reasoning-effort)를 실제 열람했다. 추론 노력과 답변 길이를 구별하는 일반 설명의 근거이며 Sol6.1의 특정 길이나 품질 보장은 아니다. 모델/프롬프트/provider/런타임은 이번 경로 확인에서 변경하지 않았다. 문서/정책 JSON의 기준값과 참조를 검사한다.

이번 추가 기록의 JSON/실제 기준값1103×4=4412·UTF-8·diff 검사 PASS. 별도 fallback 실제 loopback HTTP 회귀456 PASS/3 WARN/기존 유효음력30일 FAIL1, 외부 모델0, 격리 검사 서버 종료를 확인했다. 증거는 등록된 기존 root의 `user-story-depth-20261011.json`/`.log`에 보존한다. 실행 중 Codex API/웹은 유지했고4배 본문·모델 성능 비교를 검사한 것은 아니다.
