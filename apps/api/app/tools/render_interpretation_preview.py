"""이 파일은 해석 미리보기을 렌더링하는 로직을 담는다."""

import argparse
import json
import sys
from pathlib import Path

from app.domain.saju.schemas import SajuPreviewRequest
from app.domain.saju.services.build_interpretation_payload import build_interpretation_payload
from app.domain.saju.services.format_interpretation_fallback import format_interpretation_fallback
from app.domain.saju.services.preview_orchestrator import create_saju_preview_response


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _model_dump_json(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return json.loads(model.json())


def parse_args() -> argparse.Namespace:
    """이 도구에 필요한 CLI 인자를 파싱한다."""
    parser = argparse.ArgumentParser(description="Render a fallback interpretation from preview data.")
    parser.add_argument("--calendar-type", choices=["solar", "lunar"], default="solar")
    parser.add_argument("--birth-date", required=True)
    parser.add_argument("--birth-time", default="00:00")
    parser.add_argument("--gender", choices=["male", "female"], required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--locale", choices=["ko", "en"], default="ko")
    parser.add_argument("--estimated-time", action="store_true")
    parser.add_argument("--lunar-leap-month", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    """이 모듈의 CLI 진입점을 실행한다."""
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
        trace_id="dev-interpretation-preview",
        debug_requested=False,
        service_name="suju-insight",
    )
    interpretation_payload = build_interpretation_payload(request=payload, response=response)
    narrative = format_interpretation_fallback(payload=interpretation_payload, locale=args.locale)
    rendered = {
        "payload": _model_dump_json(interpretation_payload),
        "narrative": _model_dump_json(narrative),
    }

    if args.output:
        args.output.write_text(json.dumps(rendered, ensure_ascii=False, indent=2), encoding="utf-8")
        print(args.output)
        return

    print(json.dumps(rendered, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
