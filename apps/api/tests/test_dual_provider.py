"""Exercise both real adapter functions with captured SDK/CLI boundaries."""

import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tests.test_generate_interpretation import make_payload, make_report
from app.domain.saju.category_reading import _writing_context
from app.domain.saju.services import generate_interpretation as generation
from app.domain.saju.services.codex_provider import CodexProviderResult


class DualProviderContractTests(unittest.TestCase):
    def render(self, provider, output):
        create = Mock(return_value=SimpleNamespace(id="replayed-sdk", output_text=output))
        client = Mock(return_value=SimpleNamespace(responses=SimpleNamespace(create=create)))
        codex = Mock(return_value=CodexProviderResult(output_text=output, response_id="replayed-cli", duration_ms=1))
        with patch.multiple(generation.settings, llm_provider=provider, openai_api_key="local-test-only",
                            openai_model="gpt-5.4", codex_model="gpt-6.1-sol", llm_max_attempts=1,
                            llm_allow_repair=False), patch.object(generation, "OpenAI", client), patch.object(generation, "call_codex_json", codex):
            result = generation.generate_interpretation_report(payload=make_payload(), trace_id="dual-replay", service_name="test")
        return result, client, create, codex

    def test_same_json_reaches_same_validated_report_through_both_adapters(self):
        source = generation._model_dump_json(make_report())
        output = json.dumps({k:source[k] for k in ("summary","core_analysis","love","career","wealth","luck_flow")}, ensure_ascii=False)
        api, client, create, unused_cli = self.render("openai", output)
        cli, unused_api, unused_create, call_codex = self.render("codex", output)
        self.assertEqual(api.provider, "openai")
        self.assertEqual(cli.provider, "codex")
        unused_cli.assert_not_called()
        unused_api.assert_not_called()
        self.assertEqual(create.call_count, 1)
        self.assertEqual(call_codex.call_count, 1)
        for key in ("summary","core_analysis","love","career","wealth","luck_flow"):
            self.assertEqual(getattr(api,key), getattr(cli,key))
        from app.domain.saju.services.structured_output_schema import strict_output_schema
        self.assertEqual(create.call_args.kwargs["text"]["format"]["schema"], strict_output_schema(call_codex.call_args.kwargs["output_schema"]))
        self.assertEqual(json.loads(create.call_args.kwargs["input"][1]["content"]), call_codex.call_args.kwargs["user_payload"])
        self.assertEqual(create.call_args.kwargs["input"][0]["content"], call_codex.call_args.kwargs["developer_prompt"])
        self.assertEqual(_writing_context(api)["writing_status"], "model_generated")
        self.assertEqual(_writing_context(cli)["writing_model"], "gpt-6.1-sol")

    def test_bad_evidence_and_invalid_json_use_visible_fallback_without_cross_provider_call(self):
        source = generation._model_dump_json(make_report())
        source["wealth"]["evidence_ids"] = ["invented.fact"]
        output = json.dumps(source, ensure_ascii=False)
        for provider in ("openai", "codex"):
            for text in (output, "not-json"):
                with self.subTest(provider=provider, output=text[:8]):
                    report, client, create, cli = self.render(provider, text)
                    self.assertEqual(report.provider, "fallback")
                    meta = _writing_context(report)
                    self.assertEqual(meta["requested_writing_provider"], provider)
                    self.assertEqual(meta["writing_status"], "fallback")
                    self.assertTrue(meta["writing_fallback_reason"])
                    (cli if provider=="openai" else client).assert_not_called()

    def test_critical_hold_metadata_does_not_claim_model_generation(self):
        self.assertEqual(_writing_context(None)["writing_status"], "not_called")
        self.assertIsNone(_writing_context(None)["writing_model"])
