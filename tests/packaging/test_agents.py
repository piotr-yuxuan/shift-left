"""The front matter of the reviewer agent of `principles`, checked against what reads it.

The expectations come from the decisions of 2026-10-16 that gave the agent its requirements lens,
not from the file. A caller learns what the agent does, that lens included, from its description,
which Claude Code reads from the front matter of `agents/principles-reviewer.md`. The front matter
is the lines between a first line `---` and the next line `---`. It holds five keys, each once:
`name`, the name of the file; `description`, `tools` and `model`, each on one line; and `skills`, a
list of at least one name, each on a line `  - <name>` below the line `skills:`. Every value is in
the subset that `test_skills.py` reads, whose rule is imported from it: a value that a reader of
lines and a YAML reader give as the same string, so with no colon followed by a space and no `#`
after a space. Anything else fails as outside that subset, which does not say that it is invalid.

Nothing else checks this. On 2026-10-16, `plugin validate` of Claude Code 2.1.295 passed a copy of
this agent whose front matter does not close, from which `plugin details` then read no description,
and a copy whose description holds a second colon followed by a space, which a YAML reader refuses.
"""

import unittest
from pathlib import Path

from tests.packaging.test_skills import PLAIN_VALUE, SUBSET, YAML_WORDS

ROOT = Path(__file__).resolve().parents[2]
AGENT = ROOT / "plugins" / "principles" / "agents" / "principles-reviewer.md"
KEYS = {"name", "description", "tools", "model", "skills"}


class ReviewerAgent(unittest.TestCase):
    def front_matter(self) -> dict[str, str | list[str]]:
        """Each key with its value, or with the list below it; fails the test outside the subset."""
        # No translation of line ends: a carriage return must stay, to be seen as not printable.
        lines = AGENT.read_text(encoding="utf-8", newline="").split("\n")
        if lines[0] != "---" or "---" not in lines[1:]:
            self.fail(f"{SUBSET}: no first line `---` that a later line `---` closes")
        fields: dict[str, str | list[str]] = {}
        listing: list[str] | None = None
        for line in lines[1 : lines.index("---", 1)]:
            key, _, value = line.partition(": ")
            if listing is not None and line.startswith("  - "):
                value = line.removeprefix("  - ")
                listing.append(value)
            elif line.endswith(":") and line[:-1] in KEYS - fields.keys():
                listing = fields[line[:-1]] = []
                continue
            elif key in KEYS - fields.keys():
                fields[key], listing = value, None
            else:
                self.fail(f"{SUBSET}: the line {line!r}")
            plain = PLAIN_VALUE.fullmatch(value) and value.isprintable()
            if not plain or value.lower() in YAML_WORDS:
                self.fail(f"{SUBSET}: the line {line!r}")
        return fields

    def test_the_front_matter_holds_the_five_keys(self):
        self.assertEqual(set(self.front_matter()), KEYS)

    def test_the_name_is_the_name_of_the_file(self):
        self.assertEqual(self.front_matter().get("name"), AGENT.stem)

    def test_the_description_the_tools_and_the_model_are_each_one_line(self):
        fields = self.front_matter()
        for key in ("description", "tools", "model"):
            with self.subTest(key=key):
                self.assertIsInstance(fields.get(key), str)

    def test_skills_is_a_list_of_at_least_one_name(self):
        skills = self.front_matter().get("skills")
        self.assertIsInstance(skills, list)
        self.assertGreater(len(skills), 0)


if __name__ == "__main__":
    unittest.main()
