"""The manifests of the plugins, checked against the Agent Plugins standard and the rules kept here.

The expectations come from the standard and from those rules, not from the files.

The standard is Agent Plugins 1.0.0, as it was read on 2026-10-11: agent-plugins.org/specification,
4.1 "General requirements" and 5.2 "Manifest object", and the schema of the manifest,
agent-plugins.org/schemas/1.0.0/plugin.schema.json. A plugin has a `plugin.json` at its root. The
schema of that file is closed. `$schema` is the address of the schema, and `name` has 1 to 64
characters of `a-z`, `0-9`, `.` and `-`, starts and ends with a letter or a digit, and holds
neither `--` nor `..`. Every other field that these manifests use is a string.

The rules of this repository:

- The directories under `plugins/` are the entries of the marketplace file, each under its name.
- A plugin has a root manifest exactly when it has a `skills/` directory: a skill is the one
  component of the standard that this repository ships.
- A root manifest holds `$schema`, `name`, `version`, `description`, `license` and `repository`.
- `.claude-plugin/plugin.json` stays beside it for Claude Code, which reads no other. The two agree
  on the name, which is the name of the directory, and on the licence. The root description is the
  other one or its beginning: it stops before what a client of the standard does not get.
"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGINS = sorted(path for path in (ROOT / "plugins").iterdir() if path.is_dir())
WITH_ROOT_MANIFEST = [plugin for plugin in PLUGINS if (plugin / "plugin.json").is_file()]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


ENTRIES = read_json(ROOT / ".claude-plugin" / "marketplace.json")["plugins"]


class Manifests(unittest.TestCase):
    def test_the_directories_of_the_plugins_are_the_entries_of_the_marketplace_file(self):
        self.assertCountEqual(
            [(entry["name"], entry["source"]) for entry in ENTRIES],
            [(plugin.name, f"./plugins/{plugin.name}") for plugin in PLUGINS],
        )

    def test_a_plugin_has_a_root_manifest_exactly_when_it_has_skills(self):
        for plugin in PLUGINS:
            with self.subTest(plugin=plugin.name):
                self.assertEqual(
                    (plugin / "plugin.json").is_file(),
                    (plugin / "skills").is_dir(),
                    "a root plugin.json goes with a skills/ directory, and with nothing else",
                )

    def test_a_root_manifest_holds_six_fields_in_the_form_that_the_standard_asks(self):
        for plugin in WITH_ROOT_MANIFEST:
            with self.subTest(plugin=plugin.name):
                manifest = read_json(plugin / "plugin.json")
                self.assertEqual(
                    set(manifest),
                    {"$schema", "name", "version", "description", "license", "repository"},
                )
                self.assertEqual(
                    manifest["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
                )
                self.assertRegex(
                    manifest["name"], r"\A(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\Z"
                )
                self.assertLessEqual(len(manifest["name"]), 64)
                for field in ("version", "description", "license", "repository"):
                    self.assertIsInstance(manifest[field], str, field)

    def test_the_two_manifests_of_a_plugin_agree(self):
        for plugin in WITH_ROOT_MANIFEST:
            with self.subTest(plugin=plugin.name):
                root = read_json(plugin / "plugin.json")
                claude_code = read_json(plugin / ".claude-plugin" / "plugin.json")
                self.assertEqual((root["name"], claude_code["name"]), (plugin.name, plugin.name))
                self.assertEqual(root["license"], claude_code["license"])
                self.assertTrue(
                    claude_code["description"].startswith(root["description"]),
                    f"{root['description']!r} is not the beginning of {claude_code['description']!r}",
                )


if __name__ == "__main__":
    unittest.main()
