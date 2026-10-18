"""The installer, through its command line.

Each case writes clones in a scratch home directory and runs `install.sh` from one of them, the
holding clone, with a stand-in for the Claude Code CLI that records its arguments. It reads the
exit status, the output, the calls of the stand-in and what the script left in the home
directory. The expectations come from the header of the script. The clones have names of the
tests' own: the holding clone has a plugin with two skills and a plugin with none, and another
clone has one plugin with one skill.

The cases of the class `RealCli` run the Claude Code CLI itself on a copy of this repository,
under a scratch configuration, and are skipped where there is none.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = os.environ.get("CLAUDE_CODE_EXECPATH") or shutil.which("claude")

# Each clone that the cases write: the name of its marketplace, and the skills of each plugin.
HOLDING = ("holding", {"first": ["alpha", "beta"], "second": []})
OTHER = ("other", {"third": ["gamma"]})

# Records its arguments; reads all of its standard input, as a command may; fails when its
# second argument, the verb, is the one that STAND_IN_FAILS names: `list`, `marketplace`,
# `install` or `update`; prints STAND_IN_LIST for `list`.
STAND_IN = """\
#!/usr/bin/env bash
echo "$*" >>"{log}"
cat >/dev/null
[ "$2" != "${{STAND_IN_FAILS:-}}" ] || exit 1
[ "$2" != list ] || printf '%s\\n' "${{STAND_IN_LIST:-[]}}"
"""


def write_clone(directory: Path, marketplace: str, plugins: dict[str, list[str]]) -> Path:
    """A clone of a marketplace: its marketplace file, and a directory for each plugin with a
    SKILL.md for each of its skills."""
    manifest = directory / ".claude-plugin" / "marketplace.json"
    manifest.parent.mkdir(parents=True)
    entries = [{"name": plugin, "source": f"./plugins/{plugin}"} for plugin in plugins]
    manifest.write_text(
        json.dumps({"name": marketplace, "owner": {"name": "Tests"}, "plugins": entries})
    )
    for plugin, skills in plugins.items():
        (directory / "plugins" / plugin).mkdir(parents=True)
        for skill in skills:
            (directory / "plugins" / plugin / "skills" / skill).mkdir(parents=True)
            (directory / "plugins" / plugin / "skills" / skill / "SKILL.md").write_text(
                f"---\nname: {skill}\ndescription: A skill of the tests.\n---\n"
            )
    return directory


class InstallCase(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.home = self.scratch / "home"
        self.holding = write_clone(self.home / "src" / "holding", *HOLDING)
        shutil.copy2(ROOT / "install.sh", self.holding / "install.sh")
        self.rules = self.holding / "instructions" / "global.md"
        self.rules.parent.mkdir()
        self.rules.write_text("The shared rules of the tests.\n")
        self.other = write_clone(self.home / "src" / "other", *OTHER)
        self.log = self.scratch / "calls.log"
        self.stand_in = self.stand_in_at(self.scratch / "bin" / "claude", self.log)
        # Built from nothing, so that no variable and no configuration of the caller reaches
        # the script. OSTYPE as bash sets it on Linux, whatever the system of the caller.
        self.environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.home),
            "C": str(self.stand_in),
            "OSTYPE": "linux-gnu",
        }

    def stand_in_at(self, path: Path, log: Path) -> Path:
        log.touch()
        path.parent.mkdir(exist_ok=True)
        path.write_text(STAND_IN.format(log=log))
        path.chmod(0o755)
        return path

    def install(
        self, *clones: str, holding: Path | None = None, cwd: Path | None = None, **environment: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str((holding or self.holding) / "install.sh"), *clones],
            env=self.environment | environment,
            cwd=cwd or self.scratch,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def skill(self, clone: Path, plugin: str, name: str) -> Path:
        return clone / "plugins" / plugin / "skills" / name

    def calls(self, log: Path | None = None) -> list[str]:
        return (log or self.log).read_text().splitlines()

    def snapshot(self) -> dict[str, tuple]:
        """What the home directory holds: each link with its target, each file with its
        content, each directory."""
        state = {}
        for path in self.home.rglob("*"):
            if path.is_symlink():
                state[str(path)] = ("link", os.readlink(path))
            elif path.is_dir():
                state[str(path)] = ("directory",)
            else:
                state[str(path)] = ("file", path.read_bytes())
        return state

    def clear(self, *names: str) -> None:
        """Removes each of these entries of the home directory: a link, a file or a directory."""
        for name in names:
            path = self.home / name
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path, ignore_errors=True)

    def assertPasses(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assertLinked(self, place: Path, target: Path) -> None:
        self.assertTrue(place.is_symlink(), place)
        self.assertTrue(place.samefile(target), place)


class Installs(InstallCase):
    def run_with_both_clones(self) -> subprocess.CompletedProcess[str]:
        # The other clone by a path from the working directory, which is not its parent.
        return self.install(str(self.holding), "home/src/other", cwd=self.scratch)

    def test_one_link_per_skill_of_each_clone_and_nothing_else_in_the_skills_of_the_user(self):
        skills = self.home / ".agents" / "skills"
        with self.subTest(clones="none named"):
            self.assertPasses(self.install())
            self.assertCountEqual(os.listdir(skills), ["alpha", "beta"])
            self.assertLinked(skills / "alpha", self.skill(self.holding, "first", "alpha"))
            self.assertLinked(skills / "beta", self.skill(self.holding, "first", "beta"))
        with self.subTest(clones="both named"):
            self.assertPasses(self.run_with_both_clones())
            self.assertCountEqual(os.listdir(skills), ["alpha", "beta", "gamma"])
            self.assertLinked(skills / "gamma", self.skill(self.other, "third", "gamma"))

    def test_a_relative_path_is_read_from_the_working_directory_whatever_cdpath_says(self):
        # A clone of another marketplace at the same relative path from the directory that
        # CDPATH names, where `cd` would look first.
        decoy = self.scratch / "decoy"
        write_clone(decoy / "home" / "src" / "other", "decoy", {"fourth": []})
        result = self.install("home/src/other", cwd=self.scratch, CDPATH=str(decoy))
        self.assertPasses(result)
        self.assertIn(f"plugin marketplace add {self.other}", self.calls())

    def test_the_script_run_by_a_relative_path_uses_the_holding_clone_whatever_cdpath_says(self):
        # A clone of another marketplace, with shared rules of its own, at the path of the holding
        # clone from the directory that CDPATH names, where `cd` would look first.
        decoy = self.scratch / "decoy"
        clone = write_clone(decoy / "home" / "src" / "holding", "decoy", {"fourth": []})
        (clone / "instructions").mkdir()
        (clone / "instructions" / "global.md").write_text("The shared rules of the decoy.\n")
        result = self.install(holding=Path("home/src/holding"), cwd=self.scratch, CDPATH=str(decoy))
        self.assertPasses(result)
        self.assertIn(f"plugin marketplace add {self.holding}", self.calls())
        self.assertLinked(self.home / ".codex" / "AGENTS.md", self.rules)

    def test_a_module_in_the_working_directory_is_not_run_and_nothing_is_written_there(self):
        # Python looks for a module in its working directory first, unless told not to.
        work = self.scratch / "work"
        work.mkdir()
        (work / "json.py").write_text('open("ran", "w").close()\n')
        self.assertPasses(self.install(cwd=work))
        self.assertEqual(os.listdir(work), ["json.py"])

    def test_a_clone_without_skills_gets_no_link_and_its_plugins_are_installed(self):
        bare = write_clone(self.home / "src" / "bare", "bare", {"hooks": []})
        result = self.install(str(bare))
        self.assertPasses(result)
        # A directory is made only to hold a link.
        self.assertFalse((self.home / ".agents").exists())
        self.assertIn("plugin update hooks@bare", self.calls())
        self.assertIn('    "~/src/bare/plugins/hooks": true,', result.stdout.splitlines())

    def test_a_run_that_links_no_skill_passes_when_the_skills_of_the_user_are_claude_codes(self):
        (self.home / ".claude" / "skills").mkdir(parents=True)
        (self.home / ".agents").mkdir()
        (self.home / ".agents" / "skills").symlink_to(self.home / ".claude" / "skills")
        bare = write_clone(self.home / "src" / "bare", "bare", {"hooks": []})
        self.assertPasses(self.install(str(bare)))

    def test_the_cli_lists_once_then_registers_each_clone_and_installs_then_updates_its_plugins(self):
        self.assertPasses(self.run_with_both_clones())
        self.assertEqual(
            self.calls(),
            [
                "plugin list --json",
                f"plugin marketplace add {self.holding}",
                "plugin install first@holding",
                "plugin update first@holding",
                "plugin install second@holding",
                "plugin update second@holding",
                f"plugin marketplace add {self.other}",
                "plugin install third@other",
                "plugin update third@other",
            ],
        )

    def test_one_entry_for_vs_code_per_plugin_from_the_home_directory_and_no_home_path(self):
        result = self.run_with_both_clones()
        self.assertPasses(result)
        lines = result.stdout.splitlines()
        start = lines.index('  add these entries to "chat.pluginLocations" in the user settings:')
        self.assertEqual(
            lines[start + 1 :],
            [
                '    "~/src/holding/plugins/first": true,',
                '    "~/src/holding/plugins/second": true,',
                '    "~/src/other/plugins/third": true,',
            ],
        )
        self.assertNotIn(str(self.home), result.stdout)

    def test_a_run_adds_links_and_their_directories_and_changes_nothing_that_was_there(self):
        before = self.snapshot()
        self.assertPasses(self.run_with_both_clones())
        after = self.snapshot()
        self.assertEqual({path: after[path] for path in before}, before)
        added = {path: state[0] for path, state in after.items() if path not in before}
        self.assertTrue(added)
        self.assertLessEqual(set(added.values()), {"link", "directory"}, added)

    def test_the_instruction_links_lead_to_the_shared_rules_of_the_holding_clone(self):
        for name, clones in (("none named", ()), ("only another named", (str(self.other),))):
            with self.subTest(clones=name):
                for parent in (".codex", ".config"):
                    shutil.rmtree(self.home / parent, ignore_errors=True)
                self.assertPasses(self.install(*clones))
                self.assertLinked(self.home / ".codex" / "AGENTS.md", self.rules)
                prompts = self.home / ".config" / "Code" / "User" / "prompts"
                self.assertLinked(prompts / "shift-left.instructions.md", self.rules)

    def test_on_macos_the_instructions_of_vs_code_are_linked_in_its_user_folder_there(self):
        # OSTYPE as bash sets it on macOS.
        result = self.install(OSTYPE="darwin23")
        self.assertPasses(result)
        user = self.home / "Library" / "Application Support" / "Code" / "User"
        self.assertLinked(user / "prompts" / "shift-left.instructions.md", self.rules)
        self.assertFalse((self.home / ".config").exists())
        self.assertIn(
            "  ~/Library/Application Support/Code/User/prompts/shift-left.instructions.md: linked",
            result.stdout.splitlines(),
        )

    def test_with_codex_home_set_the_instructions_of_codex_are_linked_there_and_not_in_dot_codex(self):
        codex_home = self.scratch / "codex"
        result = self.install(CODEX_HOME=str(codex_home))
        self.assertPasses(result)
        self.assertLinked(codex_home / "AGENTS.md", self.rules)
        self.assertFalse((self.home / ".codex").exists())
        self.assertIn(f"  {codex_home / 'AGENTS.md'}: linked", result.stdout.splitlines())

    def test_a_slash_at_the_end_of_home_codex_home_or_claude_config_dir_changes_no_place(self):
        codex_home = self.scratch / "codex"
        config = self.scratch / "config"
        result = self.install(
            HOME=f"{self.home}/", CODEX_HOME=f"{codex_home}/", CLAUDE_CONFIG_DIR=f"{config}/"
        )
        self.assertPasses(result)
        lines = result.stdout.splitlines()
        self.assertIn(f"  {codex_home}/AGENTS.md: linked", lines)
        self.assertIn(f"  {config}/CLAUDE.md: add this line to import the shared rules:", lines)
        self.assertIn("    @~/src/holding/instructions/global.md", lines)
        self.assertIn('    "~/src/holding/plugins/first": true,', lines)
        self.assertNotIn(str(self.home), result.stdout)

    def test_a_second_run_changes_nothing_and_says_each_link_is_already_linked(self):
        first = self.install()
        self.assertPasses(first)
        before = self.snapshot()
        second = self.install()
        self.assertPasses(second)
        self.assertEqual(self.snapshot(), before)
        places = (
            "~/.agents/skills/alpha",
            "~/.agents/skills/beta",
            "~/.codex/AGENTS.md",
            "~/.config/Code/User/prompts/shift-left.instructions.md",
        )
        for place in places:
            with self.subTest(place=place):
                self.assertIn(f"  {place}: linked", first.stdout.splitlines())
                self.assertIn(f"  {place}: already linked", second.stdout.splitlines())

    def test_a_plugin_that_the_list_holds_for_the_user_is_updated_and_not_installed(self):
        listed = [{"id": "first@holding", "scope": "user", "enabled": False}]
        self.assertPasses(self.install(STAND_IN_LIST=json.dumps(listed)))
        calls = self.calls()
        self.assertNotIn("plugin install first@holding", calls)
        self.assertEqual(calls.count("plugin update first@holding"), 1)
        self.assertIn("plugin install second@holding", calls)

    def test_a_plugin_that_the_list_holds_for_a_project_only_is_installed_for_the_user(self):
        listed = [{"id": "first@holding", "scope": "project", "enabled": True}]
        self.assertPasses(self.install(STAND_IN_LIST=json.dumps(listed)))
        self.assertIn("plugin install first@holding", self.calls())

    def test_one_directory_for_the_skills_of_codex_and_of_the_user_passes_at_each_run(self):
        agents = self.home / ".agents" / "skills"
        codex = self.home / ".codex" / "skills"
        for real, link in ((codex, agents), (agents, codex)):
            with self.subTest(link=str(link.relative_to(self.home))):
                for parent in (".agents", ".codex", ".config"):
                    shutil.rmtree(self.home / parent, ignore_errors=True)
                real.mkdir(parents=True)
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(real)
                for _ in range(2):
                    self.assertPasses(self.install())
                self.assertLinked(agents / "alpha", self.skill(self.holding, "first", "alpha"))

    def test_links_made_through_a_linked_directory_are_kept_and_said_already_linked(self):
        # The holding clone reached through a link to its directory: another path, the same files.
        through = self.scratch / "through"
        through.symlink_to(self.holding)
        skill = self.home / ".agents" / "skills" / "alpha"
        agents_md = self.home / ".codex" / "AGENTS.md"
        made = {
            skill: through / "plugins" / "first" / "skills" / "alpha",
            agents_md: through / "instructions" / "global.md",
        }
        for place, target in made.items():
            place.parent.mkdir(parents=True)
            place.symlink_to(target)
        result = self.install()
        self.assertPasses(result)
        for place, target in made.items():
            with self.subTest(place=str(place.relative_to(self.home))):
                self.assertEqual(os.readlink(place), str(target))
                shown = f"~/{place.relative_to(self.home)}"
                self.assertIn(f"  {shown}: already linked", result.stdout.splitlines())


class ImportCheck(InstallCase):
    """The check of the user-level CLAUDE.md of Claude Code, which runs with a CLI or without."""

    ADD = "  ~/.claude/CLAUDE.md: add this line to import the shared rules:"
    IMPORTS = "  ~/.claude/CLAUDE.md: imports the shared rules"
    THROUGH_A_LINK = (
        "  ~/.claude/CLAUDE.md: import the shared rules through a link, as their path holds # or \\"
    )

    def write_claude_md(self, text: str, directory: Path | None = None) -> None:
        directory = directory or self.home / ".claude"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "CLAUDE.md").write_text(text)

    def assertAsksForLine(self, result: subprocess.CompletedProcess[str], line: str) -> None:
        self.assertPasses(result)
        lines = result.stdout.splitlines()
        self.assertIn(self.ADD, lines)
        self.assertEqual(lines[lines.index(self.ADD) + 1], f"    {line}")

    def test_without_a_claude_md_the_line_to_add_is_printed_and_no_file_is_made(self):
        self.assertAsksForLine(self.install(), "@~/src/holding/instructions/global.md")
        self.assertFalse((self.home / ".claude").exists())

    def test_a_line_that_imports_the_shared_rules_by_any_path_is_reported(self):
        (self.home / "via").symlink_to(self.holding)
        (self.home / "with space").symlink_to(self.holding)
        texts = {
            "absolute, through a linked directory": f"@{self.home}/via/instructions/global.md\n",
            "from ~/, with an escaped space": "@~/with\\ space/instructions/global.md\n",
            "from the directory of the file": "@../src/holding/instructions/global.md\n",
            "the last line, with no line break": "@~/src/holding/instructions/global.md",
        }
        for name, text in texts.items():
            with self.subTest(line=name):
                self.write_claude_md(f"# Instructions\n\nSome text.\n{text}")
                result = self.install()
                self.assertPasses(result)
                self.assertIn(self.IMPORTS, result.stdout.splitlines())
                self.assertNotIn(self.ADD, result.stdout.splitlines())

    def test_a_claude_md_that_is_a_link_to_the_shared_rules_is_reported_and_no_line_is_asked(self):
        # A line added to it would go into the shared rules.
        (self.home / ".claude").mkdir()
        (self.home / ".claude" / "CLAUDE.md").symlink_to(self.rules)
        result = self.install()
        self.assertPasses(result)
        lines = result.stdout.splitlines()
        self.assertIn("  ~/.claude/CLAUDE.md: is the shared rules", lines)
        self.assertNotIn(self.ADD, lines)

    def test_a_path_ends_before_its_first_hash_as_claude_code_reads_it(self):
        with self.subTest(line="the shared rules, then a fragment"):
            self.write_claude_md("@~/src/holding/instructions/global.md#rules\n")
            result = self.install()
            self.assertPasses(result)
            self.assertIn(self.IMPORTS, result.stdout.splitlines())
        with self.subTest(line="through a directory whose name holds a hash"):
            (self.home / "c#").symlink_to(self.holding)
            self.write_claude_md("@~/c#/instructions/global.md\n")
            self.assertAsksForLine(self.install(), "@~/src/holding/instructions/global.md")

    def test_no_line_is_printed_when_the_path_of_the_shared_rules_holds_a_hash_or_a_backslash(self):
        # Claude Code ends a path at a `#`, and at a `\` that no space follows.
        for directory in ("c#", "b\\a"):
            with self.subTest(directory=directory):
                copy = self.home / "src" / directory / "holding"
                shutil.copytree(self.holding, copy)
                result = self.install(holding=copy)
                self.clear(".agents", ".codex", ".config")
                self.assertPasses(result)
                lines = result.stdout.splitlines()
                self.assertIn(self.THROUGH_A_LINK, lines)
                self.assertNotIn(self.ADD, lines)

    def test_a_line_inside_an_html_comment_imports_nothing(self):
        line = "@~/src/holding/instructions/global.md"
        with self.subTest(text="the line inside a comment"):
            self.write_claude_md(f"# Mine\n\n<!--\n{line}\n-->\n")
            self.assertAsksForLine(self.install(), line)
        with self.subTest(text="the line after two comments"):
            self.write_claude_md(f"<!-- A note. -->\n  <!--\n@~/other.md\n-->\n{line}\n")
            result = self.install()
            self.assertPasses(result)
            self.assertIn(self.IMPORTS, result.stdout.splitlines())

    def test_a_line_inside_a_fenced_code_block_imports_nothing(self):
        # Claude Code skips code blocks, a comment inside one included.
        line = "@~/src/holding/instructions/global.md"
        asked = {
            "the line inside a fence of backticks": f"# Mine\n\n```\n{line}\n```\n",
            "the line after a shorter fence inside a longer one": f"````\n```\n{line}\n````\n",
            "the line inside a fence that is never closed": f"~~~ text\n{line}\n",
        }
        for name, text in asked.items():
            with self.subTest(text=name):
                self.write_claude_md(text)
                self.assertAsksForLine(self.install(), line)
        imported = {
            "the line after a comment opened inside a fence": f"```\n<!-- example\n```\n{line}\n",
            "the line after a fence opened inside a comment": f"<!--\n~~~\n-->\n{line}\n",
        }
        for name, text in imported.items():
            with self.subTest(text=name):
                self.write_claude_md(text)
                result = self.install()
                self.assertPasses(result)
                self.assertIn(self.IMPORTS, result.stdout.splitlines())

    def test_a_line_that_imports_another_file_is_not_reported(self):
        (self.home / "other.md").write_text("Other rules.\n")
        self.write_claude_md("@~/other.md\n")
        self.assertAsksForLine(self.install(), "@~/src/holding/instructions/global.md")

    def test_the_claude_md_read_is_the_one_of_claude_config_dir_when_it_is_set(self):
        config = self.scratch / "config"
        importing = "@~/src/holding/instructions/global.md\n"
        with self.subTest(importing="the one of CLAUDE_CONFIG_DIR"):
            self.write_claude_md(importing, config)
            self.write_claude_md("No import.\n")
            result = self.install(CLAUDE_CONFIG_DIR=str(config))
            self.assertPasses(result)
            self.assertIn(f"  {config}/CLAUDE.md: imports the shared rules", result.stdout.splitlines())
        with self.subTest(importing="the one of ~/.claude"):
            self.write_claude_md("No import.\n", config)
            self.write_claude_md(importing)
            result = self.install(CLAUDE_CONFIG_DIR=str(config))
            self.assertPasses(result)
            self.assertIn(
                f"  {config}/CLAUDE.md: add this line to import the shared rules:",
                result.stdout.splitlines(),
            )

    def test_the_line_to_add_escapes_a_space_and_is_absolute_outside_the_home_directory(self):
        copies = (
            (self.home / "with space" / "holding", "@~/with\\ space/holding/instructions/global.md"),
            (self.scratch / "outside", f"@{self.scratch}/outside/instructions/global.md"),
        )
        for copy, line in copies:
            with self.subTest(holding=str(copy)):
                shutil.copytree(self.holding, copy)
                result = self.install(holding=copy)
                for parent in (".agents", ".codex", ".config"):
                    shutil.rmtree(self.home / parent, ignore_errors=True)
                self.assertAsksForLine(result, line)


class Refusals(InstallCase):
    def assertRefusedAndUnchanged(
        self, result: subprocess.CompletedProcess[str], before: dict[str, tuple], place: str
    ) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(
            any(line.startswith(f"refused {place}: ") for line in result.stderr.splitlines()),
            result.stderr,
        )
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.snapshot(), before)

    def test_something_at_the_place_of_a_skill_link_that_does_not_lead_to_the_skill_is_refused(self):
        place = self.home / ".agents" / "skills" / "alpha"
        elsewhere = self.scratch / "elsewhere"
        elsewhere.mkdir()
        cases = {
            "a directory": lambda: place.mkdir(),
            "a file": lambda: place.write_text("kept\n"),
            "a link elsewhere": lambda: place.symlink_to(elsewhere),
            "a link to nothing": lambda: place.symlink_to(self.scratch / "missing"),
        }
        for name, make in cases.items():
            with self.subTest(case=name):
                shutil.rmtree(self.home / ".agents", ignore_errors=True)
                place.parent.mkdir(parents=True)
                make()
                before = self.snapshot()
                self.assertRefusedAndUnchanged(self.install(), before, "~/.agents/skills/alpha")

    def test_a_file_or_a_link_to_nothing_on_the_way_to_a_link_is_refused(self):
        # As a folder on a volume that is not mounted would be.
        unmounted = self.scratch / "unmounted"
        cases = {
            "~/.agents": lambda place: place.write_text("kept\n"),
            "~/.agents/skills": lambda place: place.symlink_to(unmounted),
            "~/.codex": lambda place: place.symlink_to(unmounted),
            "~/.config/Code": lambda place: place.symlink_to(unmounted),
        }
        for shown, make in cases.items():
            with self.subTest(place=shown):
                self.clear(".agents", ".codex", ".config")
                place = self.home / shown.removeprefix("~/")
                place.parent.mkdir(parents=True, exist_ok=True)
                make(place)
                before = self.snapshot()
                self.assertRefusedAndUnchanged(self.install(), before, shown)

    def test_a_directory_of_links_that_leads_into_a_clone_is_refused(self):
        # As the skills of one plugin, shown to Codex by a link to their folder, would be. The case
        # of the skills comes last, since a link that it made would change the clone.
        cases = {
            "~/.codex": self.holding / "instructions",
            "~/.config/Code/User/prompts": self.holding / "instructions",
            "~/.agents/skills": self.holding / "plugins" / "first" / "skills",
        }
        for shown, target in cases.items():
            with self.subTest(place=shown):
                self.clear(".agents", ".codex", ".config")
                place = self.home / shown.removeprefix("~/")
                place.parent.mkdir(parents=True, exist_ok=True)
                place.symlink_to(target)
                before = self.snapshot()
                result = self.install(str(self.holding), str(self.other))
                self.assertRefusedAndUnchanged(result, before, shown)

    def test_skills_of_the_user_that_are_the_skills_of_claude_code_are_refused(self):
        agents = self.home / ".agents" / "skills"
        claude = self.home / ".claude" / "skills"
        config = self.scratch / "config"
        cases = {
            "~/.agents/skills a link": (claude, agents, {}),
            "~/.claude/skills a link": (agents, claude, {}),
            "CLAUDE_CONFIG_DIR set": (config / "skills", agents, {"CLAUDE_CONFIG_DIR": str(config)}),
        }
        for name, (real, link, environment) in cases.items():
            with self.subTest(case=name):
                self.clear(".agents", ".claude")
                shutil.rmtree(config, ignore_errors=True)
                real.mkdir(parents=True)
                link.parent.mkdir(parents=True, exist_ok=True)
                link.symlink_to(real)
                before = self.snapshot()
                result = self.install(**environment)
                self.assertRefusedAndUnchanged(result, before, "~/.agents/skills")

    def test_a_skill_that_the_skills_of_codex_hold_is_refused(self):
        (self.home / ".codex" / "skills" / "beta").mkdir(parents=True)
        before = self.snapshot()
        result = self.install()
        self.assertRefusedAndUnchanged(result, before, "~/.codex/skills/beta")
        self.assertIn("Codex would list", result.stderr)

    def test_with_codex_home_set_its_skills_are_read_and_not_those_of_dot_codex(self):
        codex_home = self.scratch / "codex"
        (codex_home / "skills" / "alpha").mkdir(parents=True)
        # Under the default place, which CODEX_HOME replaces: not read.
        (self.home / ".codex" / "skills" / "beta").mkdir(parents=True)
        before = self.snapshot()
        result = self.install(CODEX_HOME=str(codex_home))
        self.assertRefusedAndUnchanged(result, before, str(codex_home / "skills" / "alpha"))
        self.assertNotIn("beta", result.stderr)

    def test_a_codex_home_or_a_claude_config_dir_that_is_not_absolute_is_refused(self):
        for variable in ("CODEX_HOME", "CLAUDE_CONFIG_DIR"):
            with self.subTest(variable=variable):
                before = self.snapshot()
                result = self.install(cwd=self.scratch, **{variable: "relative"})
                self.assertRefusedAndUnchanged(result, before, "relative")
                self.assertFalse((self.scratch / "relative").exists())

    def test_a_home_that_is_empty_or_not_absolute_is_refused(self):
        for value in ("", "relative"):
            with self.subTest(value=value):
                before = self.snapshot()
                result = self.install(cwd=self.scratch, HOME=value)
                self.assertRefusedAndUnchanged(result, before, value)
                self.assertIn("HOME is not an absolute path", result.stderr)
                self.assertFalse((self.scratch / "relative").exists())

    def test_a_skill_name_that_two_plugins_hold_is_refused(self):
        cases = {
            "in one clone": (self.holding / "plugins" / "second", ()),
            "in two clones": (self.other / "plugins" / "third", (str(self.holding), str(self.other))),
        }
        for name, (plugin, clones) in cases.items():
            with self.subTest(case=name):
                copy = plugin / "skills" / "alpha"
                shutil.copytree(self.skill(self.holding, "first", "alpha"), copy)
                before = self.snapshot()
                result = self.install(*clones)
                self.assertRefusedAndUnchanged(result, before, "~/.agents/skills/alpha")
                self.assertIn("two plugins hold a skill of this name", result.stderr)
                shutil.rmtree(copy)

    def test_something_at_the_place_of_an_instruction_link_that_does_not_lead_to_the_rules_is_refused(
        self,
    ):
        elsewhere = self.scratch / "elsewhere.md"
        elsewhere.write_text("Instructions of the user's own.\n")
        places = ("~/.codex/AGENTS.md", "~/.config/Code/User/prompts/shift-left.instructions.md")
        cases = {
            "a file": lambda place: place.write_text("Instructions of the user's own.\n"),
            "a link elsewhere": lambda place: place.symlink_to(elsewhere),
        }
        for shown in places:
            for name, make in cases.items():
                with self.subTest(place=shown, case=name):
                    for parent in (".codex", ".config"):
                        shutil.rmtree(self.home / parent, ignore_errors=True)
                    place = self.home / shown.removeprefix("~/")
                    place.parent.mkdir(parents=True)
                    make(place)
                    before = self.snapshot()
                    self.assertRefusedAndUnchanged(self.install(), before, shown)

    def test_a_clone_in_which_no_marketplace_file_can_be_read_is_refused(self):
        (self.home / "src" / "empty").mkdir()
        unreadable = {
            "not JSON": "{not json\n",
            "no plugin": json.dumps({"name": "none", "plugins": []}),
            "a name with a line break": json.dumps(
                {"name": "two\nlines", "plugins": [{"name": "one"}]}
            ),
        }
        for name, text in unreadable.items():
            manifest = self.home / "src" / name / ".claude-plugin" / "marketplace.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(text)
        cases = {
            "no marketplace file": ("home/src/empty", "home/src/empty"),
            "no such directory": (str(self.home / "src" / "missing"), "~/src/missing"),
        } | {
            f"a file with {name}": (str(self.home / "src" / name), f"~/src/{name}")
            for name in unreadable
        }
        for name, (argument, shown) in cases.items():
            with self.subTest(case=name):
                before = self.snapshot()
                result = self.install(str(self.holding), argument, cwd=self.scratch)
                self.assertRefusedAndUnchanged(result, before, shown)

    def test_a_clone_whose_marketplace_has_the_name_of_another_clones_is_refused(self):
        # Without skills, so that no refusal of a skill name stops the run first.
        first = write_clone(self.home / "src" / "a", "bare", {"hooks": []})
        second = write_clone(self.home / "src" / "b", "bare", {"hooks": []})
        before = self.snapshot()
        result = self.install(str(first), str(second))
        self.assertRefusedAndUnchanged(result, before, "~/src/b")

    def test_a_holding_clone_without_a_file_of_shared_rules_is_refused(self):
        self.rules.unlink()
        for name, make in (("no file", lambda: None), ("a directory", self.rules.mkdir)):
            with self.subTest(case=name):
                make()
                before = self.snapshot()
                result = self.install()
                self.assertRefusedAndUnchanged(result, before, "~/src/holding/instructions/global.md")

    @unittest.skipIf(os.geteuid() == 0, "root reads a file whatever its mode")
    def test_shared_rules_that_cannot_be_read_are_refused(self):
        before = self.snapshot()
        self.rules.chmod(0)
        try:
            result = self.install()
        finally:
            self.rules.chmod(0o644)
        self.assertRefusedAndUnchanged(result, before, "~/src/holding/instructions/global.md")

    def test_without_python3_on_path_the_run_says_so_and_changes_nothing(self):
        # The commands that the script runs, but python3.
        commands = self.scratch / "commands"
        commands.mkdir()
        for command in ("bash", "dirname", "mkdir", "ln"):
            (commands / command).symlink_to(shutil.which(command))
        before = self.snapshot()
        result = self.install(PATH=str(commands))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "install.sh needs python3 on PATH\n")
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.calls(), [])
        self.assertEqual(self.snapshot(), before)

    def test_a_bash_older_than_4_4_is_refused_before_anything_is_read(self):
        # BASH_VERSINFO cannot be set, and one bash runs the tests: the copy that runs reads the
        # version from an array of the same form that it is given first.
        script = (ROOT / "install.sh").read_text()
        self.assertIn("BASH_VERSINFO", script)
        script = script.replace("BASH_VERSINFO", "VERSIONS")
        for version in ("3.2", "4.0", "4.3", "4.4", "5.0", "5.3"):
            with self.subTest(version=version):
                major, minor = version.split(".")
                pretended = script.replace("\n", f"\nVERSIONS=({major} {minor} 0)\n", 1)
                (self.holding / "install.sh").write_text(pretended)
                self.clear(".agents", ".codex", ".config", ".claude")
                self.log.write_text("")
                before = self.snapshot()
                result = self.install()
                if version in ("3.2", "4.0", "4.3"):
                    self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                    self.assertEqual(result.stderr, "install.sh needs bash 4.4 or later\n")
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(self.calls(), [])
                    self.assertEqual(self.snapshot(), before)
                else:
                    self.assertPasses(result)

    def test_the_script_run_through_a_link_from_another_directory_is_refused(self):
        # The script takes the directory of the link for the clone that holds it, and finds no
        # shared rules there.
        commands = self.home / "bin"
        commands.mkdir()
        (commands / "install.sh").symlink_to(self.holding / "install.sh")
        before = self.snapshot()
        result = self.install(str(self.holding), holding=commands)
        self.assertRefusedAndUnchanged(result, before, "~/bin/instructions/global.md")


class Cli(InstallCase):
    def test_the_cli_is_c_else_claude_code_execpath_else_claude_on_path(self):
        other_log = self.scratch / "other.log"
        other = self.stand_in_at(self.scratch / "other" / "claude", other_log)
        del self.environment["C"]
        cases = (
            ("C", {"C": str(self.stand_in), "CLAUDE_CODE_EXECPATH": str(other)}, self.log),
            ("CLAUDE_CODE_EXECPATH", {"CLAUDE_CODE_EXECPATH": str(other)}, other_log),
            ("PATH", {"PATH": f"{other.parent}{os.pathsep}{os.environ['PATH']}"}, other_log),
        )
        for name, environment, used in cases:
            with self.subTest(cli=name):
                for log in (self.log, other_log):
                    log.write_text("")
                self.assertPasses(self.install(**environment))
                unused = other_log if used == self.log else self.log
                self.assertEqual(self.calls(used)[0], "plugin list --json")
                self.assertEqual(self.calls(unused), [])

    def test_without_a_cli_its_steps_are_skipped_and_the_rest_runs(self):
        result = self.install(C=str(self.scratch / "missing"))
        self.assertPasses(result)
        lines = result.stdout.splitlines()
        self.assertIn("  skipped: no Claude Code CLI; set C to its path", lines)
        self.assertIn("  ~/.claude/CLAUDE.md: add this line to import the shared rules:", lines)
        self.assertIn("== VS Code", lines)
        self.assertLinked(
            self.home / ".agents" / "skills" / "alpha", self.skill(self.holding, "first", "alpha")
        )
        self.assertEqual(self.calls(), [])

    def test_a_failing_step_of_the_cli_ends_the_run_with_status_1_and_nothing_runs_after_it(self):
        for verb in ("list", "marketplace", "install", "update"):
            with self.subTest(verb=verb):
                self.log.write_text("")
                result = self.install(STAND_IN_FAILS=verb)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                verbs = [call.split()[1] for call in self.calls()]
                self.assertEqual(verbs[-1], verb)
                self.assertEqual(verbs.count(verb), 1)
                self.assertNotIn("== VS Code", result.stdout.splitlines())

    def test_a_list_that_the_script_cannot_read_ends_the_run_with_status_1(self):
        for name, listed in (
            ("an entry without a scope", '[{"id": "first@holding"}]'),
            ("no JSON", "oops"),
        ):
            with self.subTest(list=name):
                self.log.write_text("")
                result = self.install(STAND_IN_LIST=listed)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertEqual(self.calls(), ["plugin list --json"])
                self.assertNotIn("== VS Code", result.stdout.splitlines())


@unittest.skipUnless(CLI, "no Claude Code CLI: neither CLAUDE_CODE_EXECPATH nor claude on PATH")
class RealCli(unittest.TestCase):
    """The part of Claude Code, with the real CLI under a scratch configuration, on a copy of
    this repository."""

    def setUp(self):
        scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.copy = scratch / "home" / "src" / "shift-left"
        for part in (".claude-plugin", "plugins", "instructions"):
            shutil.copytree(ROOT / part, self.copy / part, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(ROOT / "install.sh", self.copy / "install.sh")
        self.marketplace = json.loads((self.copy / ".claude-plugin" / "marketplace.json").read_text())
        self.environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(scratch / "home"),
            "C": CLI,
            "CLAUDE_CONFIG_DIR": str(scratch / "configuration"),
            # Plugin commands need no network: keep the CLI from reaching out for anything else.
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }

    def cli(self, *arguments: str) -> str:
        done = subprocess.run(
            [CLI, *arguments],
            env=self.environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
        return done.stdout

    def test_each_plugin_is_installed_for_the_user_and_one_disabled_stays_disabled_at_a_second_run(
        self,
    ):
        name = self.marketplace["name"]
        plugins = [plugin["name"] for plugin in self.marketplace["plugins"]]
        disabled = plugins[0]
        for run in (1, 2):
            result = subprocess.run(
                [str(self.copy / "install.sh")],
                env=self.environment,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=600,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            if run == 1:
                self.cli("plugin", "disable", f"{disabled}@{name}")
        listed = {plugin["id"]: plugin for plugin in json.loads(self.cli("plugin", "list", "--json"))}
        for plugin in plugins:
            with self.subTest(plugin=plugin):
                entry = listed[f"{plugin}@{name}"]
                self.assertEqual(entry["scope"], "user")
                self.assertEqual(entry["readFromFolder"], str(self.copy / "plugins" / plugin))
                self.assertEqual(entry["enabled"], plugin != disabled)


if __name__ == "__main__":
    unittest.main()
