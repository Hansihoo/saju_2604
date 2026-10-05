# API cost and deployment review

검토일: 2026-10-05. 목적은 기존 배포를 현재 작업으로 교체하기 전에 호출 구조, 현재 단가, 입력 증가와 미확인 범위를 확인하는 것이다. 이번 검토에서는 배포·운영 환경 변수·모델을 변경하지 않았고 유료 추론을 실행하지 않았다.

호출 횟수와 코드 기본 모델은 기존 배포 소스와 같다. 새 지식/근거 계약으로 입력이 커졌으므로 비용 증가 가능성이 있다. 운영 환경 변수와 실제 청구 토큰을 확인하지 못했으므로 청구액의 전후 증가율은 확정할 수 없다.

## 배포와 설정 확인

- Vercel 프로젝트 `saju_2604`, 최신 production deployment `dpl_CA8Q45X6m9Kka7mGGnRkBPyQ5dWN`, READY. [배포 기록](https://vercel.com/signous/saju_2604/CA8Q45X6m9Kka7mGGnRkBPyQ5dWN).
- 배포 소스는 `saju` 브랜치의 `8fd02a67e4ffe7d84439ca82c6d5b9a826c371ec`. 현재 로컬 HEAD도 이 commit이며 이후 작업은 미커밋 변경이다. 전체 diff를 검토하고 배포할 revision을 확정해야 한다.
- 그 commit과 현재 `apps/api/app/config.py`의 기본 provider/model은 `openai`/`gpt-5.4`, reasoning은 `low`, 설정 출력 한도는 7,000이다.
- production 기본값은 generation attempt 1회, timeout 45초, repair 비활성, SDK retry 0회다. 로컬 기본값의 2회/repair 설정을 운영 설정으로 취급하지 않는다.
- Vercel 환경 변수 조회는 403으로 거부됐다. 실제 운영 provider/model/한도 override와 청구 내역은 미확인이다. 키나 환경 변수 값은 읽지 않았다.
- Codex 3역할 검증기는 개발용 독립 실행기다. 고객 API route가 사용자·질의·감독 작업을 매번 호출하지 않는다. 로컬 Codex provider는 운영 서버의 무료 API 대체가 확정된 구조가 아니다.

## 사용자 동작과 호출

아래는 OpenAI provider와 production 기본 한도를 적용한 코드 경로다. API 호출과 모델 호출을 구별한다.

| 동작 | 모델 호출 | 조건/출력 상한 |
| --- | --- | --- |
| 첫 결과 `/saju/preview` | 최대 1회 | 무료 미리보기 generation, 6,000 output tokens |
| 전체 풀이 `/saju/free-detail` | 최대 1회 추가 | 사용자의 명시적 요청; 화면 내 중복 요청 방지, 7,000 output tokens |
| 이미 받은 결과의 주제 전환·분석 노트 | 0회 | 받은 결과를 화면에서 전환/표시 |
| PNG 공유·표정 선택 | 0회 | 저장된 캐릭터 이미지와 기존 결과를 browser canvas로 합성 |
| 기존 시기 상세 `detail-prepare` / `detail-render` | 준비 0회, render cache miss 최대 1회 | 별도 legacy 상세 경로; render 1,200~2,400 output tokens |

preview/full generation 한도 식도 기존 배포 commit과 같다. 토큰 한도는 실제 사용량이 아니다. 모델의 보이지 않는 reasoning도 output 사용량에 포함되므로 보이는 문장 길이만으로 계산하지 않는다. [OpenAI 토큰 집계 설명](https://developers.openai.com/api/docs/guides/token-counting).

현재 첫 결과는 선택한 질문 하나만 생성하는 구조가 아니라 여러 주제의 결과를 함께 생성한다. preview/full에는 생성 결과를 재사용하는 backend cache가 없어서 같은 입력 재제출이나 새 세션에는 다시 호출할 수 있다. legacy 상세 cache는 메모리 TTL 900초/128건 기본값으로 serverless instance 간 공유나 재시작 후 유지가 보장되지 않는다.

## 입력 증가 측정

S2 합성 사례를 고정 `as_of=2026-10-05T12:00:00+09:00`, `report_mode=none`으로 계산했다. 현재 payload를 공통 기준으로 삼아 이전 입력에서는 새 `reading_plan`만 제거하고, developer prompt는 배포 commit의 실제 문자열과 현재 문자열을 비교했다. UTF-8 인코딩 후의 byte 수다.

| 텍스트 부분 | 비교 기준 bytes | 현재 bytes | 증가 |
| --- | ---: | ---: | ---: |
| JSON payload | 23,670 | 33,366 | 9,696 (+40.96%) |
| preview developer prompt + payload | 32,099 | 43,175 | 11,076 (+34.51%) |
| full developer prompt + payload | 36,529 | 46,840 | 10,311 (+28.23%) |

이는 추가된 읽기 계획과 prompt의 크기 비교다. 배포 당시 전체 엔진/문구를 별도 checkout으로 재실행한 역사적 요청 재현은 아니다. 사례 하나이며 message/schema formatting과 토큰화도 포함하지 않는다. **byte 증가율을 토큰·청구액 증가율로 사용하지 않는다.** 유료 모델 호출이나 API 토큰 집계 요청은 하지 않았다.

## 현재 공식 단가와 가정 계산

일반 텍스트 Standard 단가, USD/100만 tokens. 확인한 현재 단가이며 과거 청구 단가의 변경 이력을 검증한 표는 아니다.

| 모델 | 일반 입력 | cached 입력 | 출력 |
| --- | ---: | ---: | ---: |
| [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4) | $2.50 | $0.25 | $15.00 |
| [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) | $0.75 | $0.075 | $4.50 |

같은 토큰 사용량이면 mini의 요금은 70% 낮다. 모델 교체 후 출력량·오류·repair·품질이 같다는 뜻은 아니다. 이 프로젝트의 실제 mini 결과 품질은 미검증이다.

아래는 첫 검토의 비교다. 이후 요청으로 최신 OpenAI와 타 공급자를 추가 조사했으며 초기 저비용 우선 후보는 GPT-6 Luna였다. 실제 문구 시험 및 균형 모델 재조사 후의 우선순위는 아래 ‘균형 모델까지 넓힌 재조사’를 따른다. GPT-5.4 mini를 비용 후보의 최종 추천으로 취급하지 않는다.

예를 들어 요청 1회마다 **uncached input 10,000 + reasoning을 포함한 total output 3,000 tokens**를 사용한다고 가정하면 GPT-5.4는 $0.070/회, mini는 $0.021/회다. 같은 요청 1,000회는 각각 $70/$21이다. 실제 요청 측정값이나 월 예상 청구액이 아니다. 전체 풀이 요청, 별도 상세, 실패 후 재요청, hosting, 세금, 환율, 특수 요금 조건은 별도다.

현재 `response.usage`의 input/output/cached/reasoning token 집계는 저장하지 않는다. diagnostic의 문자 수·시도·출력 한도만으로는 청구량을 복원할 수 없다. token 요금은 입력/출력 usage에 단가를 곱해 계산하고 reasoning은 total output에 다시 중복 가산하지 않는다.

## 최신 저비용 API 후보 추가 조사

2026-10-05, 공식 공급자 가격표·모델/출력 계약 문서를 조사했다. 표는 일반 텍스트 입력, uncached, Standard/정가 기준 USD/100만 tokens다. `1,000회`는 공급자별로 **각 요청 input 10,000 + total output 3,000 tokens**를 사용한다고 가정한 단순 계산이다. 같은 한국어 텍스트가 공급자마다 같은 토큰 수가 되는 것은 아니며 실제 요금·속도·한국어 품질을 측정한 표가 아니다. cache read/write, 지역/장문 요금, 도구, 재요청, hosting와 세금은 제외했다.

| 후보 | 입력 | 출력 | 가정 1,000회 | 도입 판단 |
| --- | ---: | ---: | ---: | --- |
| GPT-5.4, 현재 코드 기본값 | $2.50 | $15.00 | $70.00 | 비교 기준 |
| **GPT-6 Luna** | **$0.10** | **$0.50** | **$2.50** | 같은 공급자·Responses/Structured Outputs; 저비용 비교 기준으로 유지 |
| GPT-6.1 Sol | $2.00 | $10.00 | $50.00 | 최신 균형 후보; GPT-5.4보다 낮은 동일 토큰 단가, 사주 API 품질 미측정 |
| GPT-5.6 Luna | $0.20 | $1.20 | $5.60 | 이전 세대 저비용 후보; GPT-6 Luna보다 높은 단가 |
| GPT-5.4 mini | $0.75 | $4.50 | $21.00 | 첫 검토 후보; 최신 저비용 후보보다 높은 단가 |
| Solar Mini 4 | $0.10 | $0.40 | $2.20 | 국내 공급자 저비용 후보; 새 provider 설정/호환 검증 필요 |
| Solar Pro 4 | $0.30 | $1.20 | $6.60 | 한국어 문구 비교 후보; Mini보다 좋은 사주 문구를 낸다는 결과는 없음 |
| DeepSeek V4.1 Flash (`deepseek-flash`) | $0.15~$0.30 | $0.60~$1.20 | $3.30~$6.60 | off-peak/peak 요금; 새 provider·실제 호환 검증 필요 |
| DeepSeek V4 Pro (`deepseek-v4-pro`) | $0.66~$1.32 | $1.98~$3.96 | $12.54~$25.08 | 현행 가격표의 Pro-0813; Flash보다 높은 단가, 한국어 문구 품질 미측정 |
| Gemini 3.1 Flash-Lite | $0.25 | $1.50 | $7.00 | 저비용 안정판; 2027-05-07 종료 예정 |
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 | $10.50 | Google이 신규 프로젝트에 제안하는 현행 Lite 후보 |
| Gemini 3.8 Flash | $0.75 → $1.50 | $3.75 → $7.50 | $18.75 → $37.50 | 현재 단가 → 2027-01-01 단가. Lite와 별도인 일반 Flash 비교 후보 |
| Claude Sonnet 5.5 | $2.00 | $10.00 | $50.00 | 최신 균형 후보; 새로운 provider/출력 계약 검증 필요 |
| Claude Haiku 4.5 | $1.00 | $5.00 | $25.00 | 가격 우선 후보보다 높아 이번 비용 절감의 첫 선택에서 제외 |

가격 출처: [OpenAI 현행 가격표](https://developers.openai.com/api/docs/pricing), [Upstage 가격표](https://www.upstage.ai/pricing/api), [DeepSeek 가격표](https://api-docs.deepseek.com/quick_start/pricing/), [Gemini 가격표](https://ai.google.dev/gemini-api/docs/pricing), [Claude 가격표](https://platform.claude.com/docs/en/about-claude/pricing). OpenAI 표는 272K 이하 short context 기준이다. DeepSeek peak는 중국 공휴일을 제외한 평일 UTC 01–04시/06–10시(한국 10–13시/15–19시)이며 그 외 off-peak다. 긴 reasoning을 켜면 output 사용량이 달라질 수 있다.

Upstage는 가격표에 Solar Mini 4의 **2026-10-10 UTC까지 70% 할인**을 명시한다. 할인 input $0.03/output $0.12에서는 같은 가정의 1,000회가 $0.66이다. Pro 4의 가격표 프로모션 구간도 2026-10-11T00:00:00Z까지 input $0.09/output $0.36을 기재해 같은 계산은 $1.98이다. 장기 예산/순위는 종료 후 정가를 사용하고 실제 계정 적용 조건은 가입/결제 화면에서 확인해야 한다. Solar Pro 2/3와 구 Solar Mini는 2026-10-30 종료 표기가 있어 신규 도입 후보에 넣지 않는다. [Upstage 가격/기간](https://www.upstage.ai/pricing/api).

Gemini 2.5 Flash-Lite는 $0.10/$0.40로 저렴하지만, 현재 공식 문서는 2.5를 과거에 적극 사용한 사용자 중심으로 제한하고 신규 프로젝트에는 3.5 Flash-Lite/3.8 Flash를 안내한다. 신규 계정에서 이용할 수 있는 최저가라고 추천하지 않는다. Gemini 3.1 Flash-Lite의 종료일도 같은 문서에서 확인했다. 무료 Gemini tier는 제품 개선 사용 `Yes`, paid tier는 `No`로 표기돼 이 비교는 paid 기준이다. [Google 지원 수명/접근 제한](https://ai.google.dev/gemini-api/docs/deprecations), [무료/유료 조건](https://ai.google.dev/gemini-api/docs/pricing).

### 이 프로젝트와의 적합성

- **GPT-6 Luna:** 공식 문서는 focused/high-volume 작업에 적합하고 Responses·Structured Outputs와 reasoning `none/low`를 지원한다고 설명한다. 현재 요청은 Responses, strict JSON Schema, `reasoning=low`를 사용하므로 문서상 주요 인터페이스가 맞는다. 이는 도입 비용이 가장 낮을 것이라는 엔지니어링 판단이며 실제 SDK/계정 접근·출력 품질 검증은 아니다. GPT-6는 cache-write 과금도 있어 GPT-5.4의 cache 조건을 그대로 비용에 적용하지 않는다. [모델/기능](https://developers.openai.com/api/docs/models/gpt-6-luna), [현행 모델 선택 안내](https://developers.openai.com/api/docs/guides/latest-model).
- **Solar Mini 4 / Pro 4:** 공식 Responses API가 두 모델, JSON Schema, OpenAI SDK, reasoning을 지원한다. 현재 코드에는 별도 API key/base URL/provider 라우팅이 없으므로 모델 이름만 바꿔 Upstage로 연결되는 것은 아니다. 지원하지 않는 parameter/strict 처리·응답 필드를 계약 테스트로 확인해야 한다. [Upstage Responses API](https://console.upstage.ai/api/responses).
- **DeepSeek Flash:** 공식 Responses API에 JSON Schema 형식이 문서화되어 있다. OpenAI와 모든 parameter/엄격성 동작이 같다고 보장하지 않으며 default thinking·가격 시간대·실패/사용량을 별도 adapter에서 처리해야 한다. 웹 본문 fetch timeout 뒤 같은 공식 페이지를 인증 없는 HTTP로 읽어 가격/Schema 지원을 확인했다. [Responses 계약](https://api-docs.deepseek.com/api/create-response/).
- **Gemini:** JSON Schema를 지원한다. 확인한 OpenAI 호환 예시는 Chat Completions이며 현재 Responses 호출을 model/base URL 변경만으로 쓸 수 있다고 판단하지 않는다. native/호환 adapter와 Schema 변환 검토가 필요하다. [Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output), [OpenAI 호환 범위](https://ai.google.dev/gemini-api/docs/openai).

사주 계산/판단은 기존 backend가 맡고 모델은 공급된 사실·선택 규칙의 문장화만 담당한다. 일반 코딩/추론 benchmark나 공급자의 한국어 홍보로 사주 정확도·흥미·전문성을 입증하지 않는다. 가격·지원 인터페이스는 조사 완료이며 다사례 API 품질/latency/token usage는 미검증이다. 이후 앱 에이전트의 한 사례 문구 비교는 아래에 별도로 기록한다. 모델/운영 배포를 바꾸지 않았다.

### 추천과 실제 비교 조건

초기 조사에서는 **GPT-6 Luna를 첫 후보**, Solar Pro 4를 한국어 문구 비교 후보, Solar Mini 4를 최소 비용 후보로 정했다. 같은 1,000회 가정에서 Luna는 현재 기본 모델보다 96.43%, 이전 mini 후보보다 88.10% 낮다. 절대 요금은 실제 토큰 집계 후 확인한다. 최신 우선순위는 아래 균형 모델 재조사로 보강한다.

실제 비교는 같은 동결 chart/rule/question과 출생시간 미상·지원하지 않는 시기 질문을 포함한 KO/EN 사례를 사용해야 한다. 필수 기준은 사실/분석 노트 정합성, 질문에 직접 답하기, 성향으로 시기 답변을 대체하지 않기, 보장·확률·날짜 날조 금지, JSON 통과, 짧고 기억할 만한 한국어다. 재미/의미/전문성은 모델 이름을 숨긴 별도 검토로 평가하고 latency p50/p95·사용량·실패 뒤 재요청까지 함께 비교한다. 현재 3역할 검증기의 transport는 fixture/Codex CLI이며 여러 유료 공급자를 직접 실행하는 기능은 없다. 비용만 비교한 이번 조사에서는 키·유료 추론·새 adapter를 사용/구현하지 않았다.

### 실제 문구 시험 후 판단 보강

같은 날 후속 요청으로 **앱의 GPT-6 Luna와 현재 채팅 설정을 상속한 후보**가 방향·고정 방향 문구·미지원 질문의 세 과제를 실제 생성했다. [문구 비교 보고서](MODEL_COPY_COMPARISON.md)에 원문과 기계 검사·별도 입력 눈가림 검토를 남겼다. 이 한 사례에서 상속 후보는 지금 제공 가능한 별도 오늘 카드까지 방향을 잡고 더 구체적인 캐릭터 문구를 썼다. Luna는 근거·미지원 한계를 지켰으나 필요한 자료 안내에 머물렀고 문체/한 문장 요구를 일부 놓쳤다. 두 후보 모두 원본 질문 ID를 바꿔 그대로 backend에 연결할 수 없었다.

**가격 근거의 ‘우선 시험 후보’를 전체 서비스 교체 추천으로 확대하지 않는다.** 콘텐츠 방향은 검토 가능한 지식/편집 기준으로 고정하고, 실제 요청의 저비용 문장화 적합성을 별도로 비교한다. 고객 요청마다 상위 모델과 Luna를 둘 다 호출하는 구조를 구현/권고한 것은 아니다.

CLI에서는 요청한 Luna/Sol/GPT-5.4의 9개 job이 계정·모델 호환 오류로 모두 거부되어 문구 생성은 0이다. 앱 상속 후보의 정확한 모델 ID도 관측되지 않아 Sol/GPT-5.4 API 성공 결과로 취급하지 않는다. 외부 API 키가 없어 Solar/DeepSeek/Gemini는 미실행이다. 가격표 가정 비용과 앱 문구 결과를 합쳐 실제 API의 품질당 비용을 계산하지 않는다. 운영 설정과 배포는 유지했다.

### 균형 모델까지 넓힌 재조사

2026-10-05 후속 요청: ‘Luna의 한계를 이유로 GPT-5.4에 머물지 말고 유사 예산의 더 좋은 후보를 찾아야 한다.’ 앞선 선택은 경량/최저가 후보에 치우쳤다. 공식 OpenAI Docs와 공급자 문서를 다시 읽어 GPT-6.1 Sol, Gemini 3.8 Flash, Claude Sonnet 5.5, DeepSeek V4 Pro를 보강했다. **GPT-5.4는 기존 비용/품질 비교 기준이며 유지 추천이 아니다.** 새 모델이 이 프로젝트에서 더 재미있거나 정확한 문구를 낸다는 실행 증거는 아직 없다.

- **저렴한 예산에서 우선 비교:** Solar Pro 4, DeepSeek V4.1 Flash. Solar Pro 4는 정가 기준 Luna 가정 비용의 2.64배이지만 1,000회 $6.60이고 영어·한국어·일본어 입력/출력을 명시한다. 최소 모델보다 넓은 작업을 대상으로 한 후보를 이 가격에서 시험한다는 선택이며, 한국어 사주 문구가 더 낫다는 사실은 아니다. [Solar 기능/가격](https://www.upstage.ai/blog/en/solar-pro-4), [현행 정가](https://www.upstage.ai/pricing/api).
- **경량 모델보다 넓은 해석·구성의 비교 후보:** Gemini 3.8 Flash. 2026-09 stable 모델이며 structured outputs, thinking low/medium/high를 지원한다. Google은 복합 작업용 Flash로 소개하지만 사주 문구 우위를 검증한 benchmark는 아니다. 현행 Standard $0.75/$3.75로 가정 1,000회 $18.75, **2027-01-01부터 $1.50/$7.50로 $37.50**이다. 현행 할인을 영구 정가로 취급하지 않는다. [모델 기능](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash), [기간별 가격](https://ai.google.dev/gemini-api/docs/pricing).
- **기존 GPT-5.4 예산에서 최신 균형 후보:** GPT-6.1 Sol과 Claude Sonnet 5.5는 일반 입력 $2/output $10로 같은 가정 $50이며 GPT-5.4의 $70보다 28.57% 낮다. Luna의 $2.50와 같은 가격대는 아니다. GPT-6.1 Sol은 Responses/Structured Outputs 및 low reasoning을 지원해 현행 호출과 문서상 가까우며, Claude는 별도 provider/계약 검토가 필요하다. ‘더 최신’과 문서상 성능 소개를 한국어 사주 품질 측정으로 바꾸지 않는다. [OpenAI 가격](https://developers.openai.com/api/docs/pricing), [Sol 기능](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [Claude 가격](https://platform.claude.com/docs/en/about-claude/pricing), [Sonnet 모델](https://platform.claude.com/docs/en/models/sonnet-5-5/overview).
- **DeepSeek Pro 보강:** 공식 현행 가격표에 `deepseek-v4-pro`/Pro-0813가 있어 input/output off-peak $0.66/$1.98, peak $1.32/$3.96을 확인했다. 가정 1,000회 $12.54~$25.08이다. 9월 초기 공지의 Pro→Flash routing 안내와 현행 가격표/업데이트가 일치하지 않으므로 이름만으로 실제 모델을 추정하지 않고 API 응답을 확인해야 한다. 공개 문서 웹 fetch 오류 후 인증 없는 HTTP로 현행 표 본문을 읽었다. [현행 가격](https://api-docs.deepseek.com/quick_start/pricing/), [변경 기록](https://api-docs.deepseek.com/updates/).

현재 비용·기능에 따른 **시험 순서는 Solar Pro 4 / Gemini 3.8 Flash를 우선**, DeepSeek Flash를 저렴한 대조군, Luna를 기존 초안 대조군으로 둔다. 기존 예산까지 허용하는 비교에는 GPT-6.1 Sol 또는 Sonnet 5.5를 추가한다. 이는 검토 우선순위다. 운영 승자 선정이나 공급자별 API 시험 완료가 아니다. 이후 동일 prompt bytes·schema·날짜/facts·reasoning을 보존한 여러 사례에서 재미·질문 적합성·근거·실패와 총 usage를 비교해 선정한다.

### 저비용 OpenAI의 Codex 실제 시험

후속 요청의 ‘비싼 모델 제외’ 조건으로 6 Luna / 5.6 Luna를 낮은 reasoning으로 각각 앱 두 회차, 5.6 Luna는 native CLI 한 회차 실행했다. [실제 시험 보고서](OPENAI_CHEAP_CODEX_TRIAL.md)에 동결 prompt·서로 다른 오늘 사실/미지원 질문·원문·검사와 CLI usage를 보존했다. 앱 JSON/기본 계약은 6 Luna 1/2, 5.6 Luna 2/2, 별도 CLI 5.6 Luna 1회 통과였다. 두 표본은 일반 안정성 순위를 입증하지 않으며, 의미·흥미는 기본 계약 통과와 별개다.

5.6 Luna는 더 단정하지만 재미/방향의 질적 우위가 보이지 않았고 tradeoff 대신 조언을 반복했다. 같은 토큰 가정에서는 1,000회 $5.60로 6 Luna의 $2.50보다 2.24배다. mini/nano는 현재 Codex 목록/앱 override에 없고 API 키도 없어 미실행이다. GPT-5.4/Sol/Astra 등 비싼 비교 호출은 0이었다. Codex 계정 사용량과 직접 API 요금을 구별하고, 이 결과로 운영 provider나 배포를 바꾸지 않았다.

### 실제 시험 후 교체 보류

2026-10-05 후속 피드백은 현재 구성을 유지하는 쪽이다. 추가 유료 추론이나 모델·공급자·배포 변경은 진행하지 않는다. 작은 Codex 표본에서 5.6 Luna의 문구/방향 개선이 확인되지 않았으므로 운영 교체를 보류한다. 이는 기존 GPT-5.4가 최저가 또는 품질 승자로 검증됐다는 뜻은 아니다.

OpenAI Docs를 다시 확인했다. 기존 가정(input 10,000 + total output 3,000, Standard/uncached/short context, 1,000회)에서 6 Luna $2.50, 5.6 Luna $5.60(2.24배), 6.1 Sol $50(20배), GPT-5.4 $70(28배)다. 실제 Codex 사용료나 API 청구액은 아니다. 현재 코드 기본값은 여전히 `openai`/`gpt-5.4`; Luna는 시험 후보이며 운영 적용된 모델로 설명하지 않는다. 운영 override는 앞선 403 이후 계속 미확인이다. 출처: [OpenAI 가격](https://developers.openai.com/api/docs/pricing), [5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna), [GPT-5.4](https://developers.openai.com/api/docs/models/gpt-5.4).

현재 권고는 모델을 올리기보다 질문별 필요한 사실·해석 규칙·문구 역할을 보강하는 것이다. 이는 다음 작업의 우선순위이며 이번 비용 질의에서 제품을 변경하거나 의미/흥미 향상을 검증한 것은 아니다. 아래 후보 시험과 비용 계측은 추후 작업으로 남긴다.

## 배포 전 권고와 남은 작업

후속 실행 요청은 원격 `main` 반영과 로컬 `gpt-6.1-sol`/`xhigh` 설정이다.
이에 따라 위 교체 보류는 로컬 실행에 한해 해제한다. 프로젝트 CLI 0.160.0의
실제 model/list에는 이제 6.1 Sol과 xhigh가 노출된다. 이는 0.144.1에서 수행한
이전 가용성/실패 기록을 바꾸지 않는다. 운영 API 기본값과 Codex 계정 사용량,
직접 API 청구액은 계속 구별한다. 실행·반영 결과는
[Main/로컬 실행 기록](MAIN_LOCAL_RELEASE.md)을 따른다.

1. **실측:** provider/model/attempt별 input/output/cached/reasoning 사용량을 PII 없이 집계한다. 원본 생년월일·풀이 전문을 비용 로그에 남기지 않는다. 운영 모델 설정과 실제 usage를 확인한 뒤 방문 수와 전체 풀이 선택률로 예산을 잡는다.
2. **입력 축소:** 현재 여러 주제 generation을 유지할 경우 실제 선택 규칙/사실·출력 역할·지원 한계만 모델에 제공한다. 질문 하나만 생성하는 방식은 재진입 호출 수와 결과 계약도 함께 검토해야 한다. 전체 근거는 backend에 보존한다.
3. **비용·품질 후보 비교:** 균형 모델 재조사에 따라 Solar Pro 4 / Gemini 3.8 Flash를 우선 비교하고, DeepSeek Flash/Luna를 저비용 대조군으로 유지한다. 기존 예산 비교에는 GPT-6.1 Sol/Sonnet 5.5를 추가한다. 동일 동결 facts/질문/출력 계약으로 질문 적합성·근거·한국어 재미와 usage를 검토한 후 선택한다. 규칙 기반 fallback도 token fee 없이 동작하지만 표현 다양성과 흥미를 따로 평가한다. 단계별 provider routing은 현재 구현되지 않았다.
4. **운영 교체:** 비용/품질 방침, 배포 revision, 환경 설정, 기존 WAF 운영 절차를 확정하고 production 교체를 검증한다. 이번 HTTP 회귀의 유효 음력 30일 입력 422 FAIL도 해결/범위를 결정해야 한다.

위 항목은 제안이며 이번 검토에서 구현하거나 게시하지 않았다. 제품 피드백 회귀는 API 관련 117 tests, 웹 helper 12, build/typecheck가 통과했다. fallback HTTP는 456 PASS / 3 WARN / 기존 음력 입력 1 FAIL이다. 실제 모델 의미·사용자 흥미·청구 비용은 이 회귀로 검증되지 않는다. [제품 편집 지식](PRODUCT_CONTENT_KNOWLEDGE.md), [공개 베타 운영 절차](../operations/PUBLIC_BETA_RUNBOOK.md).
