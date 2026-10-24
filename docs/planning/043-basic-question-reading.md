# 기본 사주 → 질문 → 선택한 답

2026-10-08 구현. 첫 진입의 `운세 보기`와 두 단계 출생 입력을 유지하며, 최초 결과는 계산된 사주팔자다. 결과에서 지원 질문을 고르면 해당 답만 요청한다. 기존 전체 preview/detail API와 계산 정책은 유지한다.

후속 피드백으로 질문 앞에 항상 보이는 개인별 기본 본문을 추가했다. 현재 계약과 본문 검증은 [044](044-useful-basic-reading.md)를 함께 따른다. 기본 명식과 질문 메뉴만으로 화면을 축소하지 않는다.

## 실제 지원 범위

| 질문 ID | 공개 질문 | 제공 정보 |
| --- | --- | --- |
| luck.current_next | 지금 대운은 언제 바뀌어? | 정밀 시작·교체 시각으로 선택한 현재/다음 대운, 글자 및 천간 십성 관계 |
| stars.dohwa | 내 사주에 도화가 있어? | 함지 연지/일지 기준의 위치 합집합, 별도 왕지·목욕 방법과 위치 |
| wealth.locations | 재성은 내 사주 어디에 있어? | 겉 천간과 표시된 지장간의 재성 글자 자리, 일간과의 개별 대조 |
| period.this_year | 올해 내 사주에 들어오는 글자는? | 출생지 시간대의 입춘 구간과 세운 천간/일간 십성 관계 |

이 질문들은 계산 사실과 용어 설명이다. 만남·취업·승진의 유리한 기간, 사건 확률, 인구 순위, 운세 지수는 지원하지 않는다. 이전 질문의 이름을 바꿔 미래 시기에 답한 것으로 취급하지 않는다. 핵심 미래 시기 요구는 여전히 규칙 검토가 필요하다.

시간 미상에서는 시주·대운을 제외하고 지원 질문 목록에서도 대운을 빼며, 도화/재성은 세 기둥만 대상으로 한다. `critical` 계산 불확실성은 선택된 정책의 계산 사실 설명에 표시하고 신규 해석 판정으로 확대하지 않는다. 필요하지 않은 연애 상황은 받지 않는다. 신규 상황 질문은 질문별 규칙/상황 계약을 갖춘 뒤 추가한다.

## 계약과 모듈

- `POST /saju/basic`: 기존 `SajuPreviewRequest` 입력. `report_mode=none`으로 계산하고 기존 응답에 `question_flow`를 추가한다. 첫 화면에 모델을 호출하지 않는다.
- `POST /saju/question`: `{input, question_id, context:null}`. 서버가 원본 입력을 계산/재사용하며, 선택한 질문의 answer/sections/memo/notices/facts/source_context/versions만 반환한다. 클라이언트 사실 입력과 미등록 질문은 거부한다.
- `question_schemas.py`: 별도 `basic-question-reading-v1`. 기존 `question-reading-v1` 해석 4역할 계약을 수정하거나 우회하지 않는다.
- `question_reading.py`: 지원 질문, 계산 사실 추출, 용어 설명, 범위 제한과 문구. 모델·전체 preview 텍스트·기존 성향 카드를 복사하지 않는다.
- `question_routes.py`: HTTP 경계와 비공개/no-store 응답. 기존 router에는 import/include만 추가한다.
- `DokkaebiQuestions.tsx`: 서버 명식/질문/답을 표시한다. 본문은 모두 노출하고 작은 `풀이 메모`는 기본 닫힘. 공유는 선택한 답과 공급된 한계를 그대로 사용한다.

사실/지식/규칙/문구/형식 버전과 진입 UI 버전은 별도다. 생년월일로 브라우저가 운세를 판단하지 않으며 입력을 URL이나 새 영구 저장소에 저장하지 않는다. 서버 메모리 캐시는 120초/48항목, deep copy, 전체 검증 입력·지역/UTC 날짜·기능 플래그·버전으로 분리한다. 질문 캐시는 실제 사실/질문/상황/locale/지역 날짜/버전을 포함한다. 같은 날짜 내 절입과 대운 교체도 검토한다. hash는 권한이 아니다.

## 질문자·답변자·감독관 검증

`verify_question_flow.py`가 모델 없는 ASGI 요청으로 실제 결과를 동결한다. 이는 API socket/브라우저 검증과 별도다. `question_flow_reviews.py`는 저장 파일만 다루며 HTTP, 설정, 엔진, 공급자를 import하지 않는다. 각 job은 다른 역할이 실행 중일 필요 없이 하나씩 처리할 수 있다.

| 역할 | 받는 입력 | 검토 |
| --- | --- | --- |
| 질문자 | 질문·직접 답·본문·표시된 한계 | 선택 질문에 답했는지, 용어와 정보의 유익성. 핵심 미래 시기 충족은 별도 필드 |
| 답변자 | 동결 질문·답·사실·정책 | 직접 답과 개인별 설명을 보강할 문구. 없는 사건/날짜 추가 금지 |
| 감독관 | 동결 질문·답·원본 사실의 필요한 경로·정책·코드 검사 | fact_fidelity/question_fit/scope/voice/note_consistency. 다른 리뷰를 보지 않음 |

실행 예시(기존 임시 영역의 새 절대 경로를 지정하고 thread artifact ledger에 먼저 등록):

```powershell
pnpm verify:question-flow -Output <new-absolute-snapshot.json>
cd apps/api
python -B -m app.tools.question_flow_reviews prepare --snapshot <snapshot.json> --output-dir <new-absolute-jobs-directory>
# 각 역할 job JSON을 별도 Codex 에이전트에 전달. 결과는 review_schema에 따라 저장.
python -B -m app.tools.question_flow_reviews evaluate --jobs-dir <jobs-directory> --reviews-dir <reviews-directory> --output <new-absolute-report.json>
```

저장 파일을 만들 때는 덮어쓰지 않는다. snapshot/job hash와 prompt/rubric 버전이 다른 리뷰는 거부한다. 코드 FAIL은 긍정 리뷰로 상쇄하지 않으며, 누락과 fixture 리뷰는 HOLD다. 역할 입력만 분리하는 `input_blind_only`이고 도구 접근이나 공유 대화 이력을 완전히 격리한 맹검이 아니다. 답변자 자기 보강과 독립 감독을 구별한다. 에이전트 리뷰의 PASS는 실사용자 흥미나 예측 정확도의 인증이 아니다.

## 2026-10-08 실행 검증

- 최종 facts `.2`, knowledge `.1`, rules `.2`, copy `.4`, format `basic-question-reading-v1`. 원래 계산 정책과 기존 provider/model 설정을 유지했다.
- 정상 KO/EN, 제천 1988-11-20 23:30 남성 경계, 출생시간 미상으로 API 답 15개와 검사 116개를 실행해 모두 통과했다. in-process ASGI/fallback, 모델 호출 0회이며 외부 정확성 인증은 아니다.
- 전체 API426 테스트 후 최종 변경의 질문22 테스트 및 독립 review 모듈15 테스트가 통과했다. 웹 타입/빌드, reading helper14/progress7도 통과했다.
- 실제 IAB KO390/KO320/EN320에서 기본 명식→선택 답, 질문 변경/메모 닫힘 초기화와 펼침, 뒤로/원본 입력 보존, 시간 미상에서 대운 제외, 서버 버전 변경 시 입력 복귀, KO/EN 1080×1350 공유 이미지 생성과 모든 supplied notices 유지를 확인했다. 가로 넘침과 새 경고/오류가 없었다. 공유 카드 중요 제한은 자르지 않고, 영역에 들어가지 않으면 내보내기를 실패 처리한다. 새 PNG 다운로드·메신저 전송·모바일 실기기/스크린리더 검증은 수행하지 않았다.
- 검토 r4에서 감독관 FAIL은 정상 대운 결과의 계산 기준 차이 notice 누락을 발견했다. 선택 답과 공유에 해당 안내를 보존하도록 수정했다. 답변자 문구 검토로 동적 조사·영문 단복수를, 질문자 지적으로 시간 미상 범위와 도화 방법 설명을 보강했다.
- 최종 r6은 질문자 HOLD/핵심 미래 요구 미충족, 답변자 사실 질문 문구 PASS, 감독관 사실·질문 적합·범위·말투·노트 대응 PASS로 종합 HOLD다. 동결 snapshot hash는 `27cb487e99084171d754c4344c7ac3eb982982f6ce17fc4f197fd1d01157cb82`. 등록 임시 영역 `question-flow-20261008`의 snapshot-r6/jobs-r6/reviews-r6/review-report-r6 원본을 보존한다. 코드 PASS가 콘텐츠 HOLD를 상쇄하지 않도록 유지한다.
- fallback-only 기존 사용자 시나리오는456 PASS/3 WARN/기존 유효 음력30일 입력 FAIL이다. 이 기존 schema 문제는 이번 흐름에서 수정하지 않았다.

## 남은 검증/보강 범위

새 인연·구직·직장 평가/보상 질문은 기간별 사실과 검토된 적용 규칙을 갖춰야 한다. 현재 계산 사실 질문만으로 그 요구를 충족했다고 보고하지 않는다. 일반 fallback 사용자 시나리오의 기존 음력 30일 입력 FAIL도 별도로 남긴다. 외부 전문가 검토, 실제 사용자 흥미, 모바일 실기기/스크린리더 검증은 미완료다.
