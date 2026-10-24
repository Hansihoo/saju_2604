# 071. OpenAI API와 로컬 Codex 실행 정리

## 목표와 범위

사용자는 기존 API 처리 자료를 확인하고 API와 Codex 모두로 풀이를 처리할 수 있게 요청했다. 이미 있는 OpenAI Responses/Codex 분기와 같은 계산·판단·게시 계약을 재사용한다. 상용 기본 OpenAI/gpt-5.4와 로컬 Codex/gpt-6.1-sol/xhigh를 유지한다. 과거 로컬 Sol 자료를 과거 OpenAI 성공으로 표시하지 않는다.

현재 차이는 Codex가 출력 스키마를 프롬프트로만 전달한다는 점과, 로컬 Codex 설정이 있는 환경에서 API 실행을 명확히 선택할 전용 명령·사전 점검이 없다는 점이다. Codex CLI에도 네이티브 JSON 스키마를 전달하고 공급자 선택·설정 검사를 추가한다. API 키와 Codex 인증은 기존 지원 위치를 사용하며 비밀 값을 수집하거나 이전 Vercel403을 우회하지 않는다.

## 구현과 위험

- 기존 풀이·미리보기·상세의 호출/검증/실패 fallback은 유지한다. Codex 네이티브 스키마와 API strict 스키마를 공통 변환으로 맞춘다.
- 실행 전에 키 존재/SDK·CLI·로그인 상태를 확인한다. 실제 추론 없이 점검하며, API가 준비되지 않았으면 실행 중인 Codex 서버를 중단하지 않는다.
- 공급자별 로컬 실행 명령을 추가하고 프로세스 환경을 실행 후 복원한다. 두 모델을 동시에 자동 호출하거나 한 공급자 실패를 다른 공급자 성공으로 숨기지 않는다.
- 저장된 실제 원고를 양쪽 adapter에 재생해 같은 게시 본문·근거·프롬프트 계약을 검증한다. 재생은 실제 OpenAI 호출 성공 증거가 아니다.

원국 종합·금전/직업 개인 결론·시기 엔진과 기존 콘텐츠 FAIL은 이번 공급자 연결 수정으로 해결되지 않는다. 키가 없는 상용 환경을 복구했다고 보고하지 않으며 배포하지 않는다.

## 검증

공급자 상태 검사·네이티브 스키마·실행 환경 복원·양쪽 adapter와 critical0호출을 회귀 검사한다. 기존 실제 원고와 출력 양식으로 재생 검사를 하고 fallback-only HTTP 사용자 시나리오를 실행한다. 유료 추론은 회귀 검증에 호출하지 않는다. 증거는 이미 등록된 `.dev-runtime/five-chart-runtime-20261010`에 보존한다.

공식 자료: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs), [Codex exec](https://learn.chatgpt.com/docs/developer-commands#codex-exec). 실제 선택·권한·모델 가용성은 문서 예시만으로 성공 처리하지 않는다.

## 진행

선택 실행과 계약 정리는 완료했다. `structured_output_schema.py`를 기존 OpenAI 본문/미리보기/상세와 Codex CLI가 공유한다. Codex는 같은 strict 스키마 파일을 `--output-schema`로 전달하며, production에서 CLI를 시작하지 않는다. API/Codex 분기·실패 fallback·근거/본문 검증은 유지했다. 지식·판정·문구·프롬프트 버전은 바꾸지 않았다.

`provider_status`는 API 키 존재/SDK 또는 Codex CLI/로그인을 검사한다. 원문 인증 출력과 비밀 값은 출력하지 않는다. `ready`는 실제 생성·계정 모델 가용성을 검증했다는 뜻이 아니다. `start-dev-provider.ps1`은 점검에 통과한 뒤에만 기존 관리 서비스를 교체하고, 프로세스 환경을 finally에서 복원한다. 로컬 env 파일을 덮어쓰지 않으며 API에 Codex의 xhigh 설정이 그대로 흘러가지 않도록 실행별 모델·effort를 명시한다.

```powershell
pnpm check:llm:openai
pnpm check:llm:codex
pnpm dev:openai
pnpm dev:codex
```

웹을 유지하며 API만 바꿀 때는 실행 명령에 `-ApiOnly`를 붙인다. 모델·effort 변경은 `-Model`/`-ReasoningEffort`로 해당 실행에만 지정한다. 기존 OpenAI 키 로딩 위치와 상용 기본 모델은 유지했다. 새 환경 변수나 공개 API 요청으로 사용자가 공급자/명령/키를 주입하는 경로는 만들지 않았다.

분류 응답의 `source_context`에는 `provider-generation-v1` 메타데이터를 추가했다. 기존 `writing_provider`와 함께 `requested_writing_provider`, `writing_model`, `writing_status`(model_generated/fallback/not_called), `writing_fallback_reason`을 확인한다. critical 미호출은 모델 성공이 아니며 실패 후 기본 풀이도 원래 요청 모델의 성공으로 표시하지 않는다.

## 완료 검증과 남은 범위

- 전체 API579개 통과(199.426초), 앞선 관련98개 통과. 네이티브 schema 전달·production0호출·SDK/CLI adapter 성공/실패·없는 근거/잘못된 JSON·준비 검사·공통 스키마의 이름/enum/ref 보존을 검사했다. 웹 helper14개도 통과했다.
- `demo-065-raw-result.json`의 실제 Codex 원고를 두 adapter의 SDK/CLI 경계에 재생했다. 동결 사실과 as_of로 재구성한 입력·프롬프트·strict 스키마가 같고, 양쪽의 본문 publication·메모·실제 질문 메뉴가 원본 및 서로와 일치했다. 원본 요청 bytes를 복구한 것이 아니며 실제 GPT-5.4 호출0이다. 재생 결과의 provenance는 별도 wrapper에서 mocked_boundary_replay로 표시했다.
- 실제 로컬 점검은 Codex CLI 로그인 준비 정상, API는 missing_api_key/SDK 정상이다. API 점검 실패 전후의 호출자 환경 복원과 서비스 metadata 무변경을 확인했다. 설치된 CLI의 `--output-schema` 지원도 추론 없이 확인했다.
- 최초 fallback HTTP 검사는 기존 웹이 꺼져 URLError로 중단됐다. 원본 중단 기록을 보존하고, 당시 API/Web의 기록 PID와 포트가 모두 비활성인 것을 확인한 뒤 기존 로그/metadata를 보존하고 웹을 실행했다. 재검사는456 PASS/3 WARN/기존 음력30일 FAIL1, 외부 모델0, 격리 helper 종료 확인이다.
- 회귀 뒤 기존 Codex6.1 Sol/xhigh 프로필로 API를 실행했다. API health/provider와 웹 결과 문서/원본 snapshot 모두 HTTP200, snapshot no-store/원본 완전 일치다. 기존 결과를 다시 생성하거나 API 결과로 이름을 바꾸지 않았다. 새 네이티브 Codex 스키마를 통한 실제 추론이나 새 브라우저 시각 확인은 수행하지 않았다.

증거는 등록 root의 `tests-*-071*.log`, `dual-replay-receipt-071.json`, `replay-{openai,codex}-071.json`, `launcher-receipt-071.json`, `user-story-071*.json`, `live-service-receipt-071.json`, `services-before-071`에 보존한다. 새 추론0, 환경 파일·운영 환경·배포 변경0이다. **API 실제 생성은 키 부재로 미검증이며 상용 연결 복구가 완료된 것은 아니다.** 기존 종합 풀이/금전·직업 결론 공백·콘텐츠 FAIL·공개 점수 노출·음력30일 오류도 이번 수정 범위 밖이다.
