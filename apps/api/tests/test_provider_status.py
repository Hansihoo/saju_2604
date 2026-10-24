import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.config import PLACEHOLDER_OPENAI_API_KEY
from app.tools import provider_status as status
from app.domain.saju.services.structured_output_schema import strict_output_schema


def configuration(**overrides):
    values = dict(llm_provider="codex", openai_model="gpt-5.4", llm_reasoning_effort="low",
                  openai_api_key=PLACEHOLDER_OPENAI_API_KEY, codex_model="gpt-6.1-sol",
                  codex_reasoning_effort="xhigh", codex_node_command=None, codex_js_path=None,
                  codex_command="codex", is_production=False)
    values.update(overrides)
    return SimpleNamespace(**values)


class ProviderReadinessTests(unittest.TestCase):
    def test_openai_missing_key_does_not_probe_codex_or_send_inference(self):
        with patch.object(status, "_openai_sdk_available", return_value=True), patch.object(status.subprocess, "run") as run:
            result = status.inspect_provider("openai", configuration=configuration())
        self.assertFalse(result["ready"])
        self.assertEqual(result["checks"][0]["reason"], "missing_api_key")
        self.assertEqual(result["model"], "gpt-5.4")
        run.assert_not_called()

    def test_api_readiness_is_not_live_generation_and_never_contains_key(self):
        with patch.object(status, "_openai_sdk_available", return_value=True):
            result = status.inspect_provider("openai", configuration=configuration(openai_api_key="private-test-marker"))
        self.assertTrue(result["ready"])
        self.assertFalse(result["live_generation_verified"])
        self.assertEqual(result["inference_calls"], 0)
        self.assertNotIn("private-test-marker", json.dumps(result))

    def test_codex_login_status_is_sanitized_and_does_not_require_api_key(self):
        with patch.object(status.shutil, "which", return_value="codex"), patch.object(status.subprocess, "run",
            return_value=SimpleNamespace(returncode=0, stdout="private account", stderr="private token")) as run:
            result = status.inspect_provider("codex", check_auth=True, configuration=configuration())
        self.assertTrue(result["ready"])
        self.assertTrue(result["auth_checked"])
        self.assertEqual(run.call_args.args[0][-2:], ["login", "status"])
        self.assertNotIn("private", json.dumps(result))

    def test_cli_login_failure_timeout_and_production_are_not_ready(self):
        for failure in (SimpleNamespace(returncode=1), status.subprocess.TimeoutExpired("codex", 15)):
            with self.subTest(failure=type(failure).__name__), patch.object(status.shutil, "which", return_value="codex"), patch.object(
                status.subprocess, "run", **({"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure})
            ):
                self.assertFalse(status.inspect_provider("codex", check_auth=True, configuration=configuration())["ready"])
        with patch.object(status.subprocess, "run") as run:
            self.assertFalse(status.inspect_provider("codex", check_auth=True, configuration=configuration(is_production=True))["ready"])
        run.assert_not_called()

    def test_schema_preserves_enums_refs_and_property_names_and_does_not_mutate_input(self):
        schema = {"type":"object", "properties":{"default":{"type":"string","enum":["fact.a"]},"nested":{"$ref":"#/$defs/Child"}},
                  "$defs":{"Child":{"type":"object","properties":{"default":{"type":"string","maxLength":5}},"required":[]}},"required":["default"]}
        original = json.dumps(schema)
        strict = strict_output_schema(schema)
        self.assertEqual(json.dumps(schema), original)
        self.assertEqual(strict["required"], ["default", "nested"])
        self.assertEqual(strict["properties"]["default"]["enum"], ["fact.a"])
        self.assertEqual(strict["$defs"]["Child"]["required"], ["default"])
        self.assertFalse(strict["$defs"]["Child"]["additionalProperties"])
        self.assertNotIn("maxLength", strict["$defs"]["Child"]["properties"]["default"])
