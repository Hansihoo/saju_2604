# Codex Runbook

2026-10-24 [074 만세력·Codex 테스트](planning/074-manse-sheet-and-codex-handoff.md): `pnpm dev:codex`로 기존 로그인/gpt-6.1-sol/xhigh를 사용하며 웹은 `http://127.0.0.1:5173`이다. 출생 입력 → 새 풀이 → **만세력 보기**에서 실제 원국/오행/접힌 십성·지장간을 확인한다. 미상 시주는 비우고 날짜 경계의 잠정 상태를 유지한다. 버튼은 기존 결과만 열며 새 모델 호출이 없다. 새 풀이 생성은 사용자가 직접 시작한다. 실행 준비/health와 실제 모델 생성 성공은 구별한다. 저장된 local-result는 원본 공급자/문구가 고정되어 있으므로 Codex 새 생성 테스트에는 처음 화면에서 다시 입력한다.

2026-10-23 [073 Codex 전환 이력](planning/073-api-key-source-recovery.md#2026-10-23-codex-전환-전후-이력-확인): 원대화의10/5 Codex 요청 뒤 로컬 프로필 전환은 확인했다. 다만 API `.env.local`은 기존 파일 부재를 확인한 후 새로 추가한 기록이며 키 파일 덮어쓰기 증거는 없다. 현재 Production은 공식 재조회에서도8/25의8fd02a67이다. 로컬전환과 상용 키누락의 인과관계, 과거 프로세스 환경의 키 전달 여부는 미확정이다. 새 모델/POST/제품/env/배포변경 없음, 복구는 계속Blocked다.

2026-10-22 [073 기존 API 키 읽기 진단](planning/073-api-key-source-recovery.md): 현재 Production에 POST1회/재시도0도 `missing_api_key` fallback/빈 attempts로 실제 OpenAI 호출0이다. 로컬 Process/User/Machine·프로젝트 파일에 키가 없고, 가짜 키 로더5/실행위치2/관련단위8은 통과했다. Vercel 팀/프로젝트 조회는 가능하나 env metadata403, 브라우저 신뢰 오류로 등록/Production 범위/배포 반영 여부는 미확정이다. 환경변수 확인 권한과 기존 유효 키 공급 경로가 확보된 뒤 복구를 이어간다. 현재 로컬 API8000/Web5173은 비응답이며 fallback 사용자 시나리오는 BLOCKED다. 과거 정상 서버·검증 기록을 현재 상태로 재사용하지 않는다. 제품/env/권한/배포/서버 변경 없음, 상용 복구 미완료.

2026-10-13 [072 실제 GPT-5.4 복구 요청](planning/072-restore-live-gpt54.md): 남은10/5 Preview2개도 실제 POST 각1회에서 missing_api_key fallback/빈attempts였다. OpenAI0, 새 결과 게시 없음. 사용자에게 채팅 대신 로컬 env에 인증 설정 또는 기존 설정 파일 경로를 요청했고 답이 pending이다. `generate-gpt54-072.py`는 인증 준비·explicit OpenAI 서버 실행 뒤에만 사용할 미실행 준비물이며 fallback을 GPT-5.4로 표시하지 않는다. 현재 서버/원본 Sol 결과와 과거 성공의 미확인 범위는 유지한다. 기존403을 다른 인증/비밀 저장소로 우회하지 않는다.

2026-10-12 [070 범위 정정](planning/067-production-provider-diagnosis.md#070-상용-실행-이력과-로컬-실행-이력의-범위-정정): 이 프로젝트의 상용 기본 경로는 OpenAI API이고 Codex는 로컬 테스트 옵션이다. 069의 로컬 Sol 성공으로 사용자가 보고한 과거 상용 성공을 설명하거나 반박하지 않는다. 과거 Production 로그는 보관 기간 초과400, 지표 schema404로 조회 불가. 환경 필터 없이 확인한 READY5개 중 추가10/5 Preview2개는 health200만 확인했고 모델 생성은 미검증이다. 현재 키 누락 관측과 과거 성공 여부를 분리한다. 새 추론·환경·배포·제품·서버 변경 없음, 상용 복구 미완료.

2026-10-12 [069 최근 이력 대조](planning/067-production-provider-diagnosis.md#069-최근-프로젝트-대화와-실행-이력-대조): 공식 도구로 프로젝트3대화109턴을 확인했다.10/5 GPT-5.4는 코드 기본값 설명과 실패한Codex 비교에 등장하며 실제사이트 성공receipt는Sol6.1/xhigh다. 기본값/요청모델/실제provider·model·attempt를 구별하고, “현재모델”이라는 과거 비용 설명을 상용5.4 성공 근거로 재사용하지 않는다. 최근 키 삭제나 모든 과거 미실행을 단정하지 않는다. 새 생성·환경·배포·서버 변경 없음.

2026-10-11 [067의068 후속](planning/067-production-provider-diagnosis.md#068-이전에-동작한-연결의-재사용-확인): 남은 이전Production2개도 공식 인증 후 실제preview 각1회에서fallback/missing_api_key였다. 현재 배포 포함3개에서 상용 연결 재사용 불가, 실제OpenAI추론0. 과거 성공 전체를 부정하지 말고 해당 주소/실행날짜로 대상을 특정한다. 보호 설정·환경·배포는 바꾸지 않았고 인증 링크/쿠키는 메모리에만 두고 비웠다.

2026-10-11 [067](planning/067-production-provider-diagnosis.md): 현재 공개 Production preview는HTTP200이어도 실제provider/model이fallback이고 `openai_api_key_missing`/`missing_api_key`로 OpenAI 호출을 건너뛴다. 현재 관측을 과거GPT-5.4 성공 여부로 일반화하지 않는다. 키 복구·배포 반영 뒤 실제 provider/model/diagnostics를 확인해야 상용 생성 성공이다. 현재 배포에는 최신 로컬reading/question 경로도 없다. 이 진단에서는 환경·배포·모델·제품코드를 변경하지 않았다.

2026-10-11 [064](planning/064-substantive-reading-recovery.md): 설명 복원·금전/직업 의미·현재/다음 주제 비교는 새 결과에서 확인한다. 이전 local-result7e3ea8ec는 원본으로 보존하며 수정 결과03e3ab65는 실제 fallback ASGI 응답이다. 신규 제품 모델 호출0, 독립 최종검토 content FAIL(전체충족partial), UI HOLD다. 코드 반영은 API만 기존Codex6.1 Sol/xhigh 설정으로 재시작했고 웹은 유지했다. 금전·직업·기간 종합 판정과 기존API 결함 해결로 보고하지 않는다.

2026-10-10 [063](planning/063-reading-conclusions-and-followup-coverage.md): 본문은 `natal_structure.conclusions`의 조건·근거가 연결된 제한된 결론을 사용한다. 분석 원본은 메모에 남고 전체 종합/분야·기간 판정은 여전히 미지원이다. 질문 응답 v3의 `sections.kind=reading`만 기본 본문, 나머지는 메모다. 다음 질문은 서버 응답 `followups`를 UI와 runtime-capture.3이 그대로 사용한다. 클라이언트/캡처에서 ID만 제거해 메뉴를 재생성하지 않는다. 변경 전 고정 local-result는 자동 갱신되지 않는다.

2026-10-10 [062](planning/062-five-chart-runtime-reinforcement.md): 임의 사례 검증은 `capture_runtime_reading --inputs <등록된 입력 JSON 절대 경로> --output <새 등록 경로>`를 사용한다. 입력 계약은 runtime-birth-inputs-v1/cases[{id,input}]이며 출생 필드 외 계산·판정 주입은 거부한다. 큰 독립 검토는 main과 공개 답을 함께 묶은 cohort별 새 job으로 실행하고 전체 source hash를 보존한다. 독립 검토와 실제 UI 확인의 범위를 구별한다.

2026-10-10 [061](planning/061-runtime-content-verification-skill.md): “런타임 검증해줘”는 프로젝트 [.agents/skills/saju-runtime-verification/SKILL.md](../.agents/skills/saju-runtime-verification/SKILL.md)를 사용한다. 실제 본문·접힌 근거·질문 메뉴·선택 답을 동결하고 쉬운 문구/궁금증 충족/후속 흥미와 약속 이행을 독립 검토한다. `apps/api`에서 `python -B -m app.tools.capture_runtime_reading --output <새 등록 절대 경로>` → `app.tools.runtime_reading_reviews prepare/evaluate`를 사용한다. CLI는 모델을 호출하지 않고 각 역할 job은 현재 대화의 별도 검토 에이전트가 처리한다. 코드/내용/UI와 실제 흥미를 구별하며 fixture·누락은 HOLD, 과거 검토를 재사용하지 않는다.

2026-10-10 [058](planning/058-natal-structure-before-symbol-hooks.md): 새 core는 `natal_structure`의 제한된 구조 풀이이며 태극은 개인 질문에 둔다. 관련 검증은 `tests.test_natal_structure`와 category/publication 테스트, `verify_category_reading`의 실제 publication/facts를 사용한다. 기존 local-result는 고정본이므로 새 개인 snapshot이 필요하다. known midnight pair의 조건부 구조·독립 대안을 검증하되 전체 critical 보류는 유지한다. 최종 강약/용신/기간 사건 판정은 미구현이며 검증에 유료 provider를 호출하지 않는다.

2026-10-09 [055](planning/055-supported-distinctive-themes-and-questions.md) 결과는 새 local-result snapshot을 생성해 확인한다. 현재 개인 입력(1988-11-20 23:30 남성/제천)은 critical 전체 보고서 보류를 유지하면서 검증된 날짜 관례 쌍에 한정한 보조 주제만 조건부로 제공한다. 이 입력의 reading/question 검증은 모델 호출 없이 가능하다. 일반 입력 회귀는 반드시 격리 fallback으로 실행하며 실행 중 Codex6.1 Sol/xhigh 설정을 바꾸지 않는다. 새 `features.*` 질문은 실제 조건이 없으면 unavailable이다. 대안 원본에 미계산 속성을 primary에서 복사하지 않는다.

2026-10-09 결과 표시/검증은 [053](planning/053-published-reading-and-folded-memos.md)를 따른다. 다섯 장 publication과 기본 접힘 메모는 새 `/saju/reading` fallback ASGI 응답 및 신규 local-result ID로 검증한다. 오래된 저장 결과의 문구/버전은 고정되어 있다. 유료 provider 검증 호출 없이 격리 ASGI로 검사하고 실행 중 Codex 설정은 유지한다. 내용 효용 실패와 기존 음력30일 사용자 시나리오 실패를 지우지 않는다.

This file explains the safest way to run the project from Codex Desktop or any restricted Windows shell.

## Quick rules

- 임시 결과 재열람은 개발 서버의 `/local-result/<32자리 임의 ID>`를 사용한다.
  `.dev-runtime/local-results/<ID>.json`의 실제 응답/입력을 기존 결과 화면으로 복원하며
  새로고침 때 계산이나 모델을 호출하지 않는다. 스냅샷은 Git/public/production build에
  넣지 않고 사용자 테스트가 끝나도 정리 요청 전까지 보관한다. [052](planning/052-temporary-local-result-url.md) 참고.

- Prefer managed background commands when Codex is asked to run the project.
- Do not start the backend with `uvicorn --reload` inside Codex unless you have already confirmed the shell can create Windows named pipes.
- If `pnpm dev` is used from Codex, the launcher now auto-disables backend reload, but `pnpm dev:bg:start` is still the safer default.

## Recommended commands

API/Codex 선택 실행은 [071](planning/071-dual-provider-execution.md)을 따른다.

```powershell
pnpm check:llm:openai
pnpm check:llm:codex
pnpm dev:openai
pnpm dev:codex
```

두 실행 명령은 같은 계산·판단·검증·게시 경로를 사용한다. API는 gpt-5.4/low,
Codex는 gpt-6.1-sol/xhigh를 기본으로 명시하며 `-Model`/`-ReasoningEffort`로
각 실행에만 변경할 수 있다. `-ApiOnly`는 웹을 다시 시작하지 않는다.
API 키는 기존 프로세스 환경/로컬 env 파일에서 읽고 파일·전역 설정을 덮어쓰지 않는다.
키·SDK 또는 CLI·로그인 사전 점검이 실패하면 기존 서비스를 중단하지 않는다.
check 명령은 추론0이며 `ready`도 실제 생성 성공이나 모델 가용성 보장이 아니다.
현재 API는 missing_api_key로 실제 생성 미검증, Codex는 로그인 준비 상태 확인이다.

Codex도 공통 strict JSON 스키마를 `--output-schema`로 전달한다. 두 공급자의
결과는 같은 본문·근거 검증을 거친다. `category_reading.source_context`의
`requested_writing_provider`, `writing_provider`, `writing_model`, `writing_status`,
`writing_fallback_reason`을 함께 확인한다. 실패한 생성은 fallback으로 남고
자동으로 다른 공급자를 호출하지 않는다. production에서 로컬 Codex 호출은 차단된다.

For the requested local Codex setup, install the locked dependencies with `pnpm install`,
sign in if needed with `pnpm exec codex login`, then run:

```powershell
pnpm dev:codex
pnpm dev:bg:status
```

This starts the local web/API using the project-pinned CLI, `gpt-6.1-sol`, `xhigh`,
read-only sandbox and a 600-second generation timeout. It uses the signed-in Codex
account rather than an OpenAI API key. The ignored `apps/api/.env.local` also keeps
this machine's local choice. CLI flags explicitly forward the requested effort;
global Codex preferences and production API defaults remain separate. For regression,
run the fallback-only HTTP verifier before restarting the services in Codex mode.

From the repository root:

```powershell
pnpm dev:bg:start
pnpm dev:bg:status
pnpm dev:bg:stop
```

Use these when Codex needs to start, verify, and later stop the services without holding the terminal open.

If a human is running the project in a normal terminal, this is still fine:

```powershell
pnpm dev
```

For regression and accuracy checks:

```powershell
pnpm ensure:skyfield
pnpm test:api
pnpm test:accuracy
pnpm verify:kasi
```

`pnpm ensure:skyfield` downloads and verifies the Skyfield `de440s.bsp` ephemeris before runtime. Normal API requests do not download this file.

`pnpm verify:kasi` requires `KASI_SERVICE_KEY` and is an explicit live API spot check, not a normal test step.

## What each command does

공통 특징051은 `python -B -m unittest tests.test_chart_characteristics tests.test_category_reading`로 공통 조합/비중/자료 누락과 날짜 관례 차이의 제한된 범위를 검사한다. 신규 `chart-characteristics-v1`은 겉글자·월지 본기·다른 기둥 지장간과 두 그룹을 이용하는 프로젝트 조건부 풀이이며 실제 능력/피해의 측정값이 아니다. 새 특징만 날짜 관례 후보를 검증·재파생하고 기존 full-report critical hold는 유지한다. `verify_category_reading`은 실제 보이는 새 본문과 접힌 메모/비교를 별도로 동결한다. 기존 동일한 prepare/evaluate로 세 역할을 검토하며 paid provider는 사용하지 않는다.

Independent verification jobs:

확인된 항목 보강(049)은 같은 category verifier로 실제 본문·잠정 표시·원본 정보 fact를 동결한다. `python -B -m unittest tests.test_reading_information tests.test_category_reading`로 발견/미발견·중복 기준·비활성/잘못된 match·pair·KO/EN·critical/미상·정밀 대운 경계를 검사한다. 정보 카탈로그/형식/문구/추출 버전은 interpretation 규칙과 독립이다. 일반 fallback 예시/숙제는 초기 표시에서 생략하며 원본 report는 보존한다. 역할 결과의 정보 증가 인정은 종합 본문 효용 PASS가 아니다. 유료/라이브 Codex로 검증하지 않고 작업 후 API를 Codex6.1 Sol/xhigh로 복원한다.

솔직한 문체 보강(050)은 promptv18/규칙 문구 `dokkaebi-2026-10-09.1`/정보 knowledge `.2`·문구 `.4`/분류 문구 `.5`/독립 `reading_voice`를 사용한다. 21개 규칙의 선택 조건·출처·판정 버전은 그대로다. 원본 사용 메타데이터의 화개 고독·공망 지연/약화·귀문관 집착이 용어 설명에서 빠지지 않는 회귀를 추가한다. 내부 대운 favorability/tone/rank 변화가 같은 사실/규칙에 새 길흉 판정을 만들지 않는 회귀를 검사한다. 조건부 부담과 실제 사용자 상태를 구별하며 종합 길흉 규칙은 미지원이다. 낯선 십성 이름을 메모로 옮길 때 실제 위치·주제는 본문, 이름·같은 위치·정밀 날짜는 메모에서 함께 확인한다. 실제 fallback 화면과 prompt 반영을 검증한 것이 live Codex 새 문장의 의미 검증은 아니다.

초기 다섯 분류 표시(048)는 `apps/api`에서 `python -B -m app.tools.verify_category_reading --output <새 절대 JSON 경로>`로 fallback ASGI snapshot을 캡처한다. 기존 `question_flow_reviews prepare/evaluate`로 세 역할을 독립 검토한다. 실제 full fallback과 critical/unknown 보류를 공급하며 구조 PASS와 본문 효용은 별개다. 모델 호출은 0, `/saju/basic` 검증과 별도다. 라이브 첫 결과는 `/saju/reading-stream`으로 full 보고서 하나를 기다리며 critical 해석은 생성하지 않는다.

For the additive basic-chart/question flow, use `pnpm verify:question-flow -Output <new-absolute-snapshot.json>` in an existing registered temporary directory. This forces fallback in its own process and captures actual ASGI facts/answers without model calls. Run `python -B -m app.tools.question_flow_reviews prepare` / `evaluate` from `apps/api` for saved independent questioner/answerer/supervisor jobs. See [043](planning/043-basic-question-reading.md). These jobs do not execute an API provider or model; Codex can process them separately. Missing reviews and fixture reviews remain HOLD. FAIL is saved and exits 1; invalid evidence or storage errors exit 2. HOLD exits 0 but never constitutes approval. After changes, capture a new snapshot and run each role against its new job; never reuse stale review hashes.

For the readable main body, add `-ReviewScope basic` to capture the four basic-body cases for semantic jobs while preserving all executed question checks. Prompt/rubric `2026-10-09.1` and review/report v2 require per-case readability/usefulness, information kind, learned information, literal visible quote and reason. Missing/duplicate cases or hidden/fabricated quotes are invalid. `code_status` and `content_usefulness` are separate: vocabulary-only basic content fails usefulness even if role verdicts and code checks pass. A direct answer to a selected fact question may pass independently. See [047](planning/047-reading-utility-recovery.md); the earlier [044](planning/044-useful-basic-reading.md)/[046](planning/046-plain-reading-and-folded-evidence.md) PASS receipts are historical, not user-utility approval. `/saju/basic` still supplies basic-overview-v2; this verification correction does not implement new interpretation/timing rules or change the critical guard. Keep original snapshots and new jobs/hashes; read large jobs in case-sized chunks.

```powershell
pnpm verify:codex-agents --help
pnpm verify:codex-agents run --transport fixture --output-dir <new-output-folder>
```

The output parent must exist; replace the placeholder with an actual path. Fixture is the default and does not call a model. `prepare`, `task`, `execute`, and `evaluate` can run one saved role independently. See `docs/ai/CODEX_AGENT_VERIFICATION.md` for contracts, ownership and explicit Codex evaluation. The existing fallback-only HTTP verifier remains separate.

- `pnpm dev:bg:start`
  Starts API and web as managed background processes and writes metadata/logs to `.dev-runtime/`.
- `pnpm dev:bg:status`
  Reports whether the managed API and web processes are running and healthy.
- `pnpm dev:bg:stop`
  Stops only the managed processes started by `pnpm dev:bg:start`.
- `pnpm dev`
  Starts the normal local development launchers. In Codex shells it automatically disables backend reload.
- `pnpm dev:api`
  Starts only the API launcher.
- `pnpm dev:web`
  Starts only the web launcher.
- `pnpm dev:api:direct`
  Runs the FastAPI server in the current shell without reload. Useful for manual debugging.
- `pnpm dev:api:reload`
  Runs the FastAPI server with reload. Use this only in a normal local shell.
- `pnpm dev:web:direct`
  Runs the Vite server in the current shell. Useful for manual debugging.
- `pnpm test:api`
  Ensures the Skyfield ephemeris, then runs API compile and unittest discovery with the LLM provider forced to fallback.
- `pnpm test:accuracy`
  Runs API tests, web build, reference table checks, diagnostic report generation, and golden validation.
- `pnpm ensure:skyfield`
  Downloads `de440s.bsp` if missing and verifies file size and SHA256.
- `pnpm verify:kasi`
  Runs selected live KASI API spot checks against the checked-in lunar reference table.

## Verification checklist

After startup, verify:

- API health: `http://127.0.0.1:8000/health`
- API docs: `http://127.0.0.1:8000/docs`
- Web: `http://127.0.0.1:5173`

Expected API health response includes:

- `status: "ok"`
- `service: "suju-insight"`

## Known failure mode

In Codex Desktop on Windows, `uvicorn --reload` can fail with repeated errors similar to:

```text
PermissionError: [WinError 5] Access is denied
```

When that happens, the reloader may keep writing tracebacks and rapidly grow `apps/api/uvicorn.stderr.log`.

## Recovery steps

1. Run `pnpm dev:bg:stop`.
2. Delete or truncate `apps/api/uvicorn.stderr.log` if it became very large from an older failed run.
3. Restart the managed services with `pnpm dev:bg:start`.
4. Check health with `pnpm dev:bg:status`.

## Instructions for future Codex runs

When asking Codex to run the project, point it to this file and ask it to use `pnpm dev:bg:start` first. Foreground commands such as `pnpm dev:api:direct` and `pnpm dev:web:direct` should be reserved for short manual debugging sessions.

Suggested prompt:

```text
Read docs/CODEX_RUNBOOK.md first, then run the project using the Codex-safe commands from that file.
```
