# 041. 실제 단계가 보이는 사주 대기 화면

작성일: 2026-10-07. 단계 계약 `saju-preview-progress-v1`, UI 문구 `waiting-progress-2026-10-07.1`.

## 목표와 범위

사용자가 “연애운 읽는 중”에서 오래 기다릴 때 요청이 전달되었는지, 계산이 끝났는지, 무엇을 기다리는지 알 수 있게 한다. 생성 속도를 개선했다고 주장하는 변경은 아니다. 기존 계산·판정·모델·토큰/재시도 설정을 유지하고 요청 1회의 실제 단계를 전달한다.

현재는 `/saju/preview`의 최종 JSON이 올 때까지 프론트가 처리 상태를 알 수 없었다. 타이머만으로 접수/계산/생성을 완료 처리하거나 전체 퍼센트·남은 시간을 만들어 표시하지 않는다. 이 원칙은 전문성을 암시하려고 실제 진행을 꾸미는 일을 막기 위한 표시 기준이다.

## 사용자 화면

| 서버에서 확인한 상태 | 대사 | 단계 표시 |
| --- | --- | --- |
| 아직 응답이 없음 | 출생 정보를 보내고 있어. | 정보 접수 진행 중, 나머지 대기 |
| accepted | 출생 정보 잘 받았어. 이제 사주부터 계산할게. | 접수 완료, 나머지 대기 |
| calculating | 태어난 곳과 출생 정보를 반영해서 사주를 계산하고 있어. | 접수 완료, 계산 진행 중 |
| writing | 사주 계산은 끝났어. 이제 네 풀이를 정리하고 있어. | 접수/계산 완료, 풀이 진행 중 |
| writing이며 경과 45초 이상 | 사주 계산은 끝났어. 풀이를 정리하는 데 시간이 걸리고 있어. | 단계는 그대로 유지 |
| 기존 JSON API 대기 | 풀이 결과를 기다리고 있어. | 확인되지 않은 단계에 완료 체크를 찍지 않음 |

작은 경과 시간은 실제 기다린 시간을 보여준다. 해당 응답에서 최근 30초 안에 프레임을 받으면 `응답 연결 유지 중`, 오래 받지 못하면 `응답 확인이 늦어지고 있어`로 표시한다. 이것은 모델이 새 토큰을 만들었다는 신호나 풀이 정확도의 증거가 아니다. 기존 JSON 대기에는 연결 상태를 임의로 붙이지 않는다.

캐릭터는 능청/깜짝/방긋을 천천히 바꾸며 졸림 표정은 제외했다. 표정은 장식이며 실제 단계/운세 판정이 아니다. 단계 설명에만 live status를 두고 초 단위 타이머는 live-off다. 전체 대기 영역을 aria-busy로 묶어 단계 안내의 발표를 지연시키지 않는다. 기존 reduced-motion CSS는 점 애니메이션을 끈다.

## 구현과 의존성

- POST `/saju/preview-stream`: 기존 preview 파이프라인을 1회 실행한다. 기존 JSON `/saju/preview`와 response 필드는 유지한다.
- `preview_stream.py`: 요청마다만 존재하는 큐와 Starlette의 기존 제한된 thread pool을 사용한다. 접수 → 실제 단계 → 최종 결과/오류, 대기 중 10초 heartbeat를 NDJSON으로 전송한다. 저장 job, 출생 데이터가 담긴 GET URL, 별도 모델 호출을 추가하지 않는다.
- `preview_orchestrator.py`: 실제 계산 시작만 알린다. `build_preview_response.py`: 명식·현재 기간·해석 payload 준비를 모두 마친 뒤 모델 문장화 직전에 `writing`을 알린다. 시간 미상/계산 기준과 사실·규칙 경계는 그대로다.
- `previewProgress.ts`: UTF-8 스트림/프레임 순서/버전/최종 결과/오류를 처리한다. 404/405의 미지원 endpoint만 기존 JSON 요청으로 전환한다. 네트워크 실패·중간 끊김·모델 오류는 자동 재생성하지 않는다.
- `useSajuInputForm.ts`: 서비스 화면에서만 진행 옵션을 활성화한다. 중복 제출을 막고 unmount에서 연결을 abort한다. 이미 시작한 동기 provider 작업은 즉시 강제 종료되지 않으며 기존 timeout을 따른다. 서버는 다음 단계 경계에서 연결 종료를 확인해 이후 생성을 시작하지 않는다.
- `waitingModel.ts`: UI 문구/대기 상태 표현/연결 신호/시간 형식의 순수 모듈. `DokkaebiWaiting.tsx`: 표시와 타이머. `experience.css`: 표현 스타일. 해석 규칙/knowledge copy와 별도 버전이다.
- `/design-lab?view=waiting`: 개발 모드에서만 합성 상태를 선택해 확인한다. 실제 사주 결과를 생성하지 않는다. 운영에서 단계 타이머를 만드는 장치가 아니다.

[FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)와 [MDN Readable Streams](https://developer.mozilla.org/en-US/docs/Web/API/Streams_API/Using_readable_streams)의 응답/브라우저 스트림 기능을 사용한다. 추가 패키지는 설치하지 않았다. 브라우저나 배포 프록시가 데이터를 모아 전달하면 실시간 표시가 늦어질 수 있다. 로컬에는 반영했으며 공개 배포·배포 프록시·실기기는 검증하지 않았다. 공개 배포 전 기존 요청 제한/timeout 정책에 새 경로가 포함되는지 확인한다.

## 검증 기록

- 웹 TypeScript/Vite build, 기존 reading helper12, 새 parser/transport/state 검사7 통과.
- 관련 API/파이프라인/guard 검사26: 실제 fallback ASGI stream의 단계·최종 response schema·기존 사실 일치, 느린 합성 작업보다 먼저 도착하는 접수/heartbeat, 1회 실행, 입력/계산/해석 사실 실패, raw 진단 누출 방지, 연결 종료 후 다음 생성 차단을 검사했다. 실제 Codex/OpenAI 호출은 하지 않았다.
- 브라우저 합성 preview: KO390, KO320 계산/기존 JSON 대기, EN320 3분 대기/연결 지연. 가로 넘침 없음, 확인된 단계만 완료, timer live-off, 새 콘솔 경고/오류 없음. 화면 크기는 종료 때 복원했다. 이는 실제 모델을 기다리는 사용자 세션 검증의 대체 결과가 아니다.
- 일반 HTTP verifier는 사용자 테스트 서버가 Codex여서 preflight에서 BLOCKED(2 PASS/1 FAIL)되었고 POST를 보내지 않았다. 이 보호를 해제하거나 검증 목적으로 모델을 호출하지 않았다.
- 같은 user-story verifier를 임시 in-process FastAPI ASGI client + 실제 Vite web-shell HTTP로 실행했다. 강제 fallback 및 요청 guard를 유지하여 **456 PASS / 3 WARN / 1 기존 FAIL**. 음력 1990-02-30 입력 422는 기존 문제다. WARN은 공개되지 않은 대운 십성, 실제 사용자 흥미, live 모델 의미 검증이다. API socket/전체 브라우저 흐름을 새로 통과했다고 기록하지 않는다.
- 실제 Codex 장시간 요청의 heartbeat 전달, 배포 프록시 buffering, 중간 네트워크 단절, 실기기/SR 발표, 체감 대기와 이탈 감소는 미검증이다.

현재 사용자 테스트 서버는 GPT-6.1 Sol/xhigh 설정을 유지한다. 다음 수동 테스트는 제출 뒤 접수/계산/풀이가 실제로 바뀌고 경과 시간과 연결 응답이 유지되는지 확인하는 것이다. 추가로 사용자를 기다리게 하는 강제 지연이나 가짜 ETA는 넣지 않았다.

증거는 소유권이 등록된 `.dev-runtime/reading-memo-20261007/`에 보존한다. 새 공유/업로드/분석 이벤트는 추가하지 않았다.
