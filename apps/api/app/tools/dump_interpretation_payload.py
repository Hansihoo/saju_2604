"""이 파일은 해석 payload을 출력하는 로직을 담는다."""

import argparse
import json
import sys
from types import SimpleNamespace

from app.api.routes import create_saju_preview
from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload


def _model_dump_json(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def main() -> None:
    """이 모듈의 CLI 진입점을 실행한다."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Dump the internal M2 interpretation payload.")
    parser.add_argument("--calendar-type", choices=["solar", "lunar"], default="solar")
    parser.add_argument("--birth-date", required=True)
    parser.add_argument("--birth-time", default="00:00")
    parser.add_argument("--estimated-time", action="store_true")
    parser.add_argument("--lunar-leap-month", action="store_true")
    parser.add_argument("--gender", choices=["male", "female"], required=True)
    parser.add_argument("--region-id", required=True)
    args = parser.parse_args()

    request_payload = SajuPreviewRequest(
        calendar_type=args.calendar_type,
        birth_date=args.birth_date,
        birth_time=args.birth_time,
        is_birth_time_estimated=args.estimated_time,
        is_lunar_leap_month=args.lunar_leap_month,
        gender=args.gender,
        region_id=args.region_id,
        debug=False,
    )

    request = SimpleNamespace(
        state=SimpleNamespace(
            trace_id="dump-interpretation-payload",
            debug_requested=False,
        )
    )
    response = create_saju_preview(payload=request_payload, request=request)
    interpretation_payload = build_interpretation_payload(
        request=request_payload,
        response=response,
    )
    print(json.dumps(_model_dump_json(interpretation_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
