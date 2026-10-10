"""The Python quality ratchet, checked through its contract as a hook.

Each test sends one PostToolUse event on standard input and reads the exit status and
standard error. The expectations come from the docstring of the script: exit 0 when the
edit introduced nothing, exit 2 with a report of what it introduced, exit 1 when the hook
itself failed.

The tests need `git` 2.42 or later, `ruff`, `bash` and `python3` on PATH.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2] / "plugins" / "quality-ratchet"
HOOK = PLUGIN / "hooks" / "python_quality_ratchet.py"
REGISTRATION = PLUGIN / "hooks" / "hooks.json"

# T201, a rule outside Ruff's defaults: only the configuration of the fixture repository selects it.
PRINT_CALL = 'print("committed")\n'


def mutable_default(name: str) -> str:
    """A function with one B006 problem, a rule that only the hook adds."""
    return f"\n\ndef {name}(items=[]):\n    return items\n"


def branching(branches: int) -> str:
    """A function of McCabe complexity `branches` + 1."""
    tests = "".join(
        f"    if value == {number}:\n        return {number}\n" for number in range(branches)
    )
    return f"def classify(value):\n{tests}    return None\n"


class PythonQualityRatchet(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        home = self.scratch / "home"
        home.mkdir()
        # Built from nothing, so that no GIT_* variable and no git or Ruff configuration
        # of the caller reaches git, Ruff or the hook.
        self.environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Tests",
            "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "Tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
        }

    def git(self, directory: Path, *arguments: str) -> None:
        command = ["git", "-C", str(directory), *arguments]
        subprocess.run(command, env=self.environment, check=True, capture_output=True)

    def ordinary_clone(self) -> Path:
        tree = self.scratch / "clone"
        self.git(self.scratch, "init", "--quiet", str(tree))
        return tree

    def linked_worktree(self) -> Path:
        """A linked worktree of a bare repository: its `.git` is a file, not a directory."""
        tree = self.scratch / "linked"
        self.git(self.scratch, "init", "--quiet", "--bare", "bare.git")
        self.git(
            self.scratch / "bare.git", "worktree", "add", "--quiet", "--orphan", "-b", "work", str(tree)
        )
        return tree

    def committed(self, tree: Path, source: str) -> Path:
        """Commit `source` as a module of `tree`, a repository with its own Ruff configuration."""
        (tree / "ruff.toml").write_text('[lint]\nselect = ["T201"]\n')
        module = tree / "package" / "module.py"
        module.parent.mkdir()
        module.write_text(source)
        self.git(tree, "add", "--all")
        self.git(tree, "commit", "--quiet", "--message", "Fixture")
        return module

    def after_edit(
        self, edited: Path, *command: str, **environment: str
    ) -> subprocess.CompletedProcess[str]:
        """Run the hook, or `command` in its place, on the event of an edit of `edited`."""
        event = {
            "hook_event_name": "PostToolUse",
            "tool_name": "Edit",
            "tool_input": {"file_path": str(edited)},
        }
        return subprocess.run(
            command or [str(HOOK)],
            input=json.dumps(event),
            env=self.environment | environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_a_problem_that_the_edit_introduced_is_reported(self):
        for layout in (self.ordinary_clone, self.linked_worktree):
            with self.subTest(layout=layout.__name__):
                module = self.committed(layout(), "VALUE = 1\n")
                module.write_text("VALUE = 1\n" + mutable_default("collect"))
                result = self.after_edit(module)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("B006", result.stderr)

    def test_a_problem_of_a_rule_that_only_the_repository_selects_is_reported(self):
        module = self.committed(self.ordinary_clone(), "VALUE = 1\n")
        module.write_text("VALUE = 1\n" + PRINT_CALL)
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("T201", result.stderr)

    def test_problems_that_exist_at_head_are_not_reported(self):
        for layout in (self.ordinary_clone, self.linked_worktree):
            with self.subTest(layout=layout.__name__):
                source = PRINT_CALL + mutable_default("collect")
                module = self.committed(layout(), source)
                module.write_text("# This edit moves every line down and adds no problem.\n" + source)
                result = self.after_edit(module)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_problem_that_exists_at_head_is_left_out_of_the_report(self):
        module = self.committed(self.ordinary_clone(), PRINT_CALL)
        module.write_text(PRINT_CALL + mutable_default("collect"))
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("B006", result.stderr)
        self.assertNotIn("T201", result.stderr)

    def test_the_comparison_is_with_head_and_not_with_the_index(self):
        tree = self.ordinary_clone()
        module = self.committed(tree, "VALUE = 1\n")
        module.write_text("VALUE = 1\n" + mutable_default("collect"))
        self.git(tree, "add", "--all")
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("B006", result.stderr)

    def test_one_more_of_an_identical_problem_is_reported_once(self):
        source = "VALUE = 1\n" + mutable_default("first")
        module = self.committed(self.ordinary_clone(), source)
        module.write_text(source + mutable_default("second"))
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stderr.count("B006"), 1, result.stderr)

    def test_a_function_over_the_complexity_threshold_may_not_grow(self):
        # Ruff's default threshold is 10: the committed function is already at 11.
        module = self.committed(self.ordinary_clone(), branching(10))
        module.write_text(branching(11))
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("C901", result.stderr)

    def test_a_function_over_the_complexity_threshold_that_does_not_change_is_not_reported(self):
        module = self.committed(self.ordinary_clone(), branching(10))
        module.write_text("# This edit leaves the function as it is.\n" + branching(10))
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_file_that_is_not_python_is_ignored(self):
        notes = self.committed(self.ordinary_clone(), "VALUE = 1\n").with_name("notes.txt")
        notes.write_text(mutable_default("collect"))
        result = self.after_edit(notes)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_missing_ruff_is_a_failure_of_the_hook_itself(self):
        module = self.committed(self.ordinary_clone(), "VALUE = 1\n")
        module.write_text("VALUE = 2\n")
        tools = self.scratch / "tools"
        tools.mkdir()
        for tool in ("git", "python3"):
            (tools / tool).symlink_to(shutil.which(tool))
        result = self.after_edit(module, PATH=str(tools))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertRegex(result.stderr, "(?i)ruff.*not found")

    def test_a_failure_of_ruff_is_a_failure_of_the_hook_itself(self):
        tree = self.ordinary_clone()
        module = self.committed(tree, "VALUE = 1\n")
        module.write_text("VALUE = 2\n")
        (tree / "ruff.toml").write_text('[lint]\nselect = ["NOT-A-RULE"]\n')
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertRegex(result.stderr, "(?i)ruff.*failed")

    def test_the_ruff_of_the_virtual_environment_of_the_repository_is_preferred(self):
        # The docstring of the script does not state this; the README of the plugin does.
        tree = self.ordinary_clone()
        module = self.committed(tree, "VALUE = 1\n")
        module.write_text("VALUE = 1\n" + mutable_default("collect"))
        ruff = tree / ".venv" / "bin" / "ruff"
        ruff.parent.mkdir(parents=True)
        ruff.write_text("#!/bin/sh\n# Stands for a Ruff that finds no problem.\necho '[]'\n")
        ruff.chmod(0o755)
        result = self.after_edit(module)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_the_registration_keeps_the_stanza_of_the_settings_it_replaces(self):
        expected = {
            "type": "command",
            "command": '"${CLAUDE_PLUGIN_ROOT}/hooks/python_quality_ratchet.py"',
            "timeout": 90,
            "statusMessage": "Checking Python quality",
        }
        self.assertEqual(
            json.loads(REGISTRATION.read_text()),
            {"hooks": {"PostToolUse": [{"matcher": "Edit|Write", "hooks": [expected]}]}},
        )

    def test_the_registered_command_runs_from_a_root_with_spaces_and_parentheses(self):
        root = self.scratch / "plugin root (copy)"
        shutil.copytree(PLUGIN, root)
        command = json.loads(REGISTRATION.read_text())["hooks"]["PostToolUse"][0]["hooks"][0]["command"]
        module = self.committed(self.ordinary_clone(), "VALUE = 1\n")
        module.write_text("VALUE = 1\n" + mutable_default("collect"))
        # The harness replaces the variable in the text of the command, then runs a shell.
        result = self.after_edit(
            module, "bash", "-c", command.replace("${CLAUDE_PLUGIN_ROOT}", str(root))
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("B006", result.stderr)


if __name__ == "__main__":
    unittest.main()
