"""The skills of the plugins, checked against the Agent Skills specification.

The expectations come from the specification and not from the files: agentskills.io/specification,
"SKILL.md format" and under it "Frontmatter", as it was read on 2026-10-11. The front matter of a
`SKILL.md` holds `name` and `description` and no key outside six. `name` is the name of the
directory of the skill: 1 to 64 characters of `a-z`, `0-9` and `-`, with no hyphen at either end
and no `--`. `description` has 1 to 1024 characters, `compatibility` at most 500.

Every directory `skills/<name>/` of every plugin is taken as a skill, and its `SKILL.md` is read:
a directory there that holds none ends the tests in error.

The front matter is YAML, and the standard library reads none. So these tests read only lines of
the form `<key>: <value>`, with one of the five keys whose value is a string, said once, and a
value that a reader of lines and a YAML reader give as the same string: it starts with an ASCII
letter; holds no colon followed by a space, no colon at its end and no `#` after a space; has
printable characters only and no space at either end; and is not a word that YAML reads as a
boolean or as null. Anything else fails as "outside the subset this test reads", which does not
say that it is invalid: a quoted, a nested or a multi-line value is outside, and so is a name that
starts with a digit. The sixth key, `metadata`, is outside in every form: the specification makes
it a map from text to text, which no line of this form holds, and a line `metadata: <value>` would
give a string where a map is asked.

One line outside the specification is read: `disable-model-invocation: true`. Claude Code and
VS Code then leave the skill out of the model's context, so that only the user invokes it
(code.claude.com/docs/en/skills, "Restrict Claude's skill access"; VS Code's page on agent
skills). Codex reads the same intent from `allow_implicit_invocation: false` under `policy` in
the skill's `agents/openai.yaml`, which a test checks beside the line.
"""

import re
import unittest
from pathlib import Path

PLUGINS = Path(__file__).resolve().parents[2] / "plugins"
SKILLS = sorted(path for path in PLUGINS.glob("*/skills/*") if path.is_dir())

KEYS = {"name", "description", "license", "compatibility", "allowed-tools"}
PLAIN_VALUE = re.compile(r"[A-Za-z](?:(?!: | #).)*(?<![ :])")
YAML_WORDS = {"true", "false", "yes", "no", "on", "off", "y", "n", "null"}
SUBSET = "outside the subset this test reads"
USER_INVOKED = "disable-model-invocation: true"


class Skills(unittest.TestCase):
    def front_matter(self, skill: Path) -> dict[str, str]:
        """The keys and values of the front matter; fails the test on what is outside the subset."""
        # No translation of line ends: a carriage return must stay, to be seen as not printable.
        lines = (skill / "SKILL.md").read_text(encoding="utf-8", newline="").split("\n")
        if lines[0] != "---" or "---" not in lines[1:]:
            self.fail(f"{SUBSET}: no first line `---` that a later line `---` closes")
        fields: dict[str, str] = {}
        for line in lines[1 : lines.index("---", 1)]:
            if line == USER_INVOKED:
                continue
            key, _, value = line.partition(": ")
            plain = PLAIN_VALUE.fullmatch(value) and value.isprintable()
            if key not in KEYS or key in fields or not plain or value.lower() in YAML_WORDS:
                self.fail(f"{SUBSET}: the line {line!r}")
            fields[key] = value
        return fields

    def test_the_name_of_a_skill_is_its_directory_and_has_the_form_that_the_specification_asks(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                name = self.front_matter(skill).get("name")
                self.assertEqual(name, skill.name)
                self.assertRegex(name, r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")
                self.assertLessEqual(len(name), 64)

    def test_the_description_of_a_skill_is_there_and_has_at_most_1024_characters(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                fields = self.front_matter(skill)
                self.assertIn("description", fields)
                self.assertLessEqual(len(fields["description"]), 1024)

    def test_the_compatibility_of_a_skill_has_at_most_500_characters(self):
        for skill in SKILLS:
            with self.subTest(skill=skill.name):
                self.assertLessEqual(len(self.front_matter(skill).get("compatibility", "")), 500)

    def test_a_skill_that_only_the_user_invokes_says_so_to_codex_too(self):
        for skill in SKILLS:
            lines = (skill / "SKILL.md").read_text(encoding="utf-8").split("\n")
            if USER_INVOKED in lines[1 : lines.index("---", 1)]:
                with self.subTest(skill=skill.name):
                    policy = (skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
                    self.assertIn("allow_implicit_invocation: false", policy)


if __name__ == "__main__":
    unittest.main()
