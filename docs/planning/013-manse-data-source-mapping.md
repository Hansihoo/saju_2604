# Manse Data Source Mapping 013

## 목적
- M1 범위인 `만세력 계산 완료`에서 실제로 어떤 데이터를 응답에 포함할지 고정한다.
- `D:\5_project\FortuneFlow`에서 정의한 만세력 항목과 현재 우리 엔진(`lunar-python`)이 직접 제공하는 항목을 매핑한다.
- LLM 해석 이전 단계에서 “계산 결과 자체”를 검증할 수 있는 기준 문서로 사용한다.

## 기준 결론
- M1에서는 `사주 4주 + 지장간 + 십성 + 12운성 + 12신살 + 오행 카운트 + 대운`을 핵심 만세력으로 본다.
- `LLM 해석 문장`은 M2로 분리한다.
- `{지역, 경도}` 데이터셋은 별도 작업으로 진행하고, 지금 만세력 스키마는 그 작업과 독립적으로 유지한다.

## FortuneFlow에서 확인한 만세력 관련 항목

### 1. 기본 정보
- `solar_date`
- `lunar_date`
- `corrected_solar_date`
- `location`
- `gender`
- `time_correction`

출처:
- [models.py](D:/5_project/FortuneFlow/core/models.py)

### 2. 기둥별 기본 정보
- 천간
- 지지
- 천간 십성
- 지지 십성
- 지장간
- 12운성
- 12신살

출처:
- [models.py](D:/5_project/FortuneFlow/core/models.py)
- [additional_fortune_calculator.py](D:/5_project/FortuneFlow/core/additional_fortune_calculator.py)
- [destiny_manager.py](D:/5_project/FortuneFlow/core/destiny_manager.py)

### 3. 대운
- index
- 간지
- 시작/종료 연도
- 시작/종료 나이

출처:
- [models.py](D:/5_project/FortuneFlow/core/models.py)

### 4. 확장 분석
- 오행 분포
- 십성 분석
- 신강/신약
- 용신
- 천간합
- 지지합
- 삼합
- 방합
- 충
- 형
- 파
- 해
- 원진

출처:
- [element_ten_god_calculator.py](D:/5_project/FortuneFlow/core/element_ten_god_calculator.py)

## 현재 엔진에서 직접 얻을 수 있는 항목

### 1. `lunar-python`이 직접 제공하는 항목
- `getYear / getMonth / getDay / getTime`
- `get*Gan / get*Zhi`
- `get*WuXing`
- `get*ShiShenGan`
- `get*ShiShenZhi`
- `get*HideGan`
- `get*DiShi`
- `get*NaYin`
- `get*Xun`
- `get*XunKong`
- `getYun().getDaYun()`
- `getTaiYuan`, `getMingGong`, `getShenGong`, `getTaiXi`

확인 기준:
- 로컬 `lunar_python` 런타임 메서드 확인

### 2. 우리 쪽에서 보조 계산으로 채우는 항목
- 12신살

근거:
- FortuneFlow의 [additional_fortune_calculator.py](D:/5_project/FortuneFlow/core/additional_fortune_calculator.py) 에 있는 `삼합 그룹 -> 12신살 테이블` 규칙을 참고해 우리 서비스용 보조 로직으로 분리

## M1에서 실제 응답에 넣는 만세력 구조

### 1. 기둥별 상세 정보
- `gan_zhi`
- `stem`
- `branch`
- `stem_element`
- `branch_element`
- `stem_ten_god`
- `branch_ten_god`
- `branch_ten_gods`
- `hidden_stems`
- `twelve_fortune`
- `twelve_shinsal`
- `na_yin`
- `xun`
- `xun_kong`

### 2. 표 형식 데이터
- 천간
- 천간 십성
- 지지
- 지지 십성
- 지장간
- 12운성
- 12신살
- 납음
- 공망

### 3. 요약 데이터
- `day_master`
- `element_counts`
- `luck_cycles`
- `supplementary_positions`

## 시간 미상 정책
- 출생시간 미상일 때는 내부 계산은 `00:00`으로 수행한다.
- 하지만 사용자에게 노출되는 만세력에서는 `시주`와 `시주 기반 대운`을 비활성화한다.
- 따라서 `time` 기둥은 `enabled=false`로 내려가고, 표에서는 `시주` 컬럼이 빈값으로 처리된다.

## M1에서 보류하는 항목
- 길성/신살 전체 목록
- 천간합/지지합/삼합/방합
- 충/형/파/해/원진
- 신강/신약의 상세 해석 문장
- 용신 추천 문장
- 사용자용 자연어 설명

이 항목들은 계산 자체보다 해석과 고급 분석에 더 가깝기 때문에 M2 이후 단계에서 확장한다.

## 현재 코드 반영 위치
- 내부 계산 결과 타입: [engine.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/engine.py)
- `lunar-python` adapter: [lunar_python_engine.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/adapters/lunar_python_engine.py)
- 만세력 응답 조립: [build_manse.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/build_manse.py)
- API 스키마: [schemas.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/schemas.py)
- preview 응답 합성: [build_preview_response.py](D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/build_preview_response.py)
- 스키마 문서: [014-manse-schema.md](D:/5_project/SaJu(2)/docs/planning/014-manse-schema.md)

## 다음 작업
1. 사용자용 결과 화면에 `만세력 표`를 노출할지, `요약 + 펼치기`로 갈지 결정한다.
2. `{지역, 경도}` 데이터가 준비되면 시간 보정 모듈에 연결한다.
3. golden test에 `만세력 표 행 단위 비교`를 추가한다.
4. M2에서 LLM은 이 만세력 응답을 입력으로만 사용하고, 판단 로직은 추가하지 않는다.
## 2026-04-09 Analysis Block Update

### Added to current manse output
- `analysis.visible_element_total`
- `analysis.imbalance_gap`
- `analysis.element_percentages`
- `analysis.visible_ten_god_distribution`
- `analysis.balance_score`
- `analysis.internal_grade`
- `analysis.charm_score`
- `analysis.wealth_score`
- `analysis.career_score`
- `analysis.leadership_score`
- `analysis.first_luck_cycle_direction`
- `analysis.first_luck_cycle_exact_start_age_years`
- `analysis.first_luck_cycle_precise_start_age_years`
- `analysis.first_luck_cycle_boundary_datetime`

### Why this matters
- The backend now carries both raw manse values and their deterministic analysis basis together.
- Future interpretation layers no longer need to reconstruct score rationale from scattered fields.
