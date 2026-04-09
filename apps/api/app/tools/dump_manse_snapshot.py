import argparse
import json
import sys
from pathlib import Path

from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dump the canonical manse snapshot for a single input.")
    parser.add_argument("--calendar-type", choices=["solar", "lunar"], default="solar")
    parser.add_argument("--birth-date", required=True)
    parser.add_argument("--birth-time", default="00:00")
    parser.add_argument("--gender", choices=["male", "female"], required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--estimated-time", action="store_true")
    parser.add_argument("--lunar-leap-month", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = SajuPreviewRequest(
        calendar_type=args.calendar_type,
        birth_date=args.birth_date,
        birth_time=args.birth_time,
        is_birth_time_estimated=args.estimated_time,
        is_lunar_leap_month=args.lunar_leap_month,
        gender=args.gender,
        region_id=args.region_id,
        debug=False,
    )
    response = create_saju_preview_response(
        payload=payload,
        trace_id="dev-manse-snapshot",
        debug_requested=False,
        service_name="suju-insight",
    )
    rendered = {
        "trace_id": response.trace_id,
        "region": response.region.model_dump(mode="json"),
        "time_correction": response.time_correction.model_dump(mode="json"),
        "regional_solar_correction": response.regional_solar_correction.model_dump(mode="json"),
        "calendar_normalization": response.calendar_normalization.model_dump(mode="json"),
        "manse": response.manse.model_dump(mode="json"),
    }

    if args.output:
        args.output.write_text(json.dumps(rendered, ensure_ascii=False, indent=2), encoding="utf-8")
        print(args.output)
        return

    print(json.dumps(rendered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
