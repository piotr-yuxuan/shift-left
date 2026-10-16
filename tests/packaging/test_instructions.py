"""The shared rules, `instructions/global.md`, checked against what reads them and what they name.

The expectations come from the decisions of 2026-10-16 that made the file shared by every client,
not from the file. VS Code reads a file of instructions with a front matter that says where it
applies: the file starts with the three lines `---`, `applyTo: "**"` and `---`. The file names a
skill or an agent of a plugin as `<plugin>:<name>` between backticks, and each name is one of this
repository: a skill, `plugins/<plugin>/skills/<name>/SKILL.md`, or an agent,
`plugins/<plugin>/agents/<name>.md`, so that a rename leaves no name that leads nowhere. Among them
are `workflow:plans` and `learning:learning-mode`, which the file is to name.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEXT = (ROOT / "instructions" / "global.md").read_text(encoding="utf-8")
NAMED = re.compile(r"`([a-z0-9-]+):([a-z0-9-]+)`")


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


if __name__ == "__main__":
    unittest.main()
