# 실행 절차

명령은 프로젝트의 `apps/api`에서 실행한다. 새 파일 경로를 임의의 별도 작업 폴더로 만들지 말고 기존 `.dev-runtime` 아래 현재 대화 소유 evidence root를 쓰며 생성 전에 thread-artifact-cleanup ledger에 등록한다. 개인정보가 포함된 결과는 preserve로 보관한다. 아래 `<...>`는 실제 등록된 절대 경로로 바꾼다.

## 새 runtime 동결

```powershell
python -B -m app.tools.capture_runtime_reading --output <evidence-root>/snapshot.json
python -B -m app.tools.runtime_reading_reviews prepare --snapshot <evidence-root>/snapshot.json --output-dir <evidence-root>/jobs
```

capture는 독립 프로세스에서 fallback-only를 확인한 뒤 실제 `/saju/reading`과 공개 질문의 `/saju/question`을 호출한다. 한국어/영어·일반/시간 미상/날짜 경계 사례와 원본 facts/rules/versions를 보존한다. 캡처 시각과 각 응답 as_of를 동결하므로 재검토 때 재계산하지 않는다. 출력은 fallback 본문이며 실행 중인 다른 서버의 모델 본문이나 브라우저 화면은 아니다. 서버 설정을 바꾸지 않는다. 임의 입력을 추가할 경우 유효한 생년월일시에서 계산하며 명식/사실/사건을 임의로 만들어 넣지 않는다.

사용자가 특정 저장 결과나 현재 브라우저 결과를 지정했으면 먼저 그 결과의 원본 response/input/version을 읽는다. 기본4사례 캡처로 지정 결과의 검토를 대신하지 않는다. 실제 표시된 질문과 선택 응답을 보존하고 runtime metadata를 공급한다. 개인정보는 공개 문서에 복사하지 않는다.

## 독립 검토

`jobs/reader-job.json`과 `jobs/evidence-job.json`은 각각 한 에이전트가 독립 실행한다. 이 CLI는 에이전트/모델을 호출하지 않는다. 오케스트레이터가 새 대화 맥락의 검토 에이전트를 생성하고 해당 역할 job 전체만 편집 없이 공급한다. schema_version/role과 각 버전/hash는 출력 계약에 필요한 metadata이므로 함께 전달한다. 문장 검토자에게 원본 계산·근거 의견·작성자의 자기 평가를 추가하지 않는다.

대상 job에는 기준과 실제 자료만 공급한다. rubric의 calibration_examples는 기준 설계·계약 시험을 위한 참고이며 대상 검토에 전달하지 않는다. 예시의 예상 판정이나 대상과 같은 정답을 공급해 검토를 유도하지 않는다. job 자료를 임의로 빼거나 추가하지 말고 변경이 필요하면 새 버전의 job을 생성한다.

독자 job의 모든 사례를 검토해야 한다. main은 항상 보이는 풀이와 실제 메뉴, followup은 실제 선택 답이다. 근거 job에는 main/followup 연결과 각 원본 사실·프로젝트 규칙·접힌 근거가 들어 있다. 큰 job은 입력을 사례 단위로 나눠 전달하되 같은 job의 모든 사례를 확인한 후 한 결과로 저장한다. 일부만 읽었다면 나머지를 PASS로 채우지 않고 HOLD로 남긴다.

큰 자료는 원본 cases를 main과 연결된 모든 followup의 cohort로 나눠 각 cohort의 독립 job을 생성할 수 있다. 원본 case/계산/규칙을 편집하지 않고 분할과 원본 hash를 provenance에 기록한다. 자료 공급자가 job 파일의 절대 경로와 hash를 지정한 경우 검토자는 처음에 그 파일 하나만 읽어 전체 job을 공급받을 수 있다. 잘린 출력이면 같은 파일의 나머지 부분도 읽는다. 이 입력 로딩 외의 파일 탐색·브라우저·도구 사용은 금지한다. 접근을 기술적으로 차단한 것은 아니므로 input_blind_only를 유지한다. 후속 판정 자료를 작성자가 골라 추가하지 않는다.

`--inputs <절대 경로>`로 runtime-birth-inputs-v1의 cases[{id,input}]를 공급할 수 있다. input은 출생 요청 필드만 허용하며 계산 사실·사건·규칙 주입은 거부한다. 기본4사례는 유지한다. 새로운 캡처 버전은 runtime-capture-2026-10-10.3이다. 질문 v3의 기본 reading 설명과 접힌 memo 자료를 역할별로 투영하고 다음 메뉴는 실제 서버 응답 followups를 그대로 사용한다. 질문 ID만 제외해 메뉴를 재생성하지 않는다. 근거 job은 비공개 이전 characteristics/용어 설명 템플릿을 제외하지만 원본 snapshot과 모든 계산 facts 및 실제 적용 natal/theme 규칙은 보존하며 projection_scope에 기록한다.

독립 검토 JSON을 `<evidence-root>/reviews/reader-review.json`, `evidence-review.json`에 저장한다. reviews 폴더도 등록 root 아래 생성한다. 검토자는 수정/다른 역할을 호출하지 않고 결과만 반환하며 소유 오케스트레이터가 저장한다.

```json
{
  "schema_version": "runtime-reading-review-v1",
  "role": "reader",
  "job_hash": "job에서 받은 실제 hash",
  "review_kind": "codex_agent",
  "cases": [{
    "case_index": 0,
    "understood_answer": "실제로 이해한 결론",
    "question_fulfillment": "met",
    "next_question_id": null,
    "expected_new_information": "",
    "checks": [{
      "id": "clarity", "status": "PASS",
      "evidence": [{"source": "answer", "quote": "공급된 원문에서 실제 인용"}],
      "reason": "대상과 결론이 명확함", "repair_target": "none"
    }]
  }]
}
```

위는 **필드 설명용**이며 완성된 검토/fixture가 아니다. job의 적용 criteria 전부와 모든 사례를 포함한다. evidence 역할은 reader 전용4필드를 쓰지 않는다. 실제 인용 source는 각 사례의 `evidence_sources` 키 중 고른다. PASS에는 실제 인용이 필수이며, 요소 부재를 FAIL로 판정할 때는 빈 evidence와 구체적인 누락 이유를 남길 수 있다. 질문 메뉴를 검토하는 사례의 followup_interest PASS에는 실제 메뉴에서 고른 ID와 기대하는 새 정보가 필요하다. main에 질문이 없으면 흥미 검증은 HOLD로 두며 없는 질문을 강제로 만들지 않는다. 선택 답에 남은 메뉴가 있으면 그 메뉴에도 같은 검사를 적용한다.

```powershell
python -B -m app.tools.runtime_reading_reviews evaluate --jobs-dir <evidence-root>/jobs --reviews-dir <evidence-root>/reviews --output <evidence-root>/report.json
```

실패는 종료코드1, 계약/저장 오류는2다. HOLD는 실행 완료일 뿐 승인이 아니다. 오래된 manifest/job/rubric/hash, 중복/누락 사례, 허구/접힌 자료의 독자 인용을 거부한다. fixture는 구조 시험에만 쓰고 내용 검토를 했다고 주장하지 않는다.

보고서의 observation_scope는 frozen_content이며 source_provenance는 snapshot이 공급한 캡처 기록이다. 합성 fixture를 실제 API 실행으로 인증하지 않는다. 실제 실행 여부는 캡처 명령의 완료/HTTP 증거와 함께 확인한다.

## 화면과 결과 보고

브라우저 사용 스킬을 적용해 실제 UI의 기본 본문·접힌 근거·질문 목록·선택 답·복귀를 확인한다. 서버가 실행 중이면 재사용한다. 테스트 provider를 바꾸기 위해 사용자가 실행 중인 서버를 재시작하지 않는다. 브라우저에 다른 본문이 보이면 API snapshot 검토와 분리해서 기록한다.

관련 단위 테스트와 fallback-only 사용자 시나리오도 실행한다. 알려진 음력30일 실패를 유지한다. 스킬/새 검증기 동작 검증과 서비스 콘텐츠의 통과는 별개다. 현재 종합 판단·기간 규칙의 공백이 드러나면 원인과 미충족 궁금증을 그대로 보고한다.
