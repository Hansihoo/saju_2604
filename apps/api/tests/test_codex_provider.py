"""Check that project-local model settings reach the real Codex invocation."""

from pathlib import Path
import unittest
from unittest.mock import patch

from app import config
from app.domain.saju.services import codex_provider


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


if __name__ == "__main__":
    unittest.main()
