# 072. 기존 상용 연결 복구와 실제 GPT-5.4 결과 요청

## 요청과 확인 범위

사용자는 이전에 잘 동작한 API 연결을 찾아 복구하고 실제 GPT-5.4 사주풀이를 사이트에 보여달라고 요청했다. 같은 임의 입력1993-04-22 03:40 남성/제천을 유지한다. 과거 Sol 원고의 재생이나 fallback을 GPT-5.4 결과로 표시하지 않는다.

071 이후 아직 생성 요청을 보내지 않은10/5 main Preview 두 개의 기존 API를 추가 확인했다. 프로젝트 내 env 파일의 키 존재와 웹 공개 API 목적지도 확인했다. 웹은 `/api`를 사용하며 별도 외부 API 서버 주소는 없었다. 로컬 API env 파일은 Codex 설정만 있고 OpenAI 키가 없다. 설치된 Vercel CLI나 로컬 `.vercel/project.json`도 확인되지 않았다. 인증 저장소나 다른 프로젝트를 검색하지 않았다.

기존 Vercel 환경 조회403을 다른 자격 증명으로 우회하지 않았다. 공식 connector 목록 조회도403이어서 중단했다. 복구용 API 키를 임의 생성하거나 새 Gateway/공급자로 교체하지 않았다.

## 실제 실행 결과

공식 임시 배포 접근 도구로 Preview 인증을 사용했다. 최신 배포의 첫 접근 준비는 Vercel의 read_protection_bypass/internal_server_error500이었다. 직전 배포는 정상 접근했고, 최신 배포도 같은 공식 도구의 한 번 재시도로 접근됐다. 이것은 환경 조회403 우회가 아니라 별도 배포 접근의 일시적500 재시도다. 인증 쿠키는 origin별 메모리에만 두었으며 다른 origin과 POST 반복을 차단했다.

| 배포 | 실제 요청 | 응답 | OpenAI 호출 |
| --- | --- | --- | --- |
|10/5 `10ea42a`, e2j6pe0ew Preview | POST1회/재시도0, 약1.747초 | HTTP200, fallback/fallback, configured openai, missing_api_key, attempts=[] |0 |
|10/5 `1fb3303`, fedpg2lhv Preview | POST1회/재시도0, 약4.810초 | HTTP200, fallback/fallback, configured openai, missing_api_key, attempts=[] |0 |

067/068의10/11 Production3개 관측과 합쳐 보존된 다섯 배포 모두 확인 시점의 키 누락 응답이었다. Production을10/13에 새로 생성 요청한 것은 아니다. 이 자료로 과거 정상 동작을 부정하거나 키 누락 시점·원인을 확정하지 않는다.

배포 access 링크/쿠키는 메모리에서 비웠고 파일에 저장하지 않았다. browser 연결도 시도했지만 신뢰 연결 오류로 제어 불가였다. 다른 브라우저 제어 방식으로 우회하지 않았다. 제품 코드·운영 환경·배포·현재 API/Web을 변경하지 않았다. 실제 GPT-5.4 추론0이며 새 사이트 결과도 만들지 않았다.

## 인증이 준비된 뒤의 실행

필요한 입력은 실제 OpenAI API 인증이다. 키를 채팅에 보내지 않고 기존 지원 파일 `apps/api/.env.local`의 `OPENAI_API_KEY`에 설정하거나, 이미 키가 저장된 프로젝트 설정 파일의 경로만 알려달라고 요청했다. 파일 편집기 열기는 queued 상태다. 현재 pending 질문의 답 없이 키가 준비됐다고 가정하지 않는다.

등록 root의 `generate-gpt54-072.py`는 인증 준비 후 explicit OpenAI/gpt-5.4 서버에 같은 입력으로 생성 POST 한 번만 보내는 실행 준비물이다. 아직 실행하지 않았다. 실제 응답을 먼저 보존하고 provider/model/diagnostics/writing contract가 성공일 때만 새 결과 ID를 등록·저장·HTTP/no-store 검증한다. 기존 결과를 덮어쓰지 않으며 fallback은 새 GPT-5.4 결과로 게시하지 않는다. 실제 생성 성공 후 해당 새 URL을 브라우저에 열어야 요청 완료다.

## 증거와 상태

등록 root `.dev-runtime/five-chart-runtime-20261010`의 `preview-{preflight,request,response,receipt}-072.json`, 최신 배포 대응 `preview-*-latest-072.json`과 `recovery-observation-072.json`에 실제 결과·hash·미완료 상태를 보존한다. 생성 준비 스크립트 문법·JSON·hash·문서 링크를 확인한다. 제품 코드 변경이 없어 회귀·유료 모델 테스트는 추가하지 않는다.

**Blocked: 기존 인증 복구 정보/사용 가능한 API 키가 필요하다. 실제 GPT-5.4 생성과 새 결과 사이트 표시는 미완료다.** 과거 성공 연결이 없었다는 결론은 아니며, 기존 내용 FAIL과 알려진 제품 결함도 그대로 남는다.

## 기존 키 위치를 모르는 경우의 후속 경로

사용자는 인증 질문에 “몰라 잊었어”라고 응답했다. 기존 질문의 답은 위치 미상이며 다시 기억해내도록 요구하지 않는다. 실제 인증이 필요하다는 제약은 유지한다.

공식 OpenAI 문서에서 [OpenAI Developers 연동](https://developers.openai.com/learn/developers-codex-plugin#install-the-plugin)이 연결된 OpenAI Platform 앱을 통해 프로젝트 API 키 발급을 지원함을 확인했다. 공식 plugin 검색에서 OpenAI Developers를 찾았으며 확인 당시 installed=false였다. 설치/연결을 제안했지만 자동 설치·연결·권한 변경·키 발급은 하지 않았다. 연결이 실제 확인되면 이용 가능한 키 관리 기능과 기존 프로젝트 범위를 확인해 원래 GPT-5.4 생성 요청을 이어간다. 문서가 안내하는 최초 사용 시 새 대화 필요 여부도 고려하며 현재 대화를 임의 생성/이동하지 않는다.

수동 경로는 [공식 API 키 관리](https://platform.openai.com/settings/organization/api-keys)에서 새 프로젝트 키를 발급해 기존 로컬 설정에 넣는 것이다. [공식 키 관리 원칙](https://developers.openai.com/api/docs/guides/production-best-practices#api-keys)은 새 키로 애플리케이션을 갱신하고 동작 확인 후 기존 키를 폐기하도록 안내한다. 현재 기존 키를 폐기하거나 새 키가 발급됐다고 가정하지 않는다. 공식 키 페이지와 로컬 env 편집기는 queued 상태이며 화면이 열렸다고 주장하지 않는다.

이번 후속은 공식 안내/연동 검색/설치 제안뿐이다. 실제 인증·GPT-5.4 생성·새 사이트 결과는 미완료, 제품/환경/배포/서버 변경0이다.
