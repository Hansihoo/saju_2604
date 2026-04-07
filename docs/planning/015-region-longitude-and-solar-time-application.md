# Region Longitude And Solar Time Application 015

## Purpose
- Record how the Korean `{region, longitude, regional_time_offset_minutes}` dataset is applied in the backend.
- Keep the civil timezone correction and the longitude-based solar-time correction as separate, debuggable stages.
- Make the current rule explicit so we can verify or replace the dataset later without changing the API contract again.

## Source Data
- Local dataset: [korea_city_longitudes_for_saju.csv](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/data/korea_city_longitudes_for_saju.csv)
- Original user-provided source path:
  - `C:/Users/Theo/Desktop/MouseWithoutBorders/korea_city_longitudes_for_saju.csv`
- Current columns:
  - `시도`
  - `시`
  - `경도`
  - `지역시차_분`
  - `산출방식`

## What We Applied
The region catalog now uses the CSV as its source of truth.

Each region record includes:
- `id`
- `display_name`
- `country`
- `province`
- `city`
- `tzid`
- `longitude`
- `regional_time_offset_minutes`
- `correction_basis`
- `aliases`

Code:
- Region dataset loader: [mock_data.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/mock_data.py)
- Region lookup/search: [region_catalog.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/region_catalog.py)

## Correction Stages
We now treat time correction as two separate stages.

1. Civil timezone correction
- Validates the user-entered local time against `tzid`
- Handles DST, historical timezone offsets, and ambiguous/non-existent local times
- Code: [time_correction.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/time_correction.py)

2. Regional solar correction
- Applies the CSV `지역시차_분` value to the normalized solar datetime
- Uses `longitude` and `correction_basis` as traceable metadata
- Produces `corrected_solar_datetime`
- Code: [time_correction.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/time_correction.py)

## Current Rule
- Input to the saju engine is no longer the raw normalized solar datetime.
- Input to the saju engine is `corrected_solar_datetime`.

Pipeline:
1. Resolve region
2. Validate civil local time with `tzid`
3. Normalize solar/lunar calendar input into solar datetime
4. Apply regional solar correction
5. Calculate saju/manse with the corrected solar datetime

Code path:
- Orchestrator: [preview_orchestrator.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/services/preview_orchestrator.py)
- Engine adapter: [lunar_python_engine.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/adapters/lunar_python_engine.py)

## Rounding Rule
- The dataset stores `지역시차_분` with decimal minutes.
- The engine currently accepts second precision.
- We therefore convert minutes to seconds and round to the nearest whole second before applying the correction.

Example:
- `10:30:00`
- `지역시차_분 = -32.033`
- Applied seconds = `round(-32.033 * 60) = -1922`
- Corrected solar datetime = `09:57:58`

## API Impact
The preview response now exposes:
- Region longitude metadata on `region`
- A separate `regional_solar_correction` block
- A new pipeline stage: `regional_solar_correction`

Schema:
- [schemas.py](/D:/5_project/SaJu(2)/apps/api/app/domain/saju/schemas.py)
- [contracts.ts](/D:/5_project/SaJu(2)/apps/web/src/shared/api/contracts.ts)

## Current Limitations
- The dataset is still a fixed local CSV, not an official live source.
- The current dataset is Korea-only and assumes `Asia/Seoul`.
- We have not yet built an external oracle to certify each regional correction value.
- The next verification step should compare representative outputs against KASI calendar references and a second engine.

## Verification
- Region catalog tests:
  - [test_region_catalog.py](/D:/5_project/SaJu(2)/apps/api/tests/test_region_catalog.py)
- Time correction tests:
  - [test_time_correction.py](/D:/5_project/SaJu(2)/apps/api/tests/test_time_correction.py)
- Pipeline tests:
  - [test_saju_preview_pipeline.py](/D:/5_project/SaJu(2)/apps/api/tests/test_saju_preview_pipeline.py)
