import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from app.api.routes import read_verification_provider, _guard_verification_provider, create_saju_preview, create_saju_free_detail
from app.domain.saju.schemas import SajuPreviewRequest


class VerificationGuardTests(unittest.TestCase):
    def test_provider_discovery_is_local_and_nonproduction_only(self):
        with patch("app.api.routes.settings.runtime_environment", "development"), patch("app.api.routes.settings.llm_provider", "fallback"):
            result = read_verification_provider(SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")))
            self.assertEqual(result, {"configured_provider": "fallback", "fallback_only": True})
            with self.assertRaises(HTTPException) as rejected:
                read_verification_provider(SimpleNamespace(client=SimpleNamespace(host="192.0.2.10")))
            self.assertEqual(rejected.exception.status_code, 404)
        with patch("app.api.routes.settings.runtime_environment", "production"):
            with self.assertRaises(HTTPException):
                read_verification_provider(SimpleNamespace(client=SimpleNamespace(host="127.0.0.1")))

    def test_changed_provider_rejects_before_calculation_or_llm_call(self):
        payload = SajuPreviewRequest(birth_date="1997-09-18", birth_time="14:30", region_id="kr-seoul")
        request = SimpleNamespace(headers={"x-saju-verification-provider": "fallback"})
        for handler in (create_saju_preview, create_saju_free_detail):
            with patch("app.api.routes.settings.llm_provider", "openai"), patch("app.api.routes.create_saju_preview_response") as calculate:
                with self.assertRaises(HTTPException) as rejected:
                    handler(payload=payload, request=request)
                self.assertEqual(rejected.exception.status_code, 409)
                calculate.assert_not_called()

    def test_normal_requests_are_unaffected_and_fallback_guard_passes(self):
        with patch("app.api.routes.settings.llm_provider", "openai"):
            _guard_verification_provider(SimpleNamespace(headers={}))
        with patch("app.api.routes.settings.llm_provider", "fallback"):
            _guard_verification_provider(SimpleNamespace(headers={"x-saju-verification-provider": "fallback"}))
            with self.assertRaises(HTTPException):
                _guard_verification_provider(SimpleNamespace(headers={"x-saju-verification-provider": "openai"}))
