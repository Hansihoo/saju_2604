# 067. 배포본의 상용 모델 호출 상태 진단

## 목표와 범위

사용자는 이전 GPT-5.4 사용 경험을 근거로 현재 상용 API 테스트와 배포 후 결과 제공이 가능한지 물었다. 로컬 인증 부재로 배포 환경까지 추정하지 않고, 현재 Production API의 실제 응답을 확인한다. 읽기 전용 배포 조회와 앞서 사용자가 요청한 실제 상용 결과 생성 한 번이 범위다. 배포·환경 변수·모델·제품 코드는 변경하지 않는다.

임의 입력은 기존 테스트와 같은 1993-04-22 03:40 남성/제천이다. 개인 경계 입력과 기존 local-result는 변경하지 않는다. 키 값은 조회하거나 증거에 기록하지 않는다. 이전 Vercel 환경 조회403을 다른 자격 증명 경로로 우회하지 않는다. 일반 회귀를 위한 유료 모델 호출도 하지 않는다.

## 확인된 결과

2026-10-11 13:39:34 UTC(한국22:39:34)의 `https://saju2604.vercel.app/api/saju/preview` 실제 POST는1회, 재시도0, HTTP200, 약1.985초였다. 응답의 `result.free_preview`는 다음과 같다.

| 항목 | 실제 값 |
| --- | --- |
| provider / model | fallback / fallback |
| prompt_version | saju-free-preview-v3 |
| warnings | openai_api_key_missing |
| diagnostics.configured_provider | openai |
| diagnostics.final_provider | fallback |
| diagnostics.fallback_reason | missing_api_key |
| diagnostics.attempts | 빈 배열 |
| pipeline_status.llm_formatting | skipped |
| pipeline_status.free_preview_formatting | fallback |

OpenAI 추론 호출은0이다. 배포 커밋의 `generate_free_preview.py`에서도 `OPENAI_API_KEY`가 빈 값/기본 자리표시자이면 OpenAI 호출 전에 이 경고와 fallback을 반환하는 분기를 확인했다. 따라서 현재 관측은 모델 성능이나 GPT-5.4의 응답 실패가 아니라 **배포 런타임에서 유효한 API 키를 읽지 못해 생성 자체를 건너뛴 상태**다. HTTP200과 화면에 글이 보이는 사실은 실제 모델 생성 성공의 증거가 아니다.

현재 로컬 결과 `a196da3547344cecb49e89bff1c85133`은 앞선065에서 생성한 Codex Sol6.1/xhigh 결과다. 이 결과와 Production의 fallback 응답은 별개다. 현재 기록만으로 과거 GPT-5.4 성공을 부정하거나, 키가 언제·왜 사라졌다고 단정하지 않는다. 보존된 로컬 기록의 Sol 성공/5.4 미지원 실패도 모든 과거 실행 이력을 대표하지 않는다.

## 배포 버전과 다음 복구 조건

읽기 전용 조회에서 최신 Production 배포는READY, 커밋 `8fd02a67e4ffe7d84439ca82c6d5b9a826c371ec`이다. 공개 OpenAPI에는 기존 preview/free-detail/상세 prepare-render 경로가 있으며, 현재 로컬의 `/saju/reading`과 질문 경로는 없다. 따라서 최근 로컬 풀이 개선을 현재 배포본에서 검증했다고 보고할 수 없다. `/api/health`는200이지만 새로운 `/api/verification/provider`는404다.

상용 생성 복구에는 Production 함수가 실제 `OPENAI_API_KEY`를 읽도록 환경 설정을 복구하고, `SAJU_LLM_PROVIDER=openai`/`OPENAI_MODEL=gpt-5.4` 설정과 배포 반영을 확인해야 한다. 이후 사용자가 요청한 실제 결과의 provider/model/diagnostics로 성공을 확인해야 한다. 기본 모델명이5.4라는 설정만으로 성공 처리하지 않는다. 키 복구와 최신 코드 배포는 이번에 수행하지 않았으며, 풀이 내용 FAIL과 기존 API 결함도 별도 미해결이다.

## 증거와 검증

이미 등록된 보존 root `.dev-runtime/five-chart-runtime-20261010`에 `production-request-067.json`, 요청 스크립트/로그, `production-response-067.json`, `production-receipt-067.json`, `production-observation-067.json`, `production-deployments-067.json`을 보관한다. 실제 응답 hash·진단 필드·빈 호출 목록을 검사했다. 최초 receipt는 존재하지 않는 `generation_diagnostics`를 읽어null로 기록했으므로 원본을 유지하고, 실제 `result.free_preview.diagnostics`를 읽은 observation을 추가했다. 기존 실패를 덮어쓰지 않는다.

변경은 진단 문서/진행표/작업 기록뿐이다. 제품 코드·계산·프롬프트·런타임 설정이 바뀌지 않아 모델/회귀 테스트는 추가하지 않는다. 문서 링크·증거 JSON·diff를 확인한다. 서비스와 기존 결과는 보존한다. 상용 모델 생성은 미복구 상태이며 새로운 브라우저 시각 확인이나 풀이 품질 승인을 주장하지 않는다.

## 068. 이전에 동작한 연결의 재사용 확인

사용자는 “이전에는 잘 되었을테니 그걸 이용하면 되는 것 아냐?”라며 이전 연결의 재사용을 요청했다. 목표는 남은 이전 배포에서 실제 상용 생성 연결을 찾는 것이다. 현재 프로젝트의 READY Production 배포를 조회하니 현재 배포 외에 두 개가 남아 있었다. 배포를 롤백하거나 최근 로컬 풀이를 구버전으로 교체하지 않고, 같은 임의 입력의 기존 API 응답으로 연결만 확인한다.

두 구버전의 공개 health 주소는 Vercel 로그인 페이지로 이동했다. `vercel:access-protected-vercel-deployment` 지침과 공식 Vercel access/fetch 도구로 기존 인증을 사용하니 모두 실제 API health200이었다. 인증 링크와 쿠키는 메모리에만 두고, 요청은 확인된 동일 origin으로 제한했다. 보호·환경 설정을 변경하거나 이전403 환경 조회를 우회해 API 키를 추출하지 않았다.

| 이전 배포 커밋 | 실제 preview 요청 | provider / model | 원인 | OpenAI 호출 |
| --- | --- | --- | --- | --- |
| 3288e7a / 2026-06-21 | 1회, HTTP200 | fallback / fallback | missing_api_key | 0 |
| aa3bcf8 / 2026-06-20 | 1회, HTTP200 | fallback / fallback | missing_api_key | 0 |

두 응답 모두 `openai_api_key_missing`, configured_provider=openai, 빈attempts였다. 067의 현재 배포를 합쳐 현재 접근 가능한 Production3개에서는 재사용할 상용 연결을 찾지 못했다. 이번 두 요청은 사용자가 요청한 기존 연결 결과 확인이며 회귀용 유료 호출은 아니다. 실제 OpenAI 추론은 합계0이고 POST 재시도도0이다. 두 번째 인증 준비 중 REPL 함수가 이전 origin을 참조해 origin guard가 POST 전에 거부한 기록은 별도로 남겼고, origin/session을 명시적으로 전달하는 helper로 같은 검사를 유지해 한 번만 POST했다.

프로젝트 `.dev-runtime`의6MB 이하 JSON에서 provider 메타데이터만 확인했을 때 openai provider 기록은 없었다. 이것은 보존된 일부 파일의 확인일 뿐 모든 과거 실행의 증거가 아니다. 확인된 실제 Codex 성공과 상용5.4 성공을 섞지 않으며, 사용자가 과거 다른 주소나 실행 환경에서5.4를 사용했을 가능성을 부정하지 않는다. 해당 성공 화면의 주소 또는 대략 실행 날짜를 비밀정보 없이 질문했다.

등록 root의 `previous-health-068.json`, 각 `previous-request/start/response/receipt-068-{0,1}.json`, `previous-preflight-068-1.json`, `previous-observation-068.json`에 원본 응답과 현재 결론을 보존했다. 입력 bytes가067과 같고 진단 필드와 response hash가 일치함을 검사했다. health 진단의 로그인 이동 query는 제거했고 인증 메모리도 비웠다. 제품/설정/배포 변경과 브라우저 시각 검증은 없으며, 이전 연결 재사용과 상용 생성 복구는 미완료다.

## 069. 최근 프로젝트 대화와 실행 이력 대조

사용자는 “이 프로젝트에서 처리된거고 몇일 안되었어. 과거 내역 찾아봐”라고 했고2026-10-12 계속 진행을 요청했다. 공식 `list_threads`/`read_thread`로 현재 프로젝트 대화3개의 모든 반환 페이지109개턴을 확인했다. 대상은 **사주 풀이를 재미있게 만드는 말투 추천**(83턴,10/3~10/10), **사주풀이 문장 문제 원인 찾기**(25턴,10/10~10/12), **오늘의 사주 심층 풀이**(1턴,10/11)다. 보관 대화 조회에는 항목이 없었다. 비공개 대화 DB·다른 프로젝트·인증 저장소를 검색하지 않았다.

다음은 한국 시각이며 정확한 메시지 ID와 원문은 `history-evidence-069.json`에 연결했다.

| 과거 시점 | 대화·실행에서 확인된 내용 | 의미 |
| --- | --- | --- |
| 10/5 16:16 시작한 비용 검토 | “현재 코드 기본값은 기존 배포와 같은 gpt-5.4”, 실제 운영 설정은403으로 미확인 | 기본 모델 설정 설명이며5.4 실행 성공 증거가 아님 |
| 10/5 17:02 시작한 모델 비교 | 처음에는 Codex로5.4 비교 가능하다고 안내했으나 이후 미지원 오류와 문구 미생성을 알림 | 사전 가능성 안내와 실제 실행 결과를 구분해야 함 |
| 10/5 모델 비교 receipt3개 | direction/copy/unsupported 모두 requested_model=gpt-5.4, transport=codex_chatgpt, status=error, exit_code=1, 계정 방식에서 모델 미지원 | OpenAI API의5.4 성공이 아니며 당시 Codex 비교도 실패 |
| 10/5 22:37 시작한 로컬 실행 | 사용자가 “codex 6.1 xhigt”를 요청했고 실제 생성 모델gpt-6.1-sol을 확인 | 최근 정상 사이트 생성 연결은 Codex Sol6.1/xhigh |
| 같은 로컬 실행 receipt | HTTP200, report_provider=codex, model=gpt-6.1-sol, diagnostic attempt success, 약277.141초, generation_requests=1 | 모델 이름 설정만이 아닌 실제 성공 기록 |

당시 비용 설명 일부는 코드의5.4 기본값을 “현재 모델”처럼 표현했다. 운영 모델은 미확인이라고 뒤에서 설명했지만, 기본값·Codex 비교·사이트 실제 생성의 구별이 일관되게 전달되지 않았다. 사용자가 실제5.4를 쓴 것으로 이해한 혼동 가능성을 설명하는 근거다. 실제 모델 기록을 확인하기 전에 최근 성공 주소를 사용자에게 다시 요구한 대신 이 대화를 먼저 조회했어야 한다.

확인 범위에서 최근 OpenAI API GPT-5.4 성공 기록은 발견하지 못했다. 확인된 사이트 성공은 Sol6.1/xhigh이고, GPT-5.4는 코드 기본값과 실패한 Codex 시험에 등장한다. 키가 최근 삭제됐다고 단정할 증거도 없다. 다만 삭제된 대화나 현재 조회되지 않은 실행 이력까지 부정하지 않으며,10/5 계정 미지원 오류를 현재의 전체 모델 지원 상태로 일반화하지 않는다. 이번에는 새 모델 호출·환경 설정·배포·서버 변경을 하지 않았다. 상용 생성 복구와 풀이 내용 보강은 별도 미완료다.

`history-evidence-069.json`은 대화 제목/turn/message ID/UTC·한국 시각/관련7개 원문을, `history-receipts-069.json`은 기존 실제 receipt4개와 source hash를 보존한다. 예전 live receipt의 최상위success는null이라 이를 성공 근거로 사용하지 않고 HTTP200·provider/model·diagnostic attempt success를 검사했다. JSONL8개 이벤트와 보존log의 모델 메타데이터에서도 추가5.4 성공은 확인되지 않았다. 제품 코드가 바뀌지 않아 새 모델/회귀 호출은 하지 않으며, 증거 hash·원문 연결·UTF-8·문서 링크와 diff를 검증한다.

## 070. 상용 실행 이력과 로컬 실행 이력의 범위 정정

사용자는 “상용화버전에서는 codex를 못쓰잖아. 그래도 잘 되었어.”라고 상용 배포에서의 정상 동작을 다시 설명했다. 069에서 확인한 Sol 성공은 로컬 실행 기록이다. 이를 사용자가 말한 상용 성공의 원인으로 연결한 답변은 범위를 잘못 적용했다. 과거 설명의 모호함만으로 사용자가 상용 실행을 혼동했다고 판단할 수도 없다. 069 원본은 보존하되 결론은 **조회된 로컬 기록에서 Sol 성공을 확인했다**로 제한한다. 사용자가 보고한 과거 상용 성공은 현재 자료로 확인하거나 반박하지 못했다.

프로젝트의 `config.py`와 `PROJECT_PROFILE.md`는 상용 기본 경로를 OpenAI API, Codex CLI를 개인 로컬 테스트 옵션으로 구분한다. 코드 기본값 openai/gpt-5.4는 과거 실제 호출 모델이나 배포 환경의 설정을 입증하지 않는다. 067/068의 missing-key 응답 역시10/11 관측이며, 과거에도 같은 상태였다는 증거가 아니다.

공식 Vercel 도구로 추가 확인한 범위는 다음과 같다.

| 확인 대상 | 실제 결과 | 판단 범위 |
| --- | --- | --- |
| Production 과거 로그:10/1~10/11 13:30 UTC | HTTP400, 요청 기간이 Hobby 로그 보관 기간을 초과했다는 응답 | 과거 모델 호출 여부를 조회할 수 없음. 과거 성공 부정 근거가 아님 |
| Production 최근30분 로그 | 조회 성공, 반환된 requestPath 그룹0개 | 해당 최근 창에 반환 기록이 없을 뿐 과거 실행을 설명하지 못함 |
| Observability schema | HTTP404, Observability Data not found | 추가 지표 조회를 진행하지 않음 |
| 환경 필터 없는 배포 목록 | READY5개: 기존 Production3개와10/5 main Preview2개, 다음 페이지 없음 | 앞선067/068은 Production3개만 확인했음을 명시 |
|10/5 최신 Preview `1fb3303`와 직전 Preview `10ea42a` | 공식 인증 GET health 각각 HTTP200/status=ok | 서버 응답만 확인. 모델 생성·OpenAI 연결 성공은 미검증 |

Preview의 확인 주소는 `saju2604-fedpg2lhv-signous.vercel.app`와 `saju2604-e2j6pe0ew-signous.vercel.app`다. 두 배포를 새로 생성하거나 승격하지 않았다. 기존 환경 조회403을 다른 인증 수단으로 우회하지 않았고 API 키를 읽거나 요청하지 않았다. 새 추론·생성 POST·환경·배포·제품 코드·서버 변경은0이다. 로그 보관 기간을 변경하거나 유료 관측 기능을 활성화하지 않았다.

등록 root의 `deployment-history-observation-070.json`은 비밀정보를 제외한 도구 오류, 배포 목록, health 관측과 결론 범위를 보존한다. 인증 링크·쿠키·응답 헤더·키 값은 저장하지 않는다. JSON·조회 결과 정합성·문서 링크·UTF-8·diff를 검증하며 제품 코드 변경이 없어 기능 회귀/모델 호출은 추가하지 않는다. **상용 생성 복구, 과거 정상 연결의 특정, 키 누락 원인·시점은 여전히 미완료**다.
