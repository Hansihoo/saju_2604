"""Check that project-local model settings reach the real Codex invocation."""

from pathlib import Path
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app import config
from app.domain.saju.services import codex_provider
from app.domain.saju.services.structured_output_schema import strict_output_schema


class CodexInvocationTests(unittest.TestCase):
    def test_requested_model_and_effort_are_explicit_cli_overrides(self) -> None:
        with patch.object(codex_provider, "_codex_executable_prefix", return_value=["codex"]), patch.multiple(
            codex_provider.settings,
            codex_model="gpt-6.1-sol",
            codex_reasoning_effort="xhigh",
            codex_profile=None,
        ):
            command = codex_provider._codex_command(Path("result.json"))
        self.assertEqual(command[command.index("--model") + 1], "gpt-6.1-sol")
        self.assertEqual(command[command.index("-c") + 1], 'model_reasoning_effort="xhigh"')
        self.assertEqual(command[-1], "-")

    def test_absent_effort_keeps_existing_codex_configuration(self) -> None:
        with patch.object(codex_provider, "_codex_executable_prefix", return_value=["codex"]), patch.multiple(
            codex_provider.settings, codex_model=None, codex_reasoning_effort=None, codex_profile=None
        ):
            command = codex_provider._codex_command(Path("result.json"))
        self.assertNotIn("-c", command)
        self.assertNotIn("--model", command)

    def test_installed_project_cli_takes_precedence_over_global_cli(self) -> None:
        project = Path("project")
        with patch.object(config, "REPO_ROOT", project), patch.object(Path, "exists", return_value=True):
            command = config._default_codex_command()
            entry = config._default_codex_js_path()
        self.assertEqual(Path(command).parent, project / "node_modules" / ".bin")
        self.assertEqual(entry, str(project / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"))

    def test_subprocess_boundary_receives_native_schema_and_stdin_without_a_model_call(self):
        schema = {"type": "object", "properties": {"answer": {"type": "string", "default": ""}}}
        def fake_run(command, **kwargs):
            schema_path = Path(command[command.index("--output-schema") + 1])
            self.assertEqual(json.loads(schema_path.read_text(encoding="utf-8")), strict_output_schema(schema))
            self.assertEqual(command[-1], "-")
            self.assertIn('"supplied_fact": "sample"', kwargs["input"])
            self.assertNotIn("shell", kwargs)
            Path(command[command.index("--output-last-message") + 1]).write_text('{"answer":"ok"}', encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch.object(codex_provider.settings, "runtime_environment", "development"), patch.object(
            codex_provider.subprocess, "run", side_effect=fake_run
        ) as run:
            result = codex_provider.call_codex_json(developer_prompt="Use supplied facts", user_payload={"supplied_fact": "sample"},
                output_schema=schema, schema_name="test")
        self.assertEqual(json.loads(result.output_text), {"answer": "ok"})
        self.assertEqual(run.call_count, 1)

    def test_production_cannot_launch_local_codex(self):
        with patch.object(codex_provider.settings, "runtime_environment", "production"), patch.object(codex_provider.subprocess, "run") as run:
            with self.assertRaises(codex_provider.CodexProviderError) as raised:
                codex_provider.call_codex_json(developer_prompt="", user_payload={}, output_schema={}, schema_name="test")
        self.assertEqual(raised.exception.reason, "codex_local_only")
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
