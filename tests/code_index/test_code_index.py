"""The script of the `code-index` skill, through its hooks, its command line and its decisions.

The expectations come from what the plugin promises, not from the code. A worktree is eligible when
it is a linked worktree, the main worktree of its repository holds `.codegraph/`, and `codegraph` is
on PATH; nothing is done or printed for any other directory, the main worktree and a worktree of a
bare repository included. An eligible worktree without `.codegraph/` is indexed, by one call of
`codegraph init -y .` in it, when git ignores `.codegraph/` there, and is otherwise not indexed.
A failed index leaves no `.codegraph/` behind.

- After a `Bash` command that holds `worktree add` (`PostToolUse`), every eligible worktree of the
  repository at `cwd`, from its main worktree or any other, is indexed, and each one indexed is
  named in `hookSpecificOutput.additionalContext`, the output that reaches the model.
- At `SessionStart`, an eligible worktree at `cwd` gets one line: indexed now, has an index, or not
  indexed, each naming it. Codex sends the same event with two more fields.
- Any other event, input or argument: status 0 and nothing on standard output. The status is 0 in
  every case, since 2 is the status by which a hook blocks.
- `code_index.py <path>` prints `indexed <root>`, `has an index <root>` or `not indexed ...`.

A fake codegraph on PATH records each call and writes what codegraph 1.6.2 writes:
`.codegraph/codegraph.db`, and `.codegraph/.gitignore` holding `*` and `!.gitignore`. The tests
need git 2.36 or later.
"""

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[2] / "plugins/code-index/skills/code-index/code_index.py"
FAKE = """#!{python}
import os
import sys
import time
from pathlib import Path

with open(os.environ["FAKE_LOG"], "a", encoding="utf-8") as log:
    log.write(os.getcwd() + " " + " ".join(sys.argv[1:]) + "\\n")
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
if os.environ.get("FAKE_FAIL"):
    sys.exit(1)
if sys.argv[1:2] == ["init"]:
    folder = Path(".codegraph")
    folder.mkdir(exist_ok=True)
    (folder / "codegraph.db").write_bytes(b"")
    (folder / ".gitignore").write_text("*\\n!.gitignore\\n")
"""


def load():
    spec = importlib.util.spec_from_file_location("code_index", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def session(cwd, **more):
    event = {
        "session_id": "s",
        "transcript_path": os.devnull,
        "cwd": str(cwd),
        "hook_event_name": "SessionStart",
        "source": "startup",
    }
    return event | more


def bash(cwd, command, event="PostToolUse"):
    return {
        "session_id": "s",
        "transcript_path": os.devnull,
        "cwd": str(cwd),
        "hook_event_name": event,
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": "A command"},
        "tool_response": {"stdout": "", "stderr": "", "interrupted": False, "isImage": False},
        "tool_use_id": "t",
    }


class Decide(unittest.TestCase):
    def test_each_fact_decides_as_the_rule_says(self):
        code_index = load()
        rows = [
            ({}, "index"),
            ({"linked": False}, "skip"),
            ({"linked": False, "indexed": True}, "skip"),
            ({"main_indexed": False}, "skip"),
            ({"codegraph": False}, "skip"),
            ({"indexed": True}, "has an index"),
            ({"ignored": False}, "not indexed"),
            ({"indexed": True, "ignored": False}, "has an index"),
        ]
        eligible = {"linked": True, "main_indexed": True, "codegraph": True}
        for change, expected in rows:
            facts = {"indexed": False, "ignored": True} | eligible | change
            with self.subTest(**change):
                action, _reason = code_index.decide(code_index.Facts(root=Path("/w"), **facts))
                self.assertEqual(action, expected)


class CodeIndex(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        home = self.scratch / "home"
        home.mkdir()
        fake = self.scratch / "fake"
        fake.mkdir()
        (fake / "codegraph").write_text(FAKE.format(python=sys.executable))
        (fake / "codegraph").chmod(0o755)
        self.log = self.scratch / "calls.log"
        self.log.touch()
        # Built from nothing, so that no GIT_* variable, no git configuration and no global
        # ignore file of the caller reaches git or the script.
        self.environment = {
            "PATH": f"{fake}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Tests",
            "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "Tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
            "FAKE_LOG": str(self.log),
        }

    def git(self, directory, *arguments):
        command = ["git", "-C", str(directory), *arguments]
        done = subprocess.run(command, env=self.environment, check=True, capture_output=True, text=True)
        return done.stdout

    def repository(self, name="repository", ignore="/.codegraph/\n", indexed=True):
        """A repository whose `.gitignore` holds `/.worktree/` and `ignore`."""
        primary = self.scratch / name
        self.git(self.scratch, "init", "--quiet", "--initial-branch", "main", str(primary))
        (primary / "a.py").write_text("def f():\n    return 1\n")
        (primary / ".gitignore").write_text("/.worktree/\n" + ignore)
        self.git(primary, "add", "--all")
        self.git(primary, "commit", "--quiet", "--message", "Start")
        if indexed:
            (primary / ".codegraph").mkdir()
        return primary

    def worktree(self, primary, name="w"):
        self.git(primary, "worktree", "add", "--quiet", f".worktree/{name}", "-b", name)
        return primary / ".worktree" / name

    def run_script(self, *arguments, event=None, **environment):
        stdin = event if isinstance(event, str) or event is None else json.dumps(event)
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            input=stdin or "",
            cwd=self.scratch,
            env=self.environment | environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def hook(self, event, **environment):
        done = self.run_script("--hook", event=event, **environment)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout

    def calls(self):
        return self.log.read_text().splitlines()

    def test_a_session_in_an_eligible_worktree_indexes_it_and_says_so(self):
        worktree = self.worktree(self.repository())
        line = self.hook(session(worktree))
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])
        self.assertTrue((worktree / ".codegraph" / "codegraph.db").is_file())
        self.assertIn(str(worktree), line)
        self.assertIn("indexed", line)
        self.assertNotIn("not indexed", line)
        self.assertEqual(self.git(worktree, "status", "--porcelain"), "")

    def test_a_second_session_says_that_the_worktree_has_an_index_and_calls_nothing(self):
        worktree = self.worktree(self.repository())
        self.hook(session(worktree))
        line = self.hook(session(worktree))
        self.assertEqual(len(self.calls()), 1)
        self.assertIn("has an index", line)
        self.assertIn(str(worktree), line)

    def test_a_session_start_of_codex_is_read_as_one_of_claude_code(self):
        worktree = self.worktree(self.repository())
        line = self.hook(session(worktree, model="a-model", permission_mode="default"))
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])
        self.assertIn(str(worktree), line)

    def test_after_git_worktree_add_the_new_worktree_is_indexed_and_named_to_the_model(self):
        primary = self.repository()
        worktree = self.worktree(primary)
        output = self.hook(bash(primary, "git worktree add .worktree/w -b w"))
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])
        specific = json.loads(output)["hookSpecificOutput"]
        self.assertEqual(specific["hookEventName"], "PostToolUse")
        self.assertIn(str(worktree), specific["additionalContext"])

    def test_a_worktree_added_from_inside_another_worktree_is_indexed(self):
        primary = self.repository()
        first = self.worktree(primary, "first")
        self.hook(session(first))
        second = self.worktree(primary, "second")
        (first / "sub").mkdir()
        output = self.hook(bash(first / "sub", f"git -C {primary} worktree add .worktree/second"))
        self.assertEqual(self.calls(), [f"{first} init -y .", f"{second} init -y ."])
        context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(second), context)
        self.assertNotIn(str(first), context)

    def test_events_that_the_script_does_not_handle_change_nothing_and_print_nothing(self):
        primary = self.repository()
        worktree = self.worktree(primary)
        edit = {"hook_event_name": "PostToolUse", "cwd": str(primary), "tool_name": "Edit"}
        events = {
            "no input": "",
            "text that is no JSON": "not json",
            "a JSON array": "[]",
            "an empty object": "{}",
            "an event Stop": {"hook_event_name": "Stop", "cwd": str(primary)},
            "Edit with a file_path": edit | {"tool_input": {"file_path": "a.py"}},
            "Edit with a command": edit | {"tool_input": {"command": "git worktree add x"}},
            "Bash without worktree add": bash(primary, "git status"),
            "Bash before its command": bash(primary, "git worktree add x", "PreToolUse"),
            "Bash whose command is a number": bash(primary, 42),
            "Bash whose tool_input is null": bash(primary, "x") | {"tool_input": None},
            "Bash whose cwd is a number": bash(primary, "git worktree add x") | {"cwd": 42},
            "a session whose cwd is missing": {"hook_event_name": "SessionStart"},
        }
        for name, event in events.items():
            with self.subTest(name):
                self.assertEqual(self.hook(event), "")
                self.assertEqual(self.calls(), [])
                self.assertFalse((worktree / ".codegraph").exists())

    def test_a_cwd_outside_any_repository_changes_nothing(self):
        worktree = self.worktree(self.repository())
        self.assertEqual(self.hook(bash(self.scratch, "git worktree add x")), "")
        self.assertEqual(self.hook(session(self.scratch)), "")
        self.assertEqual(self.calls(), [])
        self.assertFalse((worktree / ".codegraph").exists())

    def test_the_main_worktree_and_a_worktree_of_an_unindexed_one_get_nothing(self):
        primary = self.repository()
        plain = self.worktree(self.repository("plain", indexed=False))
        for directory in (primary, plain):
            with self.subTest(directory=directory.name):
                self.assertEqual(self.hook(session(directory)), "")
        self.assertEqual(self.calls(), [])
        self.assertFalse((plain / ".codegraph").exists())

    def test_a_worktree_of_a_bare_repository_gets_nothing(self):
        self.git(self.scratch, "init", "--quiet", "--bare", "bare.git")
        tree = self.scratch / "linked"
        bare = self.scratch / "bare.git"
        self.git(bare, "worktree", "add", "--quiet", "--orphan", "-b", "w", str(tree))
        # The parent of the common directory is no main worktree, even with an index in it.
        (self.scratch / ".codegraph").mkdir()
        self.assertEqual(self.hook(session(tree)), "")
        self.assertEqual(self.calls(), [])

    def test_without_codegraph_on_path_nothing_is_done_or_printed(self):
        worktree = self.worktree(self.repository())
        bare_path = self.scratch / "bin"
        bare_path.mkdir()
        (bare_path / "git").symlink_to(shutil.which("git"))
        self.assertEqual(self.hook(session(worktree), PATH=str(bare_path)), "")
        self.assertFalse((worktree / ".codegraph").exists())

    def test_a_worktree_is_indexed_only_where_git_ignores_its_codegraph_folder(self):
        rules = {
            "nothing": ("", "", False),
            "/.codegraph/ in .gitignore": ("/.codegraph/\n", "", True),
            ".codegraph in .gitignore": (".codegraph\n", "", True),
            ".codegraph/ in the global ignore file": ("", ".codegraph/\n", True),
        }
        for number, (name, (ignore, global_ignore, indexed)) in enumerate(rules.items()):
            with self.subTest(name):
                ignore_file = Path(self.environment["HOME"]) / ".config" / "git" / "ignore"
                ignore_file.parent.mkdir(parents=True, exist_ok=True)
                ignore_file.write_text(global_ignore)
                worktree = self.worktree(self.repository(f"r{number}", ignore=ignore))
                line = self.hook(session(worktree))
                self.assertEqual((worktree / ".codegraph").exists(), indexed)
                self.assertEqual("not indexed" in line, not indexed)
                self.assertIn(str(worktree), line)
                self.assertEqual(self.git(worktree, "status", "--porcelain"), "")

    def test_a_rule_on_the_folders_contents_is_indexed_and_leaves_codegraphs_file_untracked(self):
        worktree = self.worktree(self.repository(ignore=".codegraph/*\n"))
        self.hook(session(worktree))
        self.assertTrue((worktree / ".codegraph").is_dir())
        self.assertEqual(self.git(worktree, "status", "--porcelain"), "?? .codegraph/\n")

    def test_two_hooks_at_once_on_one_new_worktree_index_it_once(self):
        primary = self.repository()
        worktree = self.worktree(primary)
        event = json.dumps(bash(primary, "git worktree add .worktree/w -b w"))
        environment = self.environment | {"FAKE_SLEEP": "1"}
        hooks = [
            subprocess.Popen(
                [sys.executable, str(SCRIPT), "--hook"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                env=environment,
                text=True,
            )
            for _ in range(2)
        ]
        for process in hooks:
            process.communicate(event, timeout=60)
            self.assertEqual(process.returncode, 0)
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])
        self.assertTrue((worktree / ".codegraph" / "codegraph.db").is_file())

    def test_a_hook_whose_facts_predate_another_hooks_index_leaves_that_index(self):
        # The facts a concurrent hook gathered before the other made the folder, acted on
        # after it: the race that two hooks at once only sometimes reach.
        code_index = load()
        worktree = self.worktree(self.repository())
        with mock.patch.dict(os.environ, self.environment, clear=True):
            stale = code_index.gather(worktree)
            first, second = code_index.act(stale), code_index.act(stale)
        self.assertEqual((first[0], second[0]), ("indexed", "has an index"))
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])

    def test_a_failed_index_leaves_no_folder_and_the_line_says_not_indexed(self):
        worktree = self.worktree(self.repository())
        line = self.hook(session(worktree), FAKE_FAIL="1")
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])
        self.assertFalse((worktree / ".codegraph").exists())
        self.assertIn("not indexed", line)

    def test_a_hook_stopped_by_sigterm_while_it_indexes_leaves_no_folder(self):
        # A client that ends a hook at its timeout: a folder left behind would pass for an
        # index at every later run.
        worktree = self.worktree(self.repository())
        process = subprocess.Popen(
            [sys.executable, str(SCRIPT), "--hook"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            env=self.environment | {"FAKE_SLEEP": "30"},
            text=True,
        )
        process.stdin.write(json.dumps(session(worktree)))
        process.stdin.close()
        deadline = time.monotonic() + 30
        while not self.calls() and time.monotonic() < deadline:
            time.sleep(0.05)
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.wait(timeout=30), 0)
        self.assertEqual(self.calls(), [f"{worktree} init -y ."])
        self.assertFalse((worktree / ".codegraph").exists())

    def test_the_command_line_acts_for_the_worktree_that_holds_the_path(self):
        worktree = self.worktree(self.repository())
        (worktree / "sub").mkdir()
        self.assertEqual(self.run_script(str(worktree / "sub")).stdout, f"indexed {worktree}\n")
        self.assertEqual(self.run_script(str(worktree)).stdout, f"has an index {worktree}\n")
        outside = self.run_script(str(self.scratch))
        self.assertTrue(outside.stdout.startswith("not indexed "), outside.stdout)
        self.assertEqual(len(self.calls()), 1)

    def test_a_bad_argument_ends_with_status_0_and_nothing_on_standard_output(self):
        for arguments in ([], ["a", "b"], ["--no-such-option"], ["--hook", "x"]):
            with self.subTest(arguments=arguments):
                done = self.run_script(*arguments)
                self.assertEqual((done.returncode, done.stdout), (0, ""))

    def test_the_script_runs_by_its_own_first_line(self):
        self.assertTrue(os.access(SCRIPT, os.X_OK))
        done = subprocess.run(
            [str(SCRIPT), "--hook"], input="", env=self.environment, capture_output=True, timeout=60
        )
        self.assertEqual((done.returncode, done.stdout), (0, b""))


if __name__ == "__main__":
    unittest.main()
