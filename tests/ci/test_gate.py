"""The gate, through its command line.

Each case runs `ci/gate.sh` in a scratch repository that passes every check, then with one
defect seeded, and reads the exit status and standard output. The expectations come from the
header of the script: `== <check>` before each check; one line per rule, which ends with
`none` or is followed by what the rule found; `gate: the check <name> failed` as the last line
and status 1 when a check fails; status 2 for a name that is no check.

A seed that the gate would find in this repository, such as a home directory path, a Unicode
dash or an email address, is built when the tests run. No case runs the check `tests` on this
repository: the suite of a scratch repository is one passing test, or the seeded one.

The tests need `git` 2.42 or later, `ruff`, `bash` and `python3` on PATH. Those of the check
`manifests` also need the Claude Code CLI, and are skipped where there is none.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[2] / "ci" / "gate.sh"
CLI = os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude")
CHECKS = ["tests", "lint", "contained", "dashes", "private", "version", "messages", "manifests"]

DASHES = {"U+2013": chr(0x2013), "U+2014": chr(0x2014)}
HOME_PATHS = ("/ho" + "me/someone/project", "/Use" + "rs/someone/project")
ADDRESS = "someone" + "@" + "example.org"
# Addresses that are not allowed; the last two only hold one that is.
NOT_ALLOWED = (ADDRESS, "not-" + "git@github.com", "tests@example.invalid" + ".example.org")
ALLOWED = (
    "git@github.com",
    "noreply@anthropic.com",
    "12345+someone@users.noreply.github.com",
    "tests@example.invalid",
)
DENIED = "A-STRING-OF-THE-DENYLIST"
TRAILER = "co-authored-by: Someone <tests@example.invalid>"

BACK_LINK = "Back to [the skill](../SKILL.md).\n"
PASSING_TEST = """\
import unittest


class Passing(unittest.TestCase):
    def test_passes(self):
        self.assertTrue(True)
"""
FAILING_TEST = """\
import unittest


class Failing(unittest.TestCase):
    def test_fails(self):
        self.fail("seeded")
"""
# The `grep` of the machine, but for one search, which ends in error as a search does where it
# cannot run: the search of files for an email address.
FAILING_GREP = """\
#!/usr/bin/env bash
if [ "$1" = -r ]; then
  for argument in "$@"; do
    case "$argument" in *@*) exit 2 ;; esac
  done
fi
exec "{grep}" "$@"
"""


def found_by(output: str, rule: str) -> list[str]:
    """What a rule found: the lines that follow its line, up to the next rule or check."""
    lines = output.splitlines()
    found = []
    for line in lines[lines.index(f"  {rule}:") + 1 :]:
        if line.startswith(("  ", "== ", "gate: ")):
            break
        found.append(line)
    return found


class GateCase(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        home = self.scratch / "home"
        home.mkdir()
        # Built from nothing, so that no variable and no configuration of the caller
        # reaches git, Ruff, the CLI or the gate.
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
        self.tree = self.repository(self.scratch / "clone")

    def git(self, directory: Path, *arguments: str) -> str:
        command = ["git", "-C", str(directory), *arguments]
        done = subprocess.run(command, env=self.environment, check=True, capture_output=True, text=True)
        return done.stdout.strip()

    def repository(self, tree: Path) -> Path:
        """A repository that passes every check: a passing test, a version, a marketplace of
        two plugins and sixteen files that link back to their skill."""
        self.git(self.scratch, "init", "--quiet", "--initial-branch", "main", str(tree))
        marketplace = {
            "name": "scratch",
            "owner": {"name": "Tests"},
            "plugins": [
                {"name": "first", "source": "./plugins/first"},
                {"name": "second", "source": "./plugins/second"},
            ],
        }
        files = {
            "ruff.toml": "line-length = 104\n",
            ".version": "0.0.0\n",
            "tests/__init__.py": "",
            "tests/test_passing.py": PASSING_TEST,
            ".claude-plugin/marketplace.json": json.dumps(marketplace),
            "plugins/first/.claude-plugin/plugin.json": json.dumps({"name": "first"}),
            "plugins/second/.claude-plugin/plugin.json": json.dumps({"name": "second"}),
            "plugins/first/skills/guide/SKILL.md": "---\nname: guide\ndescription: A guide.\n---\n",
        }
        for number in range(16):
            files[f"plugins/first/skills/guide/references/rule-{number:02}.md"] = BACK_LINK
        self.commit(tree, "Fixture", **files)
        return tree

    def commit(self, tree: Path, message: str, **files: str) -> str:
        """Commit `files`, given by path, with `message`; the hash of the commit."""
        for path, text in files.items():
            (tree / path).parent.mkdir(parents=True, exist_ok=True)
            (tree / path).write_text(text)
        self.git(tree, "add", "--all")
        self.git(tree, "commit", "--quiet", "--allow-empty", "--message", message)
        return self.git(tree, "rev-parse", "HEAD")

    def denylist(self, text: str, tree: Path | None = None) -> None:
        """The denylist of a main worktree, which git does not track; its line ends as given."""
        tree = tree or self.tree
        (tree / "docs" / "work").mkdir(parents=True)
        (tree / "docs" / "work" / "denylist.txt").write_bytes(text.encode())

    def gate(self, tree: Path, *arguments: str, **environment: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(GATE), *arguments],
            cwd=tree,
            env=self.environment | environment,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def assertPasses(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assertFailsAt(self, check: str, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[-1], f"gate: the check {check} failed")


class SeededDefects(GateCase):
    """One defect per rule: the check passes before it and fails with it."""

    def assertSeedFails(self, check: str, tree: Path | None = None, **files: str) -> None:
        tree = tree or self.tree
        self.assertPasses(self.gate(tree, check))
        self.commit(tree, "Seed", **files)
        self.assertFailsAt(check, self.gate(tree, check))

    def test_a_failing_test_fails_tests(self):
        self.assertSeedFails("tests", **{"tests/test_failing.py": FAILING_TEST})

    def test_an_unused_import_fails_lint(self):
        self.assertSeedFails("lint", **{"unused.py": "import os\n"})

    def test_a_file_that_the_formatter_would_change_fails_lint(self):
        self.assertSeedFails("lint", **{"unformatted.py": "value  =  1\n"})

    def test_a_file_of_a_plugin_that_reaches_outside_it_fails_contained(self):
        text = "See [the other plugin](../../second/README.md).\n"
        self.assertSeedFails("contained", **{"plugins/first/skills/guide/outside.md": text})

    def test_one_back_link_more_than_the_number_fails_contained(self):
        self.assertSeedFails("contained", **{"plugins/second/guide/references/rule.md": BACK_LINK})

    def test_one_back_link_fewer_than_the_number_fails_contained(self):
        guide = "plugins/first/skills/guide/references/rule-00.md"
        self.assertSeedFails("contained", **{guide: "A guide that lost its link.\n"})

    def test_a_unicode_dash_in_a_tracked_file_fails_dashes(self):
        for name, dash in DASHES.items():
            with self.subTest(dash=name):
                tree = self.repository(self.scratch / name)
                self.assertSeedFails("dashes", tree, **{"notes.md": f"one {dash} two\n"})

    def test_a_home_directory_path_fails_private(self):
        for number, path in enumerate(HOME_PATHS):
            with self.subTest(number=number):
                tree = self.repository(self.scratch / f"home-path-{number}")
                self.assertSeedFails("private", tree, **{"notes.md": f"It is in {path}.\n"})

    def test_an_address_that_is_not_allowed_fails_private(self):
        for number, address in enumerate(NOT_ALLOWED):
            with self.subTest(number=number):
                tree = self.repository(self.scratch / f"address-{number}")
                # On a line that holds an allowed address too: the rule reads addresses.
                text = f"Write to tests@example.invalid or to {address}.\n"
                self.assertSeedFails("private", tree, **{"notes.md": text})

    def test_a_string_of_the_denylist_fails_private_from_a_linked_worktree(self):
        # An empty line is no string. And a string is the same whatever ends its line: the line
        # break of another system, or a blank left after it.
        for number, line_end in enumerate(("\n", "\r\n", " \n", "\t\n")):
            with self.subTest(line_end=line_end):
                tree = self.repository(self.scratch / f"main-{number}")
                self.denylist(f"\n{DENIED}{line_end}", tree)
                linked = self.scratch / f"linked-{number}"
                self.git(tree, "worktree", "add", "--quiet", "-b", "work", str(linked))
                control = self.gate(linked, "private")
                self.assertPasses(control)
                self.assertIn("  denylist: 1 strings searched", control.stdout.splitlines())
                self.commit(linked, "Seed", **{"notes.md": f"It names {DENIED}.\n"})
                result = self.gate(linked, "private")
                self.assertFailsAt("private", result)
                # Neither a string of the denylist nor its path is printed.
                self.assertNotIn(DENIED, result.stdout + result.stderr)
                self.assertNotIn("denylist.txt", result.stdout + result.stderr)

    def test_a_version_of_two_numbers_fails_version(self):
        self.assertSeedFails("version", **{".version": "1.0\n"})

    def test_a_trailer_on_the_second_of_three_commits_after_a_tag_fails_messages(self):
        self.git(self.tree, "tag", "v0.0.1")
        self.assertPasses(self.gate(self.tree, "messages"))
        self.commit(self.tree, "First")
        second = self.commit(self.tree, f"Second\n\n{TRAILER}")
        self.commit(self.tree, "Third")
        result = self.gate(self.tree, "messages")
        self.assertFailsAt("messages", result)
        self.assertEqual(found_by(result.stdout, "a commit with a co-author trailer"), [second])

    def test_a_unicode_dash_in_a_message_fails_messages(self):
        for name, dash in DASHES.items():
            with self.subTest(dash=name):
                tree = self.repository(self.scratch / name)
                self.assertPasses(self.gate(tree, "messages"))
                seeded = self.commit(tree, f"One {dash} two")
                result = self.gate(tree, "messages")
                self.assertFailsAt("messages", result)
                rule = "a commit with a Unicode dash in its message"
                self.assertEqual(found_by(result.stdout, rule), [seeded])

    def test_a_home_directory_path_in_a_message_fails_messages(self):
        for number, path in enumerate(HOME_PATHS):
            with self.subTest(number=number):
                tree = self.repository(self.scratch / f"home-path-{number}")
                self.assertPasses(self.gate(tree, "messages"))
                seeded = self.commit(tree, f"Move it\n\nIt was in {path}.")
                result = self.gate(tree, "messages")
                self.assertFailsAt("messages", result)
                rule = "a commit with a home directory path in its message"
                self.assertEqual(found_by(result.stdout, rule), [seeded])

    def test_an_address_that_is_not_allowed_in_a_message_fails_messages(self):
        for number, address in enumerate(NOT_ALLOWED):
            with self.subTest(number=number):
                tree = self.repository(self.scratch / f"address-{number}")
                self.assertPasses(self.gate(tree, "messages"))
                # On a line that holds an allowed address too: the rule reads addresses.
                message = f"Thank them\n\nReported by {address}, relayed by git@github.com."
                seeded = self.commit(tree, message)
                result = self.gate(tree, "messages")
                self.assertFailsAt("messages", result)
                rule = "an email address that is not allowed in the message of a commit"
                self.assertEqual(found_by(result.stdout, rule), [f"{seeded}:{address}"])

    def test_a_string_of_the_denylist_in_a_message_fails_messages(self):
        self.denylist(f"{DENIED}\n")
        control = self.gate(self.tree, "messages")
        self.assertPasses(control)
        self.assertIn("  denylist: 1 strings searched", control.stdout.splitlines())
        seeded = self.commit(self.tree, f"Rename it\n\nIt was {DENIED}.")
        result = self.gate(self.tree, "messages")
        self.assertFailsAt("messages", result)
        rule = "a commit with a string of the denylist in its message"
        self.assertEqual(found_by(result.stdout, rule), [seeded])
        self.assertNotIn(DENIED, result.stdout + result.stderr)

    def test_two_defects_at_once_are_each_named_under_their_rule(self):
        self.denylist(f"{DENIED}\n")
        trailer = self.commit(self.tree, f"First\n\n{TRAILER}")
        denied = self.commit(self.tree, f"Second\n\nIt was {DENIED}.")
        result = self.gate(self.tree, "messages")
        self.assertFailsAt("messages", result)
        self.assertEqual(found_by(result.stdout, "a commit with a co-author trailer"), [trailer])
        rule = "a commit with a string of the denylist in its message"
        self.assertEqual(found_by(result.stdout, rule), [denied])


class PassingCases(GateCase):
    def test_every_check_but_manifests_passes_and_is_named(self):
        self.denylist(f"{DENIED}\n")
        result = self.gate(self.tree, "--no-cli")
        self.assertPasses(result)
        lines = result.stdout.splitlines()
        self.assertEqual([line[3:] for line in lines if line.startswith("== ")], CHECKS)
        self.assertEqual(lines.count("  denylist: 1 strings searched"), 2)
        self.assertIn("  commits read: 1", lines)
        version = subprocess.run(["ruff", "--version"], capture_output=True, text=True, check=True)
        self.assertIn(version.stdout.strip(), lines)
        self.assertEqual(result.stderr.splitlines()[-1], "OK")

    def test_only_the_checks_that_are_named_run_in_the_order_given(self):
        result = self.gate(self.tree, "version", "dashes")
        self.assertPasses(result)
        names = [line[3:] for line in result.stdout.splitlines() if line.startswith("== ")]
        self.assertEqual(names, ["version", "dashes"])

    def test_the_gate_stops_at_the_first_check_that_fails(self):
        dash = DASHES["U+2013"]
        self.commit(self.tree, "Seed", **{"unformatted.py": "value  =  1\n", "notes.md": f"{dash}\n"})
        result = self.gate(self.tree, "--no-cli")
        self.assertFailsAt("lint", result)
        self.assertNotIn("== contained", result.stdout.splitlines())

    def test_a_version_that_is_behind_a_tag_passes_version(self):
        self.git(self.tree, "tag", "v0.0.1")
        self.assertPasses(self.gate(self.tree, "version"))

    def test_a_trailer_on_a_commit_that_a_tag_reaches_passes_messages(self):
        self.commit(self.tree, f"Before the tag\n\n{TRAILER}")
        self.git(self.tree, "tag", "v0.0.1")
        self.commit(self.tree, "After the tag")
        self.assertPasses(self.gate(self.tree, "messages"))

    def test_a_title_that_names_the_key_of_the_trailer_passes_messages(self):
        self.commit(self.tree, "State the rule on the Co-Authored-By trailer")
        self.commit(self.tree, "Co-Authored-By: is the key of the trailer")
        self.assertPasses(self.gate(self.tree, "messages"))

    def test_the_addresses_that_are_allowed_pass_private_and_messages(self):
        text = "".join(f"Write to {address}.\n" for address in ALLOWED)
        self.commit(self.tree, f"Name the addresses\n\n{text}", **{"notes.md": text})
        self.assertPasses(self.gate(self.tree, "private", "messages"))

    def test_without_a_denylist_the_checks_say_that_they_found_no_file(self):
        for check in ("private", "messages"):
            with self.subTest(check=check):
                result = self.gate(self.tree, check)
                self.assertPasses(result)
                self.assertIn("  denylist: no file found", result.stdout.splitlines())

    def test_a_repository_under_a_path_with_a_space_and_a_parenthesis_passes(self):
        tree = self.repository(self.scratch / "a (b) c")
        self.assertPasses(self.gate(tree, "--no-cli"))


class RefusedCalls(GateCase):
    def test_a_name_that_is_no_check_ends_with_status_2(self):
        result = self.gate(self.tree, "lint", "spelling")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_a_denylist_that_is_a_directory_fails_private(self):
        (self.tree / "docs" / "work" / "denylist.txt").mkdir(parents=True)
        self.assertFailsAt("private", self.gate(self.tree, "private"))

    def test_a_denylist_that_is_a_link_to_no_file_fails_private(self):
        (self.tree / "docs" / "work").mkdir(parents=True)
        (self.tree / "docs" / "work" / "denylist.txt").symlink_to(self.scratch / "missing")
        self.assertFailsAt("private", self.gate(self.tree, "private"))

    def test_a_search_of_git_that_ends_in_error_fails_its_check(self):
        checks = ("contained", "dashes", "private")
        for check in checks:
            self.assertPasses(self.gate(self.tree, check))
        # git cannot read an index that is none: its searches end in error and find nothing.
        (self.tree / ".git" / "index").write_bytes(b"no index")
        for check in checks:
            with self.subTest(check=check):
                self.assertFailsAt(check, self.gate(self.tree, check))

    def test_a_search_behind_a_filter_that_ends_in_error_fails_its_check(self):
        self.assertPasses(self.gate(self.tree, "messages"))
        # The search of the messages for an address is the one whose result is filtered.
        stand_in = self.scratch / "bin" / "grep"
        stand_in.parent.mkdir()
        stand_in.write_text(FAILING_GREP.format(grep=shutil.which("grep")))
        stand_in.chmod(0o755)
        path = f"{stand_in.parent}{os.pathsep}{os.environ['PATH']}"
        self.assertFailsAt("messages", self.gate(self.tree, "messages", PATH=path))

    def test_without_a_cli_manifests_fails_unless_it_is_skipped(self):
        # A PATH that holds no `claude`, and still every tool that the gate needs.
        path = os.pathsep.join(
            directory
            for directory in os.environ["PATH"].split(os.pathsep)
            if not (Path(directory) / "claude").exists()
        )
        for tool in ("bash", "git", "python3", "ruff"):
            if shutil.which(tool, path=path) is None:
                self.skipTest(f"{tool} is in the same directory as claude")
        skipped = self.gate(self.tree, "--no-cli", PATH=path)
        self.assertPasses(skipped)
        self.assertIn("  skipped, as --no-cli asks", skipped.stdout.splitlines())
        self.assertFailsAt("manifests", self.gate(self.tree, PATH=path))


@unittest.skipUnless(CLI, "no Claude Code CLI: neither CLAUDE_CODE_EXECPATH nor claude on PATH")
class Manifests(GateCase):
    """The check `manifests`, with the real CLI under a scratch configuration."""

    def setUp(self):
        super().setUp()
        self.configuration = self.scratch / "configuration"
        self.environment |= {
            "CLAUDE_CONFIG_DIR": str(self.configuration),
            "CLAUDE_CODE_EXECPATH": CLI,
        }

    def test_every_check_passes_and_is_named(self):
        result = self.gate(self.tree)
        self.assertPasses(result)
        names = [line[3:] for line in result.stdout.splitlines() if line.startswith("== ")]
        self.assertEqual(names, CHECKS)

    def test_the_configuration_of_the_caller_is_left_alone(self):
        self.assertPasses(self.gate(self.tree, "manifests"))
        self.assertFalse(self.configuration.exists())
        self.assertEqual(list((self.scratch / "home").iterdir()), [])

    def test_the_cli_that_c_names_is_the_one_that_runs(self):
        result = self.gate(self.tree, "manifests", C=str(self.scratch / "missing"))
        self.assertFailsAt("manifests", result)

    def test_a_marketplace_file_with_no_name_fails_manifests(self):
        self.assertPasses(self.gate(self.tree, "manifests"))
        marketplace = json.loads((self.tree / ".claude-plugin" / "marketplace.json").read_text())
        del marketplace["name"]
        self.commit(self.tree, "Seed", **{".claude-plugin/marketplace.json": json.dumps(marketplace)})
        self.assertFailsAt("manifests", self.gate(self.tree, "manifests"))

    def test_a_nameless_manifest_of_a_plugin_that_is_not_listed_fails_manifests(self):
        self.assertPasses(self.gate(self.tree, "manifests"))
        # `a-plugin` sorts before `first` and `second`: it is not the last one validated.
        self.commit(self.tree, "Seed", **{"plugins/a-plugin/.claude-plugin/plugin.json": "{}"})
        self.assertFailsAt("manifests", self.gate(self.tree, "manifests"))


if __name__ == "__main__":
    unittest.main()
