# M1 Manse Progress Log

## 목적
- `M1. 만세력 계산과 검증 완료` 마일스톤의 실제 진행 기록을 남긴다.
- 어떤 순서로 작업했고, 어디까지 맞췄고, 무엇이 남았는지 다음 작업에서 바로 이어갈 수 있게 한다.
- golden validation 결과와 수정 방향을 함께 적어 회귀 검증 기준으로 사용한다.

## 2026-04-07

### 이번에 확인한 상태
- 사주 4주(`year/month/day/time`)는 golden 정답 5케이스와 모두 일치한다.
- 12신살은 golden 정답 기준과 일치한다.
- 최신 golden validation 기준 총 mismatch는 `42`개다.
- 남은 mismatch는 거의 전부 `luck_cycles`에 집중되어 있다.
- 자동 진단 집계:
  - `regional_display_rounding_mismatch`: `1`
  - `luck_cycle_progression_rule_mismatch`: `3`

### 이번에 한 일
1. golden validation을 다시 실행해 현재 오차를 최신 기준으로 고정했다.
2. `aru`, `gomaebi`, `pororo`, `lee-hyeonjin`, `okji` 케이스의 대운 차이를 다시 비교했다.
3. `lunar-python` 내부 `Yun`, `DaYun` 소스를 직접 확인해 기본 대운 계산 규칙을 추적했다.
4. 정답지 원본 txt의 `대운 분석` 표를 다시 확인해 파서 오인식이 아니라 원문 자체가 현재 canonical JSON과 동일하게 들어가고 있음을 확인했다.
5. golden summary에 자동 진단 태그와 추천 조치를 추가해 다음 수정 포인트를 더 빨리 좁힐 수 있게 했다.
6. `lunar-python`에서 대운 1칸을 더 가져오고, API 만세력에는 빈 `index=0` 대운을 제외하도록 조정했다.
7. 그 결과 `lee-hyeonjin`, `okji`는 golden과 완전 일치하게 되었고, `pororo`는 “누락”이 아니라 실제 마지막 대운 규칙 차이로 드러났다.

### 핵심 관찰
- `lunar-python`의 `DaYun.getGanZhi()`는 `월주`를 기준으로 순행이면 `+index`, 역행이면 `-index`로 진행한다.
- `Yun.getDaYun()` 기본값은 `n=10`이고, 이 안에는 빈 `index=0`이 포함된다.
- 그래서 현재 엔진 기본값만 쓰면 실제 대운 행은 9칸만 남는다.
- `n=11`로 늘리면 `lee-hyeonjin`, `okji`는 정답과 맞는다.
- 하지만 `aru`, `gomaebi`, `pororo`는 마지막 칸까지 포함해도 golden 정답과 자동으로 맞지 않는다.
- 외부 규칙 출처를 다시 확인해도 대운은 기본적으로 `월주를 기준으로 순행/역행`하는 설명이 일관되게 나온다.
- 따라서 현재 `aru`, `gomaebi` 대운 표는 표준 `lunar-python` 규칙과도, 일반 설명 자료와도 다르게 보인다.

### 케이스별 현재 판단
- `lee-hyeonjin`, `okji`
  - 대운 10칸 출력 문제를 해결한 뒤 golden과 완전 일치했다.
- `pororo`
  - 기존에는 마지막 대운 1칸 누락처럼 보였지만, 실제로는 마지막 간지가 표준 규칙과 다르다.
- `aru`, `gomaebi`
  - 시작 나이는 현재 꽤 맞춰졌지만, 대운 간지/지지 흐름 자체가 `lunar-python` 기본 규칙과 다르다.
  - 이 둘은 단순 버그보다 “다른 대운 규칙” 또는 “다른 만세력 기준”을 쓰는 가능성이 크다.

### 현재 결론
- 지금 단계에서 대운 mismatch는 구현 실수와 규칙 차이가 섞여 있지 않고, 대부분 “규칙 차이”로 보인다.
- 따라서 다음 작업은 대운 규칙 출처를 더 확보하고, 어떤 규칙을 프로젝트 기준으로 채택할지 문서화한 뒤 코드에 반영하는 순서가 맞다.
- 특히 `aru`, `gomaebi`는 정답지 자체가 다른 대운 규칙을 쓰는지 먼저 판단해야 한다.
- `pororo`는 표준 역행 규칙상 마지막 대운이 `신묘`로 계산되는데 정답지는 `신축`으로 적혀 있어, 단일 정답지 이상 가능성도 열어두고 확인해야 한다.

### 다음 작업
1. `aru`, `gomaebi` 대운 간지 흐름이 어떤 규칙에서 나오는지 추가 조사
2. `pororo` 마지막 대운 `신축`이 규칙 차이인지 정답지 이상인지 추가 확인
3. 지역 보정 표시 규칙(`corrected_datetime`, `regional_time_offset_minutes`)을 별도 정책으로 정리

### 참고 실행 명령
```powershell
cd D:\5_project\SaJu(2)\apps\api
python -m app.tools.run_golden_validation
```

### 참고 문서
- [012-development-backlog-through-manse.md](/D:/5_project/SaJu(2)/docs/planning/012-development-backlog-through-manse.md)
- [016-golden-answer-validation-system.md](/D:/5_project/SaJu(2)/docs/planning/016-golden-answer-validation-system.md)
- [명리심리상담사 강의교안 PDF](https://www.ili.or.kr/upfiledata/Board/%EB%AA%85%EB%A6%AC%EC%8B%AC%EB%A6%AC%EC%83%81%EB%8B%B4%EC%82%AC_%EC%A0%84%EC%A0%95%ED%9B%88_%EA%B5%90%EC%95%88%EB%AA%A8%EC%9D%8C%5B1%5D.pdf)
  - 대운은 월주를 기준으로 순행/역행한다고 설명
- [대운 해석법](https://sajulatte.app/blog/daeun-interpretation)
  - 월주에서 순행이면 다음 간지, 역행이면 이전 간지로 진행하는 예시 제공
