# 임시 로컬 결과 주소

사용자 요청: 결과가 열린 탭이나 시작 주소가 아니라, 주소를 클릭하면 곧바로 결과를 읽을 수 있어야 한다.

- 목표/유형: 개발용 결과 재열람 경로. 출생 입력과 모델 재호출 없이 저장된 서버 응답을 기존 화면으로 표시한다.
- 영향 범위: Vite 개발 middleware, 개발 전용 React 진입, ServicePage의 복원된 질문 입력 전달. 계산·판정·말투·API provider는 변경하지 않는다.
- 계약: `/local-result/<32자리 임의 ID>`에서 `local-result-snapshot-v1` 파일을 읽는다. 파일에는 실제 backend 응답과 선택 질문용 입력을 함께 보관한다. 주소에 생년월일을 넣지 않는다.
- 보관: `.dev-runtime/local-results/<ID>.json`. Git ignore 대상이며 public/와 production build에 넣지 않는다. thread artifact ledger에 등록하고 사용자가 정리를 요청할 때까지 보관한다.
- 접근: middleware는 개발 서버에서만 동작한다. loopback 요청만 허용하고 cross-site 요청은 거부하며 no-store로 응답한다. ID 형식과 realpath의 부모 경계를 확인한다. production/preview에는 snapshot endpoint가 없다.
- 표시: 기존 ServicePage/분류 본문/접힌 풀이 메모/질문과 표정 선택을 재사용한다. 질문은 저장된 입력으로 기존 deterministic API를 사용한다. 저장 당시의 원본 버전과 날짜이며 최신 풀이로 자동 재생성하지 않는다. 규칙이 바뀌면 기존 질문 버전 불일치 안내를 유지한다.
- 한계: 이번 개인 결과는 날짜 관례 차이의 기존 조건부 결과다. 원국 길흉/사건 시기 종합 보강은 별도 미구현 상태다. 이 경로는 콘텐츠 효용 승인이나 공개 공유 기능이 아니다.

## 검증

- 실제 요청 정보: 1988-11-20 23:30 / 남성 / 양력 / 제천시. 별도 fallback ASGI에서 원본 응답을 저장하고 戊辰·癸亥·庚辰·丙子와 conditional 상태를 대조했다. 모델 호출 없음.
- 웹 타입/production build, helper14, HTTP 직접 경로/JSON/no-store/없는 ID 404/cross-site 403 통과. Production build에 개발 전용 page chunk와 개인 snapshot이 포함되지 않음을 확인했다.
- 실제 브라우저에서 임시 주소 직접 열기와 새로고침, 메모 펼침/닫힘, chart.pillars 선택 답과 본문 복귀, 표정 화면과 복귀가 통과했다. 최종 탭은 결과 상단으로 복원한다.
- Node 설정 타입체크에서 Node 선언 누락을 확인해 `@types/node` 개발 의존성을 추가하고 잠금파일을 갱신했다. 최종 Node 타입/웹 타입/빌드 통과. 최초 production 확인의 JSON 전체 금지 검사는 캐릭터 manifest까지 막는 잘못된 probe였으므로 개인 snapshot/개발 module의 제외만 검사하도록 수정해 통과했다.
- fallback-only 사용자 시나리오: 별도 ASGI + 실행 중 웹을 사용한다. 최초 harness의 비loopback TestClient 주소 때문에 preflight BLOCKED; 실제 guard는 유지하고 loopback ASGI client를 사용한 재검증은 456 PASS / 3 WARN / 기존 `known_issue.valid_lunar_day30` 1 FAIL. 두 결과를 보존한다. 로컬 API의 Codex6.1 Sol/xhigh 설정은 유지한다.
