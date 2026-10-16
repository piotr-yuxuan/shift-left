"""The shared rules, `instructions/global.md`, checked against what reads them and what they name.

The expectations come from the decisions of 2026-10-16 that made the file shared by every client,
not from the file. VS Code reads a file of instructions with a front matter that says where it
applies: the file starts with the three lines `---`, `applyTo: "**"` and `---`. The file names a
skill or an agent of a plugin as `<plugin>:<name>` between backticks, and each name is one of this
repository: a skill, `plugins/<plugin>/skills/<name>/SKILL.md`, or an agent,
`plugins/<plugin>/agents/<name>.md`, so that a rename leaves no name that leads nowhere. Among them
are `workflow:plans` and `learning:learning-mode`, which the file is to name. The file has at most
80 lines; of those two skills, the first has at most 120 lines and the second at most 170.

Those decisions also put rules in the file, and a cut made to keep it within 80 lines must drop
none unseen. Each of these is found by a phrase of it, in the text read with every run of blanks
as one space, since a phrase may wrap: the precedence of a repository's instructions; the skills
and the agent of `principles` and the hook of Claude Code; the rules on tests, on commits and on
writing; the invariants; `C` and the scratch configurations; that only the user invokes
`learning:learning-mode`. The rule on the primary checkout binds only a repository whose
instructions name `workflow:plans`: the list item that holds `primary checkout` begins with those
words.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "instructions" / "global.md").read_text(encoding="utf-8")
NAMED = re.compile(r"`([a-z0-9-]+):([a-z0-9-]+)`")
# A list item: a line that begins with `- `, and the lines indented by two spaces that follow it.
ITEM = re.compile(r"^- .*(?:\n  .*)*", re.MULTILINE)


class SharedRules(unittest.TestCase):
    def test_the_file_starts_with_the_front_matter_that_vs_code_reads(self):
        self.assertEqual(TEXT.split("\n")[:3], ["---", 'applyTo: "**"', "---"])

    def test_each_name_of_a_plugin_and_a_component_is_a_skill_or_an_agent_of_this_repository(self):
        names = set(NAMED.findall(TEXT))
        self.assertLessEqual({("workflow", "plans"), ("learning", "learning-mode")}, names)
        for plugin, name in sorted(names):
            with self.subTest(name=f"{plugin}:{name}"):
                directory = ROOT / "plugins" / plugin
                self.assertTrue(
                    (directory / "skills" / name / "SKILL.md").is_file()
                    or (directory / "agents" / f"{name}.md").is_file(),
                    "no skill and no agent of that name",
                )

    def test_the_file_has_at_most_80_lines(self):
        self.assertLessEqual(len(TEXT.splitlines()), 80)

    def test_each_of_the_two_skills_that_the_file_is_to_name_keeps_within_its_length(self):
        for plugin, name, limit in (("workflow", "plans", 120), ("learning", "learning-mode", 170)):
            with self.subTest(name=f"{plugin}:{name}"):
                skill = ROOT / "plugins" / plugin / "skills" / name / "SKILL.md"
                self.assertLessEqual(len(skill.read_text(encoding="utf-8").splitlines()), limit)

    def test_the_file_holds_a_phrase_of_each_rule_that_it_is_to_hold(self):
        text = " ".join(TEXT.split())
        phrases = (
            "AGENTS.local.md",
            "`principles:programming-principles`",
            "`principles:karpathy-guidelines`",
            "documented contract",
            "tests@example.invalid",
            "quality-ratchet",
            "`principles:principles-reviewer`",
            "50 characters",
            "72 characters",
            "Co-Authored-By",
            "U+2013",
            "Headings in sentence case",
            "Never push",
            "~/.config/Code",
            "destructive",
            "only clarifying questions",
            "practice questions",
            "assumptions",
            "CLAUDE_CODE_EXECPATH",
            "at the start of each command that uses it",
            "CODEX_HOME",
            "`learning:learning-mode` is for the user alone to invoke",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(phrase in text, "not found")

    def test_the_rule_on_the_primary_checkout_binds_only_a_repository_that_names_workflow_plans(self):
        scope = "- In a repository whose instructions name `workflow:plans`"
        items = [" ".join(item.split()) for item in ITEM.findall(TEXT)]
        holders = [item for item in items if "primary checkout" in item]
        self.assertTrue(holders, "no list item holds `primary checkout`")
        for item in holders:
            with self.subTest(item=item):
                self.assertTrue(item.startswith(scope))


if __name__ == "__main__":
    unittest.main()
