# Low-cost OpenAI Codex trial

검토일: 2026-10-05. 시험 버전: `openai-cheap-codex-2026-10-05.1`.

사용자 요청에 따라 Codex로 실행 가능한 저비용 OpenAI 후보를 실제 생성했다. **GPT-6 Luna와 GPT-5.6 Luna를 각각 두 번의 새 앱 맥락에서 비교했고, GPT-5.6 Luna는 native CLI에서도 한 번 결과까지 생성했다.** 비싼 Sol/Astra/일반 GPT-5.4는 시험하지 않았다. 운영 모델/설정/배포는 바꾸지 않았다.

이번 작은 표본에서는 5.6 Luna의 형식이 더 일관됐으나 재미·방향에서 비용을 더 낼 만큼의 개선을 확인하지 못했다. 6 Luna도 앱 원문 JSON이 한 번 깨져 바로 운영 승자로 선정하지 않는다. 입력/출력 계약과 fallback을 검토한 뒤 직접 API 비교가 필요하다.

## 가용성과 비용 필터

Codex CLI `0.144.1`, 기존 ChatGPT 로그인으로 app-server를 시작해 `initialize` → `initialized` → **`model/list`, includeHidden=true, limit=100**을 읽었다. pagination은 없었다. 이 조회는 thread/turn을 만들거나 모델을 생성하지 않았다. 노출된 이름은 `gpt-reserve`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`, `gpt-5.5`, `codex-auto-review`였다. 가격·범위가 확인되지 않은 hidden 모델도 시험하지 않았다.

- **CLI 저비용 가용 후보:** GPT-5.6 Luna. 실제 smoke generation 성공.
- **현재 앱 후보:** GPT-6 Luna / GPT-5.6 Luna. 제공된 모델 override로 모두 실제 최종 문구 생성. 정확한 server snapshot은 관측되지 않았다.
- **mini/nano:** 현재 CLI 목록과 앱 agent override에 없고 프로세스에 OpenAI API 키도 없다. 미실행이다. 공개 API 모델의 존재와 현재 Codex 계정에서 실행할 수 있는 모델을 구별한다.
- **비싼 모델 제외:** GPT-6 Astra, GPT-6.1 Sol, GPT-6 Sol, GPT-5.6 Sol/Terra, 일반 GPT-5.4. 이 시험의 별도 감독 모델 호출도 추가하지 않았다.

일반 텍스트 Standard, uncached input/output USD/100만 tokens. 아래 1,000회는 요청마다 input 10,000 + total output 3,000을 가정한 계산이며 실제 API 청구액이 아니다.

| 후보 | 입력 | 출력 | 가정 1,000회 | 실행 |
| --- | ---: | ---: | ---: | --- |
| GPT-6 Luna | $0.10 | $0.50 | $2.50 | 앱 2회 |
| GPT-5.6 Luna | $0.20 | $1.20 | $5.60 | 앱 2회 + CLI 1회 |
| GPT-5.4 nano | $0.20 | $1.25 | $5.75 | 현재 환경에서 미실행 |
| GPT-5.4 mini | $0.75 | $4.50 | $21.00 | 현재 환경에서 미실행 |

같은 토큰 가정에서 5.6 Luna는 6 Luna의 2.24배다. **이 시험은 Codex 계정 경로이며 직접 OpenAI API 호출/요금 측정이 아니다.** Codex 사용량을 무료라고 설명하지 않는다. [OpenAI Docs 가격](https://developers.openai.com/api/docs/pricing), [5.6 Luna 기능](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [Codex 모델 목록 계약](https://developers.openai.com/codex/app-server#list-models-modellist).

## 동결 입력과 반복 조건

기존 backend의 합성 S1/S2/S5를 fallback, `report_mode=none`, 기존 legacy 계산 정책, `as_of=2026-10-05T12:00:00+09:00`으로 준비했다. 준비 중 모델 호출은 0이다. 새로운 사주 계산/해석 규칙은 만들지 않았다.

| 과제 | 질문/목표 | 제공 범위 |
| --- | --- | --- |
| Direction | 미래 인연 주력 질문과 후보 2개, 필요 근거, 현재 가능한 오늘 콘텐츠의 관계 | 기존 capability ID/title/status, 제품 피드백, 필요한 기간·규칙 검토 |
| T1 | 오늘 같이 하는 일은 어디까지 맡는 게 좋을까? | 계 일간 / 임자 일진 / 겁재 / 축·자 합 → 자기 기준·역할 분담·협업 |
| T2 | 오늘 다른 사람과 의견이 다르면 어떻게 풀면 좋을까? | 병 일간 / 임자 일진 / 편관 / 월주 자와 같은 지지 → 책임·마감·반복 점검 |
| U1 | 연인은 언제쯤 만날 수 있을까? | 만남 시기 규칙·상호작용 미검토; 시기 답변 미지원 |
| U2 | 태어난 시간을 모르는데 올해 취업이 잘되는 달을 알려줘. | 시간 미상·직무 목표·취업 시기 규칙/기간 사실의 한계 |
| U3 | 다른 사람보다 내 운은 상위 몇 퍼센트야? | 비교 지표·모집단·표본 검증 없음 |

앱 후보마다 **같은 파일을 읽고 같은 여섯 과제를 묶어 생성하는 맥락 2회**, reasoning `low`, 새 agent history(`fork_turns=none`)를 사용했다. 실제 읽은 `exact-generation-prompt.txt`와 호출 메시지 `app-invocation.txt`, schema, task, source snapshot 및 hash를 생성 전에 저장했다. 이전 시험의 준비 packet과 실제 요약 메시지 차이를 이번 시험에는 만들지 않았다. 도구로 동결 파일 한 개를 읽는 것만 지시했으며 기술적 도구 차단을 보장한 시험은 아니다.

API strict schema와 앱의 ‘JSON을 반환하라’ 지시는 다르다. 앱 출력은 생성 후 검사했다. native CLI smoke에는 같은 prompt를 stdin으로 전달하고 `--model gpt-5.6-luna`, reasoning `low`, `--output-schema`, `--ephemeral`, read-only를 지정했다. CLI의 시스템/프로젝트 맥락은 앱과 달라 동일 조건의 세 번째 반복으로 합산하지 않는다. Schema 강제 요청을 전달한 것과 server의 strict 동작을 독립 입증한 것은 구별한다.

## 실제 원문과 편집 검토

| 항목 | GPT-6 Luna, 앱 1회차 | GPT-5.6 Luna, 앱 1회차 |
| --- | --- | --- |
| T1 강조 문장 | “오늘은 네 기준을 지키면서 함께할 몫까지만 맡아; 남의 짐까지 들면 네 손이 모자라.” | “내 몫의 기준은 또렷하게 세우고, 다른 사람의 일까지 대신 짊어지지는 마.” |
| T2 강조 문장 | “오늘 의견이 엇갈리면 해야 할 일과 마감을 먼저 맞춰; 기준이 보이면 부딪힘도 길을 찾아.” | “의견이 엇갈릴수록 해야 할 일과 마감을 눈앞에 놓고, 범위를 다시 맞춰 봐.” |
| 현재 제공할 방향 | “오늘의 내용은 당일 행동을 돌아보는 데 활용할 수 있어.” | “오늘의 내용은 자기 기준, 역할 분담, 책임 범위처럼 현재 행동을 점검하는 데 제공할 수 있으며…” |
| U1 답변 | “지금은 연인을 만날 시기를 말할 근거가 부족해. 검토된 만남 시기 규칙과 원국·대운·세운·월운의 상호작용이 필요해.” | “현재는 연인을 만나는 시기를 판단할 근거가 부족해.” |

**주 에이전트의 편집 판단이며 실제 사용자 연구/새 감독 모델 평가가 아니다.** 6 Luna는 ‘짐/손’ 비유와 부담/합의 속도를 사용해 장면을 조금 더 만들었다. 다만 ‘부딪힘도 길을 찾아’는 의미가 추상적이다. 5.6 Luna는 더 짧고 단정하지만 일반적인 안내에 머문다. 두 후보 모두 독립적인 방향 발견보다 제공된 관심사·capability의 요약에 가깝다. 구체적 의미는 전달하지만 기억/공유를 유발할 충분한 재미가 생겼다고 평가하지 않는다.

5.6 Luna는 `tradeoff`에 부담 대신 행동을 반복했다. 예: “도움을 주되 책임 범위는 분명히 해.”, “상대의 요구를 듣되 범위는 다시 합의해.” CLI도 같은 경향이다. 기계 형식 검사를 통과해도 해석 역할을 충족했다고 단정하지 않는다. 5.6 Luna의 direction reason/why 등은 존댓말이라 공용 캐릭터 문구로 그대로 쓰지 않는다. 공개 readings의 반말 검사와 구별한다.

모든 원문을 검토한 범위에서 허구의 만남/취업 월·확률·운의 백분위·전문가 승인 주장은 발견하지 않았다. 파싱 가능한 네 bundle은 facts/한계 배열을 정확히 보존했고 미지원 질문에 성격/타입 풀이를 붙이지 않았다. 깨진 6 Luna 2회차는 읽을 수 있는 문장에도 가짜 시기/백분위는 보이지 않았으나 유효한 구조 결과로 사용하거나 per-case 통과로 집계하지 않았다. 한계를 정직하게 말한 U1/U2/U3는 사용자가 원한 시기/순위를 제공한 정보 만족 성공 사례가 아니다.

## 결과 형식 검사

| 경로 | 최종 생성 | JSON/schema/기본 역할 계약 | 의미·흥미 |
| --- | --- | --- | --- |
| 앱 6 Luna 1회차 | 완료 | 통과 | 비유는 있지만 일부 추상적; 흥미 미입증 |
| 앱 6 Luna 2회차 | 완료 | **실패: JSON 구분자/괄호 오류** | 원문 보존, 구조 기반 검사 보류 |
| 앱 5.6 Luna 1회차 | 완료 | 통과 | 짧지만 평범함; tradeoff 역할 약함 |
| 앱 5.6 Luna 2회차 | 완료 | 통과 | 비슷한 문구; tradeoff 역할 약함 |
| CLI 5.6 Luna smoke | 완료, exit 0 | 통과 | 앱의 matched 반복과 별도; tradeoff 역할 약함 |

기본 계약 검사는 필드/type/enum/배열 수, 질문·순서·원본 ID/title/status, 정확한 facts/한계, 강조 답변 25–70자/구두점상 한 문장, 예시 표시, 노트 120자, 공개 역할의 일부 존댓말, 공유 문장 일치, 미지원 빈 역할을 확인했다. 앱에서는 4회 중 3회, 별도 CLI 1회가 통과했다. 이는 관심·의미·예측 정확도 점수나 일반 성공률이 아니다.

6 Luna 2회차는 U2 `limitations` 뒤에서 reading object가 먼저 닫히고 `share_sentence`가 밖으로 나온 원문이었다. **그대로 저장하고 고치거나 유효 JSON으로 재구성하지 않았다.** schema 지시만 있는 앱 실패를 실제 API Structured Outputs에서도 같은 확률로 실패한다는 근거로 사용하지 않는다. 비교당 두 맥락은 안정성/우열을 일반화하기에 작다.

## Native CLI 실행 증거

GPT-5.6 Luna 지정으로 동결 여섯 과제의 최종 출력이 생성됐다. 원문 prompt hash가 앱의 동결 파일 hash와 같으며 elapsed 36.436초, exit 0, 후처리 JSON/계약 통과다. CLI event 사용량은 input **21,858**, output **1,432**, cached input **0**, reasoning output **93**이었다. 이 값은 Codex 이벤트 usage이며 실제 API 청구를 관측한 것은 아니다. total output에 reasoning을 다시 더해 청구액을 계산하지 않았다.

이 실행에는 완료된 non-message item type `error`가 1개 있었다. 상세 원인은 당시 저장하지 않아 미확인이다. 최초 receipt의 `tools_used`가 모든 non-message type을 모으면서 이를 tool 실행처럼 표시한 집계 오류를 발견했다. 원 receipt는 보존하고 `validation.json`에 `actual_tool_item_types=[]`, `non_message_item_types=["error"]`로 정정했다. 생성/검사는 완료됐지만 모든 이벤트가 오류 없이 깨끗했다고 보고하지 않는다. 이후 harness classifier도 수정했으며 같은 호출을 재실행하지 않았다.

모델 호출은 **앱 4회 + CLI 1회**, harness retry/repair **0회**다. source 준비와 검사에는 모델을 호출하지 않았다. 실제 server snapshot과 앱 token usage, 직접 API latency/청구 비용, 다른 계정/CLI 버전의 접근 가능성은 미검증이다.

## 판단과 남은 작업

- GPT-5.6 Luna는 이 Codex CLI에서 실제 결과를 낼 수 있다. 이전에 거부됐던 GPT-6 Luna/Sol/GPT-5.4의 native 결과와 혼동하지 않는다.
- 이번 두 표본에서는 5.6 Luna의 JSON이 더 일관됐으나 재미·방향의 질적 우위를 확인하지 못했다. 같은 토큰 가정 2.24배 비용을 정당화하는 근거가 약하다.
- 6 Luna는 더 저렴한 문장화 대조군으로 유지할 수 있으나 실패 검증·fallback과 더 많은 사례/직접 API Structured Outputs 시험 없이 즉시 운영 교체하지 않는다. 모델에 방향·ID/상태·사주 판정을 자유롭게 맡기는 구조를 추천하지 않는다.
- Codex에 없는 mini/nano는 API 접근이 생길 때 시험한다. Solar/Gemini/DeepSeek 등의 다른 공급자는 이번 요청의 OpenAI/Codex 시험에 포함하지 않았다.

## 증거 파일

root: `.dev-runtime/agent-verification-20261005/openai-cheap-model-trial-20261005-2/`.

- `availability.json`, `discover_models.py`: 실제 model/list, generation/thread 0, 소유한 app-server 종료 확인.
- `source-snapshots.json`, `today-results.json`, `task.json`, `output-schema.json`, `exact-generation-prompt.txt`, `app-invocation.txt`, `trial-config.json`: 생성 전에 동결한 입력·schema·범위/hash.
- `app-luna6-r1.txt`, `app-luna6-r2.txt`, `app-luna56-r1.txt`, `app-luna56-r2.txt`: 실제 앱 최종 출력. 잘못된 JSON도 원문 그대로 유지.
- `cli-luna56-output.txt`, `cli-luna56-receipt.json`, `run_cli_smoke.py`: 별도 native 실행과 사용량/event receipt.
- `validate_outputs.py`, `validation.json`: 생성 후 기계 계약 검사와 event 분류 정정. source/application 모듈 import나 모델 호출 없음.

프로덕션 코드는 변경하지 않았다. 이번 턴에서는 생성된 실제 결과와 비교 스크립트/문서를 검증했으며 제품 build/HTTP 회귀를 새로 실행했다고 주장하지 않는다. 관련 [이전 문구 비교](MODEL_COPY_COMPARISON.md), [API 비용/후보 조사](API_COST_REVIEW.md), [사주 읽기 계약](SAJU_READING_AGENT.md)을 함께 본다.
