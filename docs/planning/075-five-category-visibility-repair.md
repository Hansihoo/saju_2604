# 075. 다섯 분야 표시 누락 수정

## 원인과 범위

사용자는 Codex 테스트 환경에서 사주의 특징과 연애·결혼운만 나온다고 지적했다. 기존 실제 날짜 경계 응답에도 다섯 section과 publication이 모두 있었지만, 서버는 `critical`과 `distinctive.status=conditional`일 때 보조 주제가 있는 분야만 `visible=true`로 덮어썼다. UI는 `visible=false`를 그대로 제외해 금전·직업·운의 흐름을 숨겼다. 과거 테스트도 이 잘못된 두 항목 표시를 예상값으로 삼고 있었다. 074의12화면 검사는 만세력 시트만 점검하고 다섯 분야 전체 표시를 놓쳤다.

작업은 표시 회귀 수정이다. 서버는 기존 다섯 항목을 모두 공개하고 UI는 옛 저장 응답의 숨김 flag도 적용하지 않는다. 보조 특징 존재 여부를 전체 분야의 표시 여부로 사용하지 않는다. 기존 본문/메모/계산 사실과 시간 미상·날짜 경계의 critical 종합 보류, 모델 미호출, 미지원 시기·금전/직업 종합 판단은 그대로다. 항목 제목 복원과 보류된 해석의 완성을 구별한다.

## 검증

한국어/영어의 정상·날짜 경계·시간 미상 JSON/stream에서 다섯 항목 표시와 보류/생성0을 검사한다. 이전 두 항목 flag를 가진 실제 저장 응답에서도 다섯 항목이 렌더링되는지 실제 브라우저로 재현한다. 관련 API·웹 타입/빌드/helper와 별도 fallback-only 사용자 시나리오를 실행한다. 사용자가 실행 중인 Codex 설정은 검증 때문에 fallback으로 바꾸지 않는다.

## 결과와 남은 범위

서버의 `visible`는 다섯 분야 모두 true이며 category copy는 `category-reading-copy-2026-10-24.1`이다. UI는 응답의 다섯 public chapter를 그대로 렌더링하므로 이전 `visible=false`가 저장된 결과도 복원된다. 원래 publication과 본문·메모·한계 문구는 바꾸지 않았다.

- 관련 API34건 PASS다. 일반·미상·날짜 경계의 KO/EN, JSON/stream5visible와 critical 생성0을 확인한다. 최초 실행은 새 EN 테스트가 기존 안내를 `conditional reading`으로 잘못 가정해1FAIL이었다. 실제 기존 문구에 맞춘 검사로 보정하고 전체34를 다시 통과했으며 원본 r0 로그를 보존했다.
- 별도 runtime capture/stream 관련30건도 PASS다. 계약 테스트가 출력한 역할 미실행 HOLD를 실제 독립 내용 검토의 통과로 취급하지 않는다.
- 웹 타입/격리 production build/helper14 PASS다. 원본 실제 fallback 저장4결과를390/320/1280에서 확인한12조합 모두 다섯 장과 목차가 표시되고 기존 본문 block의 문장이 같았다. 특히 원래 두 visible flag인 날짜 경계 원본에서5개를 확인했다. 가로넘침/콘솔오류0, UI검사POST0이며 앱 내부 브라우저 신뢰 오류 대신 별도Chromium을 사용했다.
- 실행 중 Codex를 fallback으로 바꾸지 않고 별도 loopback helper로 사용자 시나리오를 검사했다.456PASS/3WARN/기존음력30일FAIL1이며 helper 종료를 확인했다.
- Codex API만 기존 Sol6.1/xhigh 설정으로 코드를 다시 읽었다. 동일 날짜 경계 입력의 실제HTTP 응답은5visible/critical_hold=true/provider=deterministic/writing_status=not_called이다. 웹은 유지했다. 제품 모델 호출0이며 실제Codex 원고를 새로 생성한 검사가 아니다.

**표시 복구와 실제 풀이 복구는 다르다.** 금전·직업 장은 이 입력에서 원래의 종합 풀이 보류 문구가 보인다. 운의 흐름은 잠정 계산값과 기존 기간 자료를 보여준다. 다섯 제목이 보인다고 미지원 개인별 금전/직업/시기 판단을 채웠거나 궁금증 충족에 통과했다고 보고하지 않는다. 전체 종합 보류/기존 콘텐츠 FAIL과 상용 연결 공백도 유지한다.

원본 응답, 최초 실패/r0와 재검증 로그,12화면, 사용자 시나리오, live 응답과 재시작 전 API로그는 등록된 `.dev-runtime/category-visibility-20261024-01a16679`에 보존한다. 사용자 테스트 환경과 이전 저장 결과를 정리하지 않았다.
