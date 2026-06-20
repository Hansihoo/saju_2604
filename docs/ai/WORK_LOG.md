# AI Work Log

| 업무 명 | 설명 | 진행상황 | 특이사항 |
| --- | --- | --- | --- |
| 로컬 Codex LLM 옵션 추가 | OpenAI API 외에 로컬 `codex exec`를 사용하는 LLM provider 경로를 추가 | Done | 실제 Codex 호출로 메인 해석과 무료 미리보기 통과 확인. 무료 미리보기는 검증 실패 시 Codex repair 1회 후 fallback 유지. |
| 결과 디자인 랩 추가 | 현재 저장된 사주 결과값을 API 호출 없이 문서형 결과지 시안으로 비교하는 `/design-lab` 화면을 추가 | Done | 프리미엄 리포트, 에세이형 해석문, 인쇄용 요약지 3개 시안으로 전환. `pnpm build:web` 통과 및 브라우저 데스크톱/390px 모바일 확인 완료. |
| 에세이형 결과 화면 적용 | `/design-lab`의 에세이형 문서 스타일을 실제 사주 결과 화면에 적용 | Done | `SajuResultView`에 `essay-result` 모드를 추가하고 히어로, 목차, 핵심 카드, 상세 본문, 데이터 표를 문서형 톤으로 재정리. `pnpm build:web` 통과. |
| 프로젝트 문서 보완 | 프로젝트 정체성, 최근 변경점, OpenAI API 없이 테스트하는 방법을 문서에 정리 | Done | README, PROJECT_PROFILE, PROJECT_STATUS, WORK_LOG 갱신 및 `docs/START_HERE.md` 추가. 상용 기본값은 OpenAI, 로컬 테스트는 fallback/Codex 가능하다고 명시. |
