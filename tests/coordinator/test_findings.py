"""The findings script of the `instrument` skill, through its command line and its decisions.

The expectations come from what the script and the skill promise, not from the code: a finding of
fourteen fields; a schema file that is the one authority on fields, values and roles; three exit
statuses, each with its streams; a write that is whole or not at all, only where git ignores the
file, under a lock on its directory.

The tests need `git` and `python3` on PATH.
"""

import fcntl
import functools
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

SKILL = Path(__file__).resolve().parents[2] / "plugins" / "coordinator" / "skills" / "instrument"
SCRIPT = SKILL / "findings.py"
SCHEMA = json.loads((SKILL / "finding.schema.json").read_text(encoding="utf-8"))
PROPERTIES = SCHEMA["properties"]

# The fields, the values and the roles as the skill states them, not as read from the schema file.
REVIEWER_FIELDS = [
    "id",
    "file",
    "line",
    "severity",
    "summary",
    "failure_scenario",
    "fix",
    "lens",
    "subject",
]
FIELDS = REVIEWER_FIELDS + [
    "round_found",
    "origin",
    "disclosed_before_review",
    "disposition",
    "carry_over_of",
]
SEVERITIES = ["blocking", "major", "minor"]
SUBJECTS = ["code", "policy", "carry-over", "notes"]
ORIGINS = ["first-iteration", "fix-round", "coordinator", "plan-or-brief"]
DISPOSITIONS = ["open", "fixed", "declined", "needs-user", "ruled", "deferred"]
ROLES = {
    "reviewer": {"adds": REVIEWER_FIELDS},
    "fixer": {"sets": {"disposition": {"from": ["open"], "to": ["fixed", "declined"]}}},
    "coordinator": {
        "sets": {"origin": {}, "disclosed_before_review": {}, "carry_over_of": {}, "disposition": {}}
    },
}

# Stands for private text: no stream of the script may show it.
MARKER = "PRIVATE-MARKER"


def loaded(script: Path):
    """The script as a module, for its decision functions."""
    spec = importlib.util.spec_from_file_location(script.stem, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


findings = loaded(SCRIPT)


def reported(identifier: str, **changes) -> dict:
    """A finding as a reviewer gives it, with the lens that its id names."""
    finding = {
        "id": identifier,
        "file": "lib/parse.py",
        "line": 7,
        "severity": "major",
        "summary": "The total is wrong",
        "failure_scenario": "The list is empty",
        "fix": "Return zero",
        "lens": identifier.split("-", 1)[1].rpartition("-")[0],
        "subject": "code",
    }
    return finding | changes


def stored(identifier: str, **changes) -> dict:
    """A finding as the file holds it once added, with the round that its id names."""
    completed = {
        "round_found": int(identifier[1 : identifier.index("-")]),
        "origin": None,
        "disclosed_before_review": None,
        "disposition": "open",
        "carry_over_of": None,
    }
    return reported(identifier) | completed | changes


def update(identifier: str, **fields) -> dict:
    """One update of an answer of a fixer or of the coordinator."""
    return {"id": identifier} | fields


class CommandLine(unittest.TestCase):
    """A scratch repository that ignores its directory `kept`, and an environment built from nothing."""

    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        home = self.scratch / "home"
        home.mkdir()
        # No GIT_* variable and no configuration of the caller reaches git or the script.
        self.environment = {
            "PATH": os.environ["PATH"],
            "HOME": str(home),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
        }
        self.repository = self.scratch / "repository"
        self.git("init", "--quiet", str(self.repository))
        (self.repository / ".gitignore").write_text("/kept/\n")
        self.file = self.repository / "kept" / "plan.json"

    def git(self, *arguments: str) -> None:
        subprocess.run(["git", *arguments], env=self.environment, check=True, capture_output=True)

    def script(
        self,
        *arguments: str,
        answer=None,
        script: Path = SCRIPT,
        cwd: Path | None = None,
        **environment: str,
    ):
        """Run the script, or a copy of it, with `answer` on standard input."""
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            input=answer if isinstance(answer, str) else json.dumps(answer),
            cwd=cwd,
            env=self.environment | environment,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def add(self, *given, round_found=1, lens="design", file: Path | None = None, **options):
        arguments = ["--file", str(file or self.file), "--round", str(round_found), "--lens", lens]
        return self.script("add", *arguments, answer={"findings": list(given)}, **options)

    def set(self, role: str, *updates: dict, file: Path | None = None, **options):
        arguments = ["--file", str(file or self.file), "--role", role]
        return self.script("set", *arguments, answer={"updates": list(updates)}, **options)

    def hold(self, *held: dict, file: Path | None = None) -> bytes:
        """Write a findings file as a fixture, without the script, and return its bytes."""
        file = file or self.file
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({"findings": list(held)}), encoding="utf-8")
        return file.read_bytes()

    def held(self, file: Path | None = None) -> list[dict]:
        return json.loads((file or self.file).read_text(encoding="utf-8"))["findings"]

    def copy(self, change) -> Path:
        """The script of a copy of the skill whose schema file `change` has edited.

        The copy is alone under a path with a space and parentheses, as an installed plugin may be.
        """
        target = Path(tempfile.mkdtemp(prefix="a copy (1) ", dir=self.scratch)) / "instrument"
        shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns("__pycache__"))
        schema = json.loads((target / "finding.schema.json").read_text(encoding="utf-8"))
        change(schema)
        (target / "finding.schema.json").write_text(json.dumps(schema), encoding="utf-8")
        return target / "findings.py"

    def assertDone(self, result) -> dict:
        """Status 0: the result on standard output."""
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def assertRejected(self, result) -> list[dict]:
        """Status 1: errors on standard output, each a path and a rule, and no other text."""
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")
        document = json.loads(result.stdout)
        self.assertEqual(list(document), ["errors"])
        self.assertTrue(document["errors"])
        for error in document["errors"]:
            self.assertEqual(sorted(error), ["path", "rule"])
        self.assertNotIn(MARKER, result.stdout)
        return document["errors"]

    def assertFailed(self, result) -> None:
        """Status 2: nothing on standard output, and one line on standard error."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertNotIn(MARKER, result.stderr)

    def assertWrongCall(self, result) -> None:
        """Status 2 and nothing on standard output; the usage may come before the line."""
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(MARKER, result.stderr)


class Subset(unittest.TestCase):
    """The checks of the keywords, with plain values."""

    def errors(self, value, schema: dict) -> list[dict]:
        return findings.validate(value, schema, "value")

    def test_each_type_name_accepts_its_own_values_and_no_other(self):
        samples = {
            "string": "text",
            "integer": 3,
            "boolean": True,
            "null": None,
            "object": {},
            "array": [],
        }
        for name in samples:
            for other, value in samples.items():
                with self.subTest(type=name, value=other):
                    expected = [] if name == other else [{"path": "value", "rule": "type"}]
                    self.assertEqual(self.errors(value, {"type": name}), expected)

    def test_an_integer_is_a_whole_number_and_not_a_boolean(self):
        for value in (True, False, 1.5, 1.0, float("nan"), "1"):
            with self.subTest(value=value):
                self.assertEqual(
                    self.errors(value, {"type": "integer"}), [{"path": "value", "rule": "type"}]
                )
        for value in (0, -4, 10**20):
            with self.subTest(value=value):
                self.assertEqual(self.errors(value, {"type": "integer"}), [])

    def test_a_number_is_not_a_boolean(self):
        for value in (0, 1):
            with self.subTest(value=value):
                self.assertEqual(
                    self.errors(value, {"type": "boolean"}), [{"path": "value", "rule": "type"}]
                )

    def test_a_list_of_type_names_accepts_any_of_them(self):
        schema = {"type": ["integer", "null"]}
        self.assertEqual(self.errors(4, schema), [])
        self.assertEqual(self.errors(None, schema), [])
        self.assertEqual(self.errors("4", schema), [{"path": "value", "rule": "type"}])

    def test_an_enumeration_accepts_its_values_only_and_tells_true_from_one(self):
        self.assertEqual(self.errors("b", {"enum": ["a", "b", None]}), [])
        self.assertEqual(self.errors(None, {"enum": ["a", "b", None]}), [])
        refused = [{"path": "value", "rule": "enum"}]
        self.assertEqual(self.errors("c", {"enum": ["a", "b", None]}), refused)
        self.assertEqual(self.errors(None, {"enum": ["a", "b"]}), refused)
        self.assertEqual(self.errors(True, {"enum": [1]}), refused)
        self.assertEqual(self.errors(1, {"enum": [True]}), refused)
        self.assertEqual(self.errors(0, {"enum": [False, None]}), refused)
        self.assertEqual(self.errors(False, {"enum": [False]}), [])

    def test_a_pattern_is_searched_anywhere_in_a_string_and_only_in_a_string(self):
        self.assertEqual(self.errors("  x  ", {"pattern": "x"}), [])
        self.assertEqual(self.errors("  y  ", {"pattern": "x"}), [{"path": "value", "rule": "pattern"}])
        for value in (None, 3, ["y"]):
            with self.subTest(value=value):
                self.assertEqual(self.errors(value, {"pattern": "x"}), [])

    def test_a_minimum_is_checked_on_an_integer_only(self):
        self.assertEqual(self.errors(2, {"minimum": 2}), [])
        self.assertEqual(self.errors(1, {"minimum": 2}), [{"path": "value", "rule": "minimum"}])
        for value in (True, None, "0", float("nan"), 0.5):
            with self.subTest(value=value):
                self.assertEqual(self.errors(value, {"minimum": 2}), [])

    def test_required_names_the_path_of_each_missing_key(self):
        schema = {"required": ["a", "b", "c"]}
        expected = [{"path": "value.a", "rule": "required"}, {"path": "value.c", "rule": "required"}]
        self.assertEqual(self.errors({"b": None}, schema), expected)
        self.assertEqual(self.errors("not an object", schema), [])

    def test_a_key_that_the_properties_do_not_name_is_an_error_that_does_not_show_it(self):
        schema = {"properties": {"a": {}}, "additionalProperties": False}
        self.assertEqual(self.errors({"a": 1}, schema), [])
        self.assertEqual(self.errors({}, schema), [])
        expected = [{"path": "value", "rule": "additionalProperties"}]
        self.assertEqual(self.errors({"a": 1, MARKER: 2}, schema), expected)
        self.assertEqual(self.errors({MARKER: 2}, {"additionalProperties": False}), expected)

    def test_properties_and_items_carry_the_path_down(self):
        schema = {"properties": {"list": {"items": {"properties": {"n": {"type": "integer"}}}}}}
        value = {"list": [{"n": 1}, {"n": "one"}, {"other": True}, {"n": None}], "free": "text"}
        expected = [
            {"path": "value.list[1].n", "rule": "type"},
            {"path": "value.list[3].n", "rule": "type"},
        ]
        self.assertEqual(self.errors(value, schema), expected)

    def test_every_keyword_of_a_schema_is_checked(self):
        schema = {"type": "string", "enum": ["ab", 7], "pattern": "^c", "minimum": 9}
        self.assertEqual([error["rule"] for error in self.errors(7, schema)], ["type", "minimum"])
        self.assertEqual([error["rule"] for error in self.errors("ab", schema)], ["pattern"])
        self.assertEqual([error["rule"] for error in self.errors("cd", schema)], ["enum"])

    def test_a_describing_keyword_and_an_extension_check_nothing(self):
        schema = {"$schema": "s", "title": "t", "description": "d", "x-roles": {"type": "null"}}
        self.assertEqual(self.errors(12, schema), [])


class SchemaFile(unittest.TestCase):
    """What the schema file states, beside the fields and the values that the skill names."""

    def refused(self, field: str, value) -> bool:
        return bool(findings.validate(value, PROPERTIES[field], "value"))

    def test_a_finding_has_the_fourteen_fields_all_required_and_no_other(self):
        self.assertEqual(list(PROPERTIES), FIELDS)
        self.assertEqual(SCHEMA["required"], FIELDS)
        self.assertIs(SCHEMA["additionalProperties"], False)
        self.assertEqual(SCHEMA["type"], "object")

    def test_every_property_has_a_description_on_one_line(self):
        for name, property_schema in PROPERTIES.items():
            with self.subTest(field=name):
                self.assertRegex(property_schema["description"], r"\S")
                self.assertNotIn("\n", property_schema["description"])

    def test_the_description_of_severity_defines_the_three_grades(self):
        definitions = {
            "blocking": "merged as it is, the change breaks a stated requirement",
            "major": "a concrete scenario in which the change fails outside its main case",
            "minor": "it would not change the decision to merge",
        }
        for grade, definition in definitions.items():
            with self.subTest(grade):
                self.assertIn(f"{grade}: {definition}", PROPERTIES["severity"]["description"])

    def test_the_enumerations_hold_the_stated_values(self):
        self.assertEqual(PROPERTIES["severity"]["enum"], SEVERITIES)
        self.assertEqual(PROPERTIES["subject"]["enum"], SUBJECTS)
        self.assertEqual(PROPERTIES["origin"]["enum"], ORIGINS + [None])
        self.assertEqual(PROPERTIES["disposition"]["enum"], DISPOSITIONS)

    def test_the_roles_are_the_stated_ones(self):
        self.assertEqual(SCHEMA["x-roles"], ROLES)

    def test_the_schema_file_is_written_in_the_subset(self):
        self.assertEqual(list(findings.outside_subset(SCHEMA, "schema")), [])
        self.assertIs(findings.usable(SCHEMA), SCHEMA)

    def test_an_id_is_a_round_a_lens_and_a_number_from_one(self):
        for value in ("r1-correctness-2", "r12-a-b2-30", "r3-x-10"):
            with self.subTest(accepted=value):
                self.assertFalse(self.refused("id", value))
        refused = [
            "r0-x-1",
            "r01-x-1",
            "r1-x-0",
            "r1-x-01",
            "R1-x-1",
            "r1-X-1",
            "r1--1",
            "r1-x",
            "r1-2",
        ]
        refused += ["xr1-x-1", "r1-x-1x", "r1-x-1\n", "r1-x-1 ", "", 7, None]
        for value in refused:
            with self.subTest(refused=value):
                self.assertTrue(self.refused("id", value))

    def test_a_lens_is_a_lower_case_letter_then_letters_digits_and_hyphens(self):
        for value in ("correctness", "a", "a-b2"):
            with self.subTest(accepted=value):
                self.assertFalse(self.refused("lens", value))
        for value in ("", "Bad Lens", "2a", "a b", "-a", "A", "a\n", "a_b", None):
            with self.subTest(refused=value):
                self.assertTrue(self.refused("lens", value))

    def test_a_file_is_a_relative_path_or_null_and_a_line_is_one_or_more_or_null(self):
        for field, value in (
            ("file", "src/a.py"),
            ("file", None),
            ("line", 1),
            ("line", 120),
            ("line", None),
        ):
            with self.subTest(field=field, accepted=value):
                self.assertFalse(self.refused(field, value))
        refused = [("file", "/etc/passwd"), ("file", "~/notes"), ("file", ""), ("file", 3)]
        refused += [("line", 0), ("line", -1), ("line", True), ("line", 1.5), ("line", "3")]
        for field, value in refused:
            with self.subTest(field=field, refused=value):
                self.assertTrue(self.refused(field, value))

    def test_a_text_field_has_a_character_that_is_not_a_space(self):
        for field in ("summary", "failure_scenario", "fix"):
            self.assertFalse(self.refused(field, " x "))
            for value in ("", "   ", "\n\t ", None, 3):
                with self.subTest(field=field, refused=value):
                    self.assertTrue(self.refused(field, value))

    def test_the_fields_that_the_reviewer_does_not_add(self):
        accepted = [("round_found", 1), ("round_found", 9), ("disclosed_before_review", None)]
        accepted += [("disclosed_before_review", True), ("disclosed_before_review", False)]
        accepted += [("carry_over_of", "r1-x-1"), ("carry_over_of", None), ("origin", None)]
        for field, value in accepted:
            with self.subTest(field=field, accepted=value):
                self.assertFalse(self.refused(field, value))
        refused = [
            ("round_found", 0),
            ("round_found", True),
            ("round_found", None),
            ("round_found", "1"),
        ]
        refused += [("disclosed_before_review", 0), ("disclosed_before_review", "no")]
        refused += [("carry_over_of", 3), ("origin", "elsewhere"), ("disposition", None)]
        for field, value in refused:
            with self.subTest(field=field, refused=value):
                self.assertTrue(self.refused(field, value))

    def test_the_codebook_has_its_four_sections_and_the_origins_of_the_schema(self):
        codebook = (SKILL / "codebook.md").read_text(encoding="utf-8")
        headings = [line for line in codebook.splitlines() if line.startswith("## ")]
        self.assertEqual(headings, ["## Category", "## Origin", "## Knowable", "## Cheapest preventer"])
        section = codebook.split("## Origin\n")[1].split("\n## ")[0]
        listed = [line.split("`")[1] for line in section.splitlines() if line.startswith("- `")]
        self.assertEqual(sorted(listed), sorted(ORIGINS))


class RoleSchemas(CommandLine):
    def role(self, name: str, script: Path = SCRIPT) -> dict:
        return self.assertDone(self.script("schema", "--role", name, script=script))

    def test_schema_prints_the_schema_file(self):
        result = self.script("schema")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, (SKILL / "finding.schema.json").read_text(encoding="utf-8"))

    def test_a_reviewer_answers_findings_with_the_fields_that_it_adds_all_required(self):
        schema = self.role("reviewer")
        self.assertEqual(sorted(schema), ["additionalProperties", "properties", "required", "type"])
        self.assertEqual(schema["type"], "object")
        self.assertEqual(schema["required"], ["findings"])
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(list(schema["properties"]), ["findings"])
        self.assertEqual(schema["properties"]["findings"]["type"], "array")
        finding = schema["properties"]["findings"]["items"]
        self.assertEqual(finding["type"], "object")
        self.assertEqual(finding["properties"], {name: PROPERTIES[name] for name in REVIEWER_FIELDS})
        self.assertEqual(sorted(finding["required"]), sorted(REVIEWER_FIELDS))
        self.assertIs(finding["additionalProperties"], False)

    def test_a_fixer_answers_updates_with_an_id_and_the_two_dispositions_that_it_may_write(self):
        schema = self.role("fixer")
        self.assertEqual(sorted(schema), ["additionalProperties", "properties", "required", "type"])
        self.assertEqual(schema["required"], ["updates"])
        self.assertIs(schema["additionalProperties"], False)
        self.assertEqual(list(schema["properties"]), ["updates"])
        update = schema["properties"]["updates"]["items"]
        self.assertEqual(sorted(update["properties"]), ["disposition", "id"])
        self.assertEqual(update["properties"]["id"], PROPERTIES["id"])
        self.assertEqual(update["properties"]["disposition"]["enum"], ["fixed", "declined"])
        description = PROPERTIES["disposition"]["description"]
        self.assertEqual(update["properties"]["disposition"]["description"], description)
        self.assertEqual(update["required"], ["id"])
        self.assertIs(update["additionalProperties"], False)

    def test_the_coordinator_answers_updates_with_its_four_fields_and_every_value(self):
        update = self.role("coordinator")["properties"]["updates"]["items"]
        fields = ["origin", "disclosed_before_review", "carry_over_of", "disposition"]
        self.assertEqual(sorted(update["properties"]), sorted(["id"] + fields))
        for field in fields:
            with self.subTest(field=field):
                self.assertEqual(update["properties"][field], PROPERTIES[field])
        self.assertEqual(update["required"], ["id"])
        self.assertIs(update["additionalProperties"], False)

    def test_the_schema_of_a_role_is_written_in_the_subset_and_accepts_an_answer_of_the_role(self):
        answers = {
            "reviewer": {"findings": [reported("r1-design-1")]},
            "fixer": {"updates": [{"id": "r1-design-1", "disposition": "declined"}]},
            "coordinator": {"updates": [{"id": "r1-design-1", "disclosed_before_review": False}]},
        }
        for role, answer in answers.items():
            with self.subTest(role=role):
                schema = self.role(role)
                self.assertEqual(list(findings.outside_subset(schema, "schema")), [])
                self.assertEqual(findings.validate(answer, schema, "answer"), [])

    def test_a_role_that_the_schema_file_does_not_hold_is_a_wrong_call(self):
        self.assertWrongCall(self.script("schema", "--role", MARKER))
        self.assertWrongCall(self.script("schema", "--role"))


class Add(CommandLine):
    def test_add_completes_the_finding_and_writes_the_stated_format(self):
        given = dict(reversed(reported("r1-design-1", summary="Un résumé").items()))
        self.assertEqual(self.assertDone(self.add(given)), {"added": ["r1-design-1"], "findings": 1})
        expected = """{
  "findings": [
    {
      "id": "r1-design-1",
      "file": "lib/parse.py",
      "line": 7,
      "severity": "major",
      "summary": "Un résumé",
      "failure_scenario": "The list is empty",
      "fix": "Return zero",
      "lens": "design",
      "subject": "code",
      "round_found": 1,
      "origin": null,
      "disclosed_before_review": null,
      "disposition": "open",
      "carry_over_of": null
    }
  ]
}
"""
        self.assertEqual(self.file.read_bytes(), expected.encode("utf-8"))

    def test_the_file_is_utf_8_whatever_the_encoding_of_the_locale(self):
        ascii_locale = {"LC_ALL": "C", "PYTHONCOERCECLOCALE": "0", "PYTHONUTF8": "0"}
        self.assertDone(self.add(reported("r1-design-1", summary="Un résumé"), **ascii_locale))
        self.assertIn('"summary": "Un résumé"'.encode("utf-8"), self.file.read_bytes())

    def test_add_takes_the_round_of_the_call_and_a_finding_about_no_file(self):
        given = reported("r3-design-1", file=None, line=None)
        self.assertDone(self.add(given, round_found=3))
        self.assertEqual(self.held(), [stored("r3-design-1", file=None, line=None, round_found=3)])

    def test_add_keeps_the_findings_of_the_file_and_counts_them_all(self):
        self.assertDone(self.add(reported("r1-design-1"), reported("r1-design-2")))
        result = self.add(reported("r1-security-1"), lens="security")
        self.assertEqual(self.assertDone(result), {"added": ["r1-security-1"], "findings": 3})
        result = self.add(reported("r2-design-1"), round_found=2)
        self.assertEqual(self.assertDone(result), {"added": ["r2-design-1"], "findings": 4})
        expected = ["r1-design-1", "r1-design-2", "r1-security-1", "r2-design-1"]
        self.assertEqual(self.held(), [stored(identifier) for identifier in expected])

    def test_every_finding_of_the_file_is_written_with_its_keys_in_the_order_of_the_schema(self):
        self.hold(dict(reversed(stored("r1-design-1").items())))
        self.assertDone(self.add(reported("r1-design-2")))
        self.assertEqual([list(finding) for finding in self.held()], [FIELDS, FIELDS])

    def test_an_answer_with_no_finding_is_valid_and_creates_the_file(self):
        self.assertEqual(self.assertDone(self.add(round_found=4)), {"added": [], "findings": 0})
        self.assertEqual(self.file.read_text(), '{\n  "findings": []\n}\n')

    def test_missing_parent_directories_are_created_for_an_ignored_file(self):
        file = self.repository / "kept" / "a" / "b" / "plan.json"
        self.assertDone(self.add(reported("r1-design-1"), file=file))
        self.assertEqual(self.held(file), [stored("r1-design-1")])

    def test_a_faulty_answer_is_rejected_whole_and_creates_nothing(self):
        one = reported("r1-design-1")
        of_the_call = "the round and the lens given to add, before the last hyphen"
        cases = [
            (
                "a scenario of spaces only",
                [one | {"failure_scenario": " \t"}],
                "[0].failure_scenario",
                "pattern",
            ),
            ("an empty fix", [one | {"fix": ""}], "[0].fix", "pattern"),
            ("true as a line", [one | {"line": True}], "[0].line", "type"),
            ("a line of zero", [one | {"line": 0}], "[0].line", "minimum"),
            ("a line that is not whole", [one | {"line": 1.5}], "[0].line", "type"),
            ("a line that is text", [one | {"line": MARKER}], "[0].line", "type"),
            ("a missing field", [{k: v for k, v in one.items() if k != "fix"}], "[0].fix", "required"),
            ("an unknown field", [one | {"note": MARKER}], "[0]", "additionalProperties"),
            ("an unknown key", [one | {MARKER: 1}], "[0]", "additionalProperties"),
            (
                "a field of another role",
                [one | {"disposition": "fixed"}],
                "[0]",
                "additionalProperties",
            ),
            (
                "a round that the answer gives",
                [one | {"round_found": 1}],
                "[0]",
                "additionalProperties",
            ),
            ("an unknown severity", [one | {"severity": MARKER}], "[0].severity", "enum"),
            ("an unknown subject", [one | {"subject": None}], "[0].subject", "enum"),
            ("an absolute path", [one | {"file": "/" + MARKER}], "[0].file", "pattern"),
            ("a path from the home directory", [one | {"file": "~/" + MARKER}], "[0].file", "pattern"),
            ("a line of no file", [one | {"file": None}], "[0].line", "null when file is null"),
            ("an id that ends in a line break", [one | {"id": "r1-design-1\n"}], "[0].id", "pattern"),
            ("an id of another round", [one | {"id": "r2-design-1"}], "[0].id", of_the_call),
            ("an id of another lens", [one | {"id": "r1-security-1"}], "[0].id", of_the_call),
            ("an id of a longer lens", [one | {"id": "r1-design-extra-1"}], "[0].id", of_the_call),
            ("an id of a lens that goes on", [one | {"id": "r1-design-2-1"}], "[0].id", of_the_call),
            ("an id numbered zero", [one | {"id": "r1-design-0"}], "[0].id", "pattern"),
            ("an id with a leading zero", [one | {"id": "r1-design-01"}], "[0].id", "pattern"),
            (
                "a lens other than the one of the call",
                [one | {"lens": "security"}],
                "[0].lens",
                "the lens given to add",
            ),
            (
                "the same id twice",
                [reported("r1-design-2"), one, one],
                "[2].id",
                "unique among the findings",
            ),
            ("a finding that is text", [MARKER], "[0]", "type"),
            (
                "a faulty finding after a valid one",
                [one, reported("r1-design-2", line=0)],
                "[1].line",
                "minimum",
            ),
        ]
        for label, given, path, rule in cases:
            with self.subTest(label):
                errors = self.assertRejected(self.add(*given))
                found = [error for error in errors if error["path"] == "answer.findings" + path]
                self.assertTrue(found, errors)
                self.assertIn(rule, [error["rule"] for error in found])
                self.assertFalse(self.file.parent.exists())

    def test_an_answer_of_another_shape_is_rejected(self):
        one = reported("r1-design-1")
        cases = [
            ("findings that are not a list", {"findings": {}}, "answer.findings", "type"),
            (
                "a key beside the findings",
                {"findings": [one], "note": MARKER},
                "answer",
                "additionalProperties",
            ),
            ("no findings", {}, "answer.findings", "required"),
            ("a list", [one], "answer", "type"),
            ("the updates of another command", {"updates": []}, "answer.findings", "required"),
        ]
        arguments = ["add", "--file", str(self.file), "--round", "1", "--lens", "design"]
        for label, answer, path, rule in cases:
            with self.subTest(label):
                errors = self.assertRejected(self.script(*arguments, answer=answer))
                self.assertIn({"path": path, "rule": rule}, errors)
                self.assertFalse(self.file.parent.exists())

    def test_the_valid_half_of_a_rejected_answer_is_not_written(self):
        before = self.hold(stored("r1-design-1"))
        self.assertRejected(
            self.add(reported("r1-design-2"), reported("r1-design-3", severity="grave"))
        )
        self.assertEqual(self.file.read_bytes(), before)

    def test_an_id_that_the_file_holds_is_rejected_and_the_file_stays_byte_for_byte(self):
        before = self.hold(stored("r1-design-1"))
        errors = self.assertRejected(
            self.add(reported("r1-design-2"), reported("r1-design-1", fix="Other"))
        )
        self.assertEqual([error["path"] for error in errors], ["answer.findings[1].id"])
        self.assertEqual(self.file.read_bytes(), before)

    def test_an_answer_that_is_not_json_is_a_failure(self):
        arguments = ["add", "--file", str(self.file), "--round", "1", "--lens", "design"]
        for answer in ("not json " + MARKER, '{"findings": [NaN]}', '{"findings": [Infinity]}', ""):
            with self.subTest(answer=answer):
                self.assertFailed(self.script(*arguments, answer=answer))
                self.assertFalse(self.file.parent.exists())

    def test_an_answer_that_cannot_be_written_or_read_is_a_failure_and_creates_nothing(self):
        # JSON can name half of a surrogate pair by an escape, and UTF-8 does not hold it.
        half = reported("r1-design-1", summary="half \ud83d of a pair")
        answers = {
            "half of a surrogate pair": json.dumps({"findings": [half]}),
            "lists nested deeper than python reads": "[" * 100_000 + "]" * 100_000,
        }
        self.assertIn("half \\ud83d of a pair", answers["half of a surrogate pair"])
        arguments = ["add", "--file", str(self.file), "--round", "1", "--lens", "design"]
        for label, answer in answers.items():
            with self.subTest(label):
                self.assertFailed(self.script(*arguments, answer=answer))
                self.assertFalse(self.file.parent.exists())

    def test_a_round_below_one_a_lens_outside_its_pattern_or_a_missing_argument_is_a_wrong_call(self):
        file, one = ["--file", str(self.file)], {"findings": [reported("r1-design-1")]}
        calls = [
            ["add", *file, "--round", "0", "--lens", "design"],
            ["add", *file, "--round", "-1", "--lens", "design"],
            ["add", *file, "--round", "1.5", "--lens", "design"],
            ["add", *file, "--round", MARKER, "--lens", "design"],
            ["add", *file, "--round", "1", "--lens", "Bad " + MARKER],
            ["add", *file, "--round", "1", "--lens", "design\n"],
            ["add", *file, "--round", "1"],
            ["add", *file, "--lens", "design"],
            ["add", "--round", "1", "--lens", "design"],
            ["add"],
            [],
            ["remove", *file],
        ]
        for call in calls:
            with self.subTest(call=call[:1] + call[3:]):
                self.assertWrongCall(self.script(*call, answer=one))
                self.assertFalse(self.file.parent.exists())


class Set(CommandLine):
    def setUp(self):
        super().setUp()
        self.before = self.hold(
            stored("r1-design-1", severity="blocking"),
            stored("r1-design-2", disposition="fixed"),
            stored("r2-design-1"),
            stored("r2-design-2"),
        )

    def assertEachRejected(self, role: str, cases: list[tuple]) -> None:
        """Each answer is rejected with an error at the stated place, and the file stays as it was."""
        for label, updates, where in cases:
            with self.subTest(label):
                errors = self.assertRejected(self.set(role, *updates))
                self.assertIn("answer.updates" + where, [error["path"] for error in errors])
                self.assertEqual(self.file.read_bytes(), self.before)

    def test_a_fixer_sets_an_open_finding_to_fixed_or_declined_and_nothing_else_changes(self):
        declined, fixed = (
            update("r2-design-1", disposition="declined"),
            update("r1-design-1", disposition="fixed"),
        )
        result = self.set("fixer", declined, fixed)
        self.assertEqual(self.assertDone(result), {"updated": ["r2-design-1", "r1-design-1"]})
        expected = [
            stored("r1-design-1", severity="blocking", disposition="fixed"),
            stored("r1-design-2", disposition="fixed"),
            stored("r2-design-1", disposition="declined"),
            stored("r2-design-2"),
        ]
        self.assertEqual(self.held(), expected)
        self.assertEqual([list(finding) for finding in self.held()], [FIELDS] * 4)
        self.assertTrue(self.file.read_text().startswith('{\n  "findings": [\n    {\n      "id"'))

    def test_what_a_fixer_may_not_write_is_rejected_and_the_file_stays_byte_for_byte(self):
        fixed = update("r1-design-1", disposition="fixed")
        cases = [
            (
                "a value of the coordinator",
                [update("r1-design-1", disposition="ruled")],
                "[0].disposition",
            ),
            ("back to open", [update("r1-design-1", disposition="open")], "[0].disposition"),
            ("an unknown value", [update("r1-design-1", disposition=MARKER)], "[0].disposition"),
            ("a field of the reviewer", [update("r1-design-1", severity="minor")], "[0]"),
            ("a field of the coordinator", [fixed | {"origin": "fix-round"}], "[0]"),
            ("an unknown key", [fixed | {MARKER: 1}], "[0]"),
            (
                "a finding that is not open",
                [update("r1-design-2", disposition="declined")],
                "[0].disposition",
            ),
            (
                "a finding fixed already",
                [update("r1-design-2", disposition="fixed")],
                "[0].disposition",
            ),
            ("an id that the file lacks", [update("r1-design-9", disposition="fixed")], "[0].id"),
            ("an id of no form", [update(MARKER, disposition="fixed")], "[0].id"),
            ("no field", [update("r1-design-1")], "[0]"),
            ("no id", [{"disposition": "fixed"}], "[0].id"),
            (
                "a faulty update after a valid one",
                [fixed, update("r1-design-9", disposition="fixed")],
                "[1].id",
            ),
            ("the same id twice", [fixed, update("r1-design-1", disposition="declined")], "[1].id"),
            ("an update that is text", [MARKER], "[0]"),
        ]
        self.assertEachRejected("fixer", cases)

    def test_the_coordinator_sets_its_four_fields(self):
        fields = {
            "origin": "fix-round",
            "disclosed_before_review": True,
            "carry_over_of": "r1-design-1",
            "disposition": "needs-user",
        }
        result = self.set("coordinator", update("r2-design-1", **fields))
        self.assertEqual(self.assertDone(result), {"updated": ["r2-design-1"]})
        expected = json.loads(self.before)["findings"]
        expected[2] = stored("r2-design-1", **fields)
        self.assertEqual(self.held(), expected)

    def test_the_coordinator_sets_one_field_alone_a_false_or_a_null_included(self):
        self.assertDone(self.set("coordinator", update("r2-design-2", disclosed_before_review=False)))
        self.assertEqual(self.held()[3], stored("r2-design-2", disclosed_before_review=False))
        self.assertDone(self.set("coordinator", update("r2-design-2", disclosed_before_review=None)))
        self.assertEqual(self.held()[3], stored("r2-design-2"))
        self.assertDone(self.set("coordinator", update("r2-design-2", carry_over_of="r1-design-2")))
        self.assertEqual(self.held()[3], stored("r2-design-2", carry_over_of="r1-design-2"))
        self.assertDone(self.set("coordinator", update("r2-design-2", carry_over_of=None)))
        self.assertEqual(self.held()[3], stored("r2-design-2"))

    def test_the_coordinator_sets_any_disposition_from_any_other_and_any_origin(self):
        for disposition in DISPOSITIONS[1:] + DISPOSITIONS[:1]:
            with self.subTest(disposition=disposition):
                self.assertDone(self.set("coordinator", update("r1-design-2", disposition=disposition)))
                self.assertEqual(self.held()[1]["disposition"], disposition)
        for origin in ORIGINS + [None]:
            with self.subTest(origin=origin):
                self.assertDone(self.set("coordinator", update("r1-design-2", origin=origin)))
                self.assertEqual(self.held()[1]["origin"], origin)

    def test_what_the_coordinator_may_not_write_is_rejected_and_the_file_stays_byte_for_byte(self):
        valid, link = update("r2-design-2", origin="coordinator"), "[0].carry_over_of"
        cases = [
            (
                "a carry-over to a later round",
                [update("r1-design-1", carry_over_of="r2-design-1")],
                link,
            ),
            (
                "a carry-over to the same round",
                [update("r2-design-1", carry_over_of="r2-design-2")],
                link,
            ),
            ("a carry-over to itself", [update("r2-design-1", carry_over_of="r2-design-1")], link),
            ("a carry-over to nothing", [update("r2-design-1", carry_over_of="r1-design-9")], link),
            ("a carry-over that is not text", [update("r2-design-1", carry_over_of=1)], link),
            ("a carry-over that is not an id", [update("r2-design-1", carry_over_of=MARKER)], link),
            ("an unknown origin", [update("r2-design-1", origin=MARKER)], "[0].origin"),
            ("an unknown disposition", [update("r2-design-1", disposition=MARKER)], "[0].disposition"),
            (
                "a disclosure that is 0",
                [update("r2-design-1", disclosed_before_review=0)],
                "[0].disclosed_before_review",
            ),
            ("no field", [update("r2-design-1")], "[0]"),
            ("a field of the reviewer", [update("r2-design-1", severity="minor")], "[0]"),
            ("the round", [update("r2-design-1", round_found=1)], "[0]"),
            ("an id that the file lacks", [update("r3-design-1", origin="coordinator")], "[0].id"),
            (
                "a faulty update after a valid one",
                [valid, update("r2-design-1", carry_over_of="r2-design-2")],
                "[1].carry_over_of",
            ),
        ]
        self.assertEachRejected("coordinator", cases)

    def test_an_answer_of_another_shape_is_rejected(self):
        arguments = ["set", "--file", str(self.file), "--role", "coordinator"]
        valid = update("r2-design-1", origin="coordinator")
        cases = [
            ("updates that are not a list", {"updates": valid}, "answer.updates", "type"),
            (
                "a key beside the updates",
                {"updates": [valid], "note": MARKER},
                "answer",
                "additionalProperties",
            ),
            ("the findings of another command", {"findings": []}, "answer.updates", "required"),
        ]
        for label, answer, path, rule in cases:
            with self.subTest(label):
                errors = self.assertRejected(self.script(*arguments, answer=answer))
                self.assertIn({"path": path, "rule": rule}, errors)
                self.assertEqual(self.file.read_bytes(), self.before)

    def test_an_answer_with_no_update_changes_no_finding(self):
        self.assertEqual(self.assertDone(self.set("fixer")), {"updated": []})
        self.assertEqual(self.held(), json.loads(self.before)["findings"])

    def test_set_creates_no_file_and_no_directory(self):
        valid = update("r1-design-1", origin="coordinator")
        for file in (self.file.with_name("other.json"), self.file.parent / "deep" / "plan.json"):
            with self.subTest(file=file.name):
                self.assertFailed(self.set("coordinator", valid, file=file))
                self.assertFalse(file.exists())
                self.assertFalse((self.file.parent / "deep").exists())

    def test_a_role_that_sets_nothing_or_that_the_schema_file_does_not_hold_is_a_wrong_call(self):
        answer = {"updates": []}
        for call in (["--role", "reviewer"], ["--role", MARKER], []):
            with self.subTest(call=call):
                self.assertWrongCall(self.script("set", "--file", str(self.file), *call, answer=answer))
        self.assertWrongCall(self.script("set", "--role", "fixer", answer=answer))
        self.assertEqual(self.file.read_bytes(), self.before)


class Summary(CommandLine):
    def summary(self, file: Path | None = None, script: Path = SCRIPT):
        return self.script("summary", "--file", str(file or self.file), script=script)

    def test_the_summary_counts_per_round_per_disposition_and_what_is_open_and_serious(self):
        self.hold(
            stored("r1-design-1", severity="blocking", disposition="fixed"),
            stored("r1-design-2", severity="minor"),
            stored("r3-design-1", severity="major"),
            stored("r3-design-2", severity="blocking"),
            stored("r3-design-3", severity="minor", disposition="declined"),
            stored("r3-design-4", severity="major", disposition="needs-user"),
        )
        counted = self.assertDone(self.summary())
        rounds = [
            {"round": 1, "blocking": 1, "major": 0, "minor": 1},
            {"round": 3, "blocking": 1, "major": 2, "minor": 1},
        ]
        self.assertEqual(counted["rounds"], rounds)
        dispositions = dict.fromkeys(DISPOSITIONS, 0) | {
            "open": 3,
            "fixed": 1,
            "declined": 1,
            "needs-user": 1,
        }
        self.assertEqual(counted["dispositions"], dispositions)
        self.assertEqual(counted["open_serious"], 2)
        self.assertEqual(sorted(counted), ["dispositions", "open_serious", "rounds"])

    def test_the_rounds_are_in_order_whatever_the_order_of_the_findings_in_the_file(self):
        self.hold(stored("r2-design-1"), stored("r1-design-1"))
        rounds = self.assertDone(self.summary())["rounds"]
        self.assertEqual([counted["round"] for counted in rounds], [1, 2])

    def test_the_summary_of_a_file_with_no_finding(self):
        self.hold()
        expected = {"rounds": [], "dispositions": dict.fromkeys(DISPOSITIONS, 0), "open_serious": 0}
        self.assertEqual(self.assertDone(self.summary()), expected)

    def test_a_file_that_breaks_the_schema_or_a_rule_is_rejected(self):
        one, two = stored("r1-design-1"), stored("r2-design-1")
        cases = [
            ("an unknown severity", [one | {"severity": MARKER}, two], "[0].severity"),
            ("an unknown key", [one, two | {MARKER: 1}], "[1]"),
            ("a missing field", [{k: v for k, v in one.items() if k != "origin"}], "[0].origin"),
            ("true as a round", [one | {"round_found": True}], "[0].round_found"),
            ("the same id twice", [one, two, one], "[2].id"),
            ("a line of no file", [one | {"file": None}], "[0].line"),
            (
                "a carry-over to nothing",
                [one, two | {"carry_over_of": "r1-design-9"}],
                "[1].carry_over_of",
            ),
            (
                "a carry-over to a later round",
                [one | {"carry_over_of": "r2-design-1"}, two],
                "[0].carry_over_of",
            ),
            (
                "a carry-over to the same round",
                [one, stored("r1-design-2", carry_over_of="r1-design-1")],
                "[1].carry_over_of",
            ),
            (
                "a carry-over to itself",
                [one, two | {"carry_over_of": "r2-design-1"}],
                "[1].carry_over_of",
            ),
            ("a finding that is text", [MARKER], "[0]"),
        ]
        for label, held, where in cases:
            with self.subTest(label):
                before = self.hold(*held)
                errors = self.assertRejected(self.summary())
                self.assertIn("file.findings" + where, [error["path"] for error in errors])
                self.assertEqual(self.file.read_bytes(), before)

    def test_a_file_of_another_shape_is_rejected(self):
        one = stored("r1-design-1")
        cases = [
            ("a list in place of the object", [one], "file", "type"),
            ("no findings", {}, "file.findings", "required"),
            ("findings that are not a list", {"findings": one}, "file.findings", "type"),
            (
                "a key beside the findings",
                {"findings": [one], "rounds": []},
                "file",
                "additionalProperties",
            ),
        ]
        self.file.parent.mkdir()
        for label, document, path, rule in cases:
            with self.subTest(label):
                self.file.write_text(json.dumps(document))
                self.assertIn({"path": path, "rule": rule}, self.assertRejected(self.summary()))

    def test_every_command_rejects_a_file_that_breaks_a_rule_and_leaves_it_byte_for_byte(self):
        broken = {
            "the schema": stored("r1-design-1", severity=MARKER),
            "a rule": stored("r1-design-1", carry_over_of="r1-design-1"),
        }
        for label, finding in broken.items():
            file = self.file.with_name(f"breaks {label}.json")
            before = self.hold(finding, file=file)
            results = {
                "summary": self.summary(file),
                "add": self.add(reported("r3-design-1"), round_found=3, file=file),
                "add nothing": self.add(file=file),
                "set": self.set("coordinator", update("r1-design-1", origin="coordinator"), file=file),
                "set nothing": self.set("coordinator", file=file),
                # The file is judged before the answer, so a faulty answer changes nothing here.
                "add a faulty answer": self.add(
                    reported("r3-design-1", line=0), round_found=3, file=file
                ),
                "set a faulty answer": self.set(
                    "coordinator", update("r1-design-1", origin=MARKER), file=file
                ),
            }
            for command, result in results.items():
                with self.subTest(breaks=label, command=command):
                    errors = self.assertRejected(result)
                    self.assertTrue(
                        all(error["path"].startswith("file.findings[0]") for error in errors)
                    )
                    self.assertEqual(file.read_bytes(), before)

    def test_a_carry_over_to_an_earlier_round_is_valid_wherever_its_target_stands_in_the_file(self):
        self.hold(stored("r2-design-1", carry_over_of="r1-design-1"), stored("r1-design-1"))
        self.assertEqual(self.assertDone(self.summary())["open_serious"], 2)

    def test_a_file_that_is_not_json_is_a_failure_for_every_command_and_stays(self):
        self.file.parent.mkdir()
        for content in ("not json " + MARKER, '{"findings": [NaN]}', ""):
            with self.subTest(content=content):
                self.file.write_text(content)
                self.assertFailed(self.summary())
                self.assertFailed(self.set("coordinator", update("r1-design-1", origin="coordinator")))
                self.assertFailed(self.add(reported("r1-design-1")))
                self.assertEqual(self.file.read_text(), content)

    def test_a_file_that_cannot_be_read_or_written_back_is_a_failure_for_every_command_and_stays(self):
        valid = json.dumps({"findings": [stored("r1-design-1", summary="X")]}).encode("utf-8")
        contents = {
            "a byte that is not UTF-8": valid.replace(b"X", b"\xff"),
            "the escape of half of a surrogate pair": valid.replace(b"X", rb"\ud83d"),
            "lists nested deeper than python reads": b"[" * 100_000 + b"]" * 100_000,
        }
        self.file.parent.mkdir()
        for label, content in contents.items():
            with self.subTest(label):
                self.file.write_bytes(content)
                self.assertFailed(self.summary())
                self.assertFailed(self.set("coordinator", update("r1-design-1", origin="coordinator")))
                self.assertFailed(self.add(reported("r1-design-2")))
                self.assertEqual(self.file.read_bytes(), content)

    def test_without_a_file_the_summary_is_a_failure_and_creates_none(self):
        self.assertFailed(self.summary())
        self.assertFalse(self.file.parent.exists())
        self.assertWrongCall(self.script("summary"))


class Guard(CommandLine):
    """Nothing is written, and no directory is made, unless git says that it ignores the file."""

    def assertRefused(self, file: Path, top: Path, **environment: str) -> None:
        self.assertFailed(self.add(reported("r1-design-1"), file=file, **environment))
        self.assertFalse(top.exists())

    def test_a_file_that_git_does_not_ignore_is_refused_before_any_directory_is_made(self):
        self.assertRefused(self.repository / "open" / "deep" / "plan.json", self.repository / "open")

    def test_a_directory_of_the_same_name_elsewhere_in_the_repository_is_not_ignored(self):
        self.assertRefused(self.repository / "src" / "kept" / "plan.json", self.repository / "src")

    def test_a_file_outside_any_repository_is_refused(self):
        self.assertRefused(self.scratch / "elsewhere" / "plan.json", self.scratch / "elsewhere")

    def test_without_git_the_file_is_refused(self):
        empty = self.scratch / "empty"
        empty.mkdir()
        self.assertRefused(self.file, self.file.parent, PATH=str(empty))

    def test_a_file_that_is_not_ignored_is_not_changed_by_set(self):
        file = self.repository / "plan.json"
        before = self.hold(stored("r1-design-1"), file=file)
        self.assertFailed(
            self.set("coordinator", {"id": "r1-design-1", "origin": "coordinator"}, file=file)
        )
        self.assertEqual(file.read_bytes(), before)

    def test_a_file_that_git_tracks_is_refused_though_a_rule_ignores_its_path(self):
        before = self.hold(stored("r1-design-1"))
        self.git("-C", str(self.repository), "add", "--force", "kept/plan.json")
        self.assertFailed(self.add(reported("r1-design-2")))
        self.assertFailed(self.set("coordinator", update("r1-design-1", origin="coordinator")))
        self.assertEqual(self.file.read_bytes(), before)

    def test_a_relative_path_is_judged_as_the_absolute_path_of_the_file(self):
        # Judged from its directory, `open/plan.json` would be `open/open/plan.json`.
        (self.repository / ".gitignore").write_text("/kept/\n/open/open/\n")
        (self.repository / "open").mkdir()
        (self.repository / "kept").mkdir()
        one = reported("r1-design-1")
        self.assertFailed(self.add(one, file=Path("open", "plan.json"), cwd=self.repository))
        self.assertEqual(os.listdir(self.repository / "open"), [])
        self.assertDone(self.add(one, file=Path("kept", "plan.json"), cwd=self.repository))
        self.assertEqual(self.held(), [stored("r1-design-1")])

    def test_an_ignore_rule_injected_by_the_environment_changes_nothing(self):
        rules = self.scratch / "ignore-all"
        rules.write_text("*\n")
        injected = {
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "core.excludesFile",
            "GIT_CONFIG_VALUE_0": str(rules),
        }
        self.assertRefused(self.repository / "open" / "plan.json", self.repository / "open", **injected)
        injected = {"GIT_CONFIG_PARAMETERS": f"'core.excludesFile={rules}'"}
        self.assertRefused(self.repository / "open" / "plan.json", self.repository / "open", **injected)

    def test_git_is_given_no_git_variable_of_the_caller_but_the_three_that_are_kept(self):
        tools = self.scratch / "tools"
        tools.mkdir()
        seen = self.scratch / "seen"
        # Stands for git: it writes its environment, and its status says that the file is ignored.
        (tools / "git").write_text(f'#!/bin/sh\nenv > "{seen}"\n')
        (tools / "git").chmod(0o755)
        given = {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_PARAMETERS": "'core.excludesFile=ignore-all'",
            "GIT_INDEX_FILE": "index",
            "GIT_COMMON_DIR": "common",
            "GIT_INVENTED": "1",
        }
        path = os.pathsep.join([str(tools), self.environment["PATH"]])
        self.assertDone(self.add(reported("r1-design-1"), PATH=path, **given))
        names = [line.split("=")[0] for line in seen.read_text().splitlines()]
        self.assertEqual(
            sorted(name for name in names if name.startswith("GIT_")),
            ["GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_SYSTEM"],
        )

    def test_the_repository_is_the_one_of_the_file_whatever_git_dir_says(self):
        decoy = self.scratch / "decoy"
        self.git("init", "--quiet", str(decoy))
        (decoy / ".git" / "info" / "exclude").write_text("*\n")
        elsewhere = {"GIT_DIR": str(decoy / ".git"), "GIT_WORK_TREE": str(decoy)}
        self.assertRefused(
            self.repository / "open" / "plan.json", self.repository / "open", **elsewhere
        )
        self.assertRefused(
            self.repository / "open" / "plan.json",
            self.repository / "open",
            GIT_DIR=str(decoy / ".git"),
        )
        (decoy / ".git" / "info" / "exclude").write_text("")
        self.assertDone(self.add(reported("r1-design-1"), **elsewhere))
        self.assertDone(self.add(reported("r1-design-2"), GIT_DIR=str(decoy / ".git")))
        self.assertEqual(len(self.held()), 2)
        self.assertEqual(sorted(os.listdir(decoy)), [".git"])

    def test_a_file_that_a_rule_ignores_by_its_name_alone_is_written(self):
        (self.repository / ".gitignore").write_text("*.findings.json*\n")
        file = self.repository / "open" / "plan.findings.json"
        self.assertDone(self.add(reported("r1-design-1"), file=file))
        self.assertEqual(self.held(file), [stored("r1-design-1")])
        self.assertRefused(self.repository / "shut" / "plan.json", self.repository / "shut")

    def test_a_file_whose_temporary_file_git_does_not_ignore_is_refused(self):
        # The write goes through `.<name>.<pid>.tmp` beside the file, which this rule does not cover.
        (self.repository / ".gitignore").write_text("plan.json\n")
        self.assertRefused(self.repository / "open" / "plan.json", self.repository / "open")
        before = self.hold(stored("r1-design-1"), file=self.repository / "made" / "plan.json")
        result = self.add(reported("r1-design-2"), file=self.repository / "made" / "plan.json")
        self.assertFailed(result)
        self.assertIn(".tmp", result.stderr)
        self.assertEqual(os.listdir(self.repository / "made"), ["plan.json"])
        self.assertEqual((self.repository / "made" / "plan.json").read_bytes(), before)

    def test_a_personal_ignore_rule_counts_through_the_files_that_git_is_told_to_read(self):
        rules = self.scratch / "ignore-all"
        rules.write_text("*\n")
        configuration = self.scratch / "gitconfig"
        configuration.write_text(f"[core]\n\texcludesFile = {rules}\n")
        for number, variable in enumerate(("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")):
            with self.subTest(variable=variable):
                file = self.repository / f"personal-{number}" / "plan.json"
                self.assertDone(
                    self.add(reported("r1-design-1"), file=file, **{variable: str(configuration)})
                )
                self.assertEqual(self.held(file), [stored("r1-design-1")])

    def test_the_personal_ignore_file_that_git_finds_from_the_home_directory_counts(self):
        del self.environment["GIT_CONFIG_GLOBAL"]
        personal = Path(self.environment["HOME"], ".config", "git", "ignore")
        personal.parent.mkdir(parents=True)
        personal.write_text("*plan.json*\n")
        file = self.repository / "open" / "plan.json"
        self.assertDone(self.add(reported("r1-design-1"), file=file))
        self.assertEqual(self.held(file), [stored("r1-design-1")])

    def test_the_variable_that_turns_the_system_configuration_off_is_kept(self):
        rules = self.scratch / "ignore-all"
        rules.write_text("*\n")
        configuration = self.scratch / "gitconfig"
        configuration.write_text(f"[core]\n\texcludesFile = {rules}\n")
        off = {"GIT_CONFIG_SYSTEM": str(configuration), "GIT_CONFIG_NOSYSTEM": "1"}
        self.assertRefused(self.repository / "open" / "plan.json", self.repository / "open", **off)

    def test_git_is_given_ten_seconds_and_no_answer_is_a_refusal(self):
        file = self.repository / "kept" / "plan.json"
        silence = subprocess.TimeoutExpired("git", 10)
        with mock.patch.object(findings.subprocess, "run", side_effect=silence) as asked:
            with self.assertRaises(findings.Failure):
                findings.rewrite(file, self.fail)
        self.assertEqual(asked.call_args.kwargs["timeout"], 10)
        self.assertFalse(file.parent.exists())


class Writers(CommandLine):
    def writer(self, identifier: str, role: str | None = None) -> subprocess.Popen:
        """Start a writer that adds one finding, or that sets the origin of one as `role`.

        Its answer is on its standard input already.
        """
        if role is None:
            arguments = ["add", "--file", str(self.file), "--round", "1", "--lens", "design"]
            answer = {"findings": [reported(identifier)]}
        else:
            arguments = ["set", "--file", str(self.file), "--role", role]
            answer = {"updates": [update(identifier, origin="coordinator")]}
        writer = subprocess.Popen(
            [sys.executable, str(SCRIPT), *arguments],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=self.environment,
            text=True,
        )
        writer.stdin.write(json.dumps(answer))
        writer.stdin.close()
        return writer

    def test_a_writer_waits_while_another_process_holds_the_lock_on_the_directory(self):
        self.file.parent.mkdir()
        lock = os.open(self.file.parent, os.O_RDONLY)
        fcntl.flock(lock, fcntl.LOCK_EX)
        with self.writer("r1-design-1") as writer:
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    writer.wait(timeout=2)
                self.assertEqual(os.listdir(self.file.parent), [])
            finally:
                os.close(lock)
            self.assertEqual(writer.wait(timeout=60), 0)
        self.assertEqual(self.held(), [stored("r1-design-1")])

    def test_a_writer_that_sets_waits_for_the_lock_as_one_that_adds(self):
        self.hold(stored("r1-design-1"))
        lock = os.open(self.file.parent, os.O_RDONLY)
        fcntl.flock(lock, fcntl.LOCK_EX)
        with self.writer("r1-design-1", role="coordinator") as writer:
            try:
                with self.assertRaises(subprocess.TimeoutExpired):
                    writer.wait(timeout=2)
            finally:
                os.close(lock)
            self.assertEqual(writer.wait(timeout=60), 0)
        self.assertEqual(self.held(), [stored("r1-design-1", origin="coordinator")])

    def test_a_lock_held_past_the_deadline_is_a_failure_that_names_the_directory(self):
        before = self.hold(stored("r1-design-1"))
        answer = {"findings": [reported("r1-design-2")]}
        decide = functools.partial(findings.add, SCHEMA, answer=answer, round_found=1, lens="design")
        lock = os.open(self.file.parent, os.O_RDONLY)
        fcntl.flock(lock, fcntl.LOCK_EX)
        # A writer that outwaits its deadline gets the lock in the end, writes, and fails the test.
        release = threading.Timer(5, fcntl.flock, (lock, fcntl.LOCK_UN))
        release.start()
        try:
            with mock.patch.dict(os.environ, self.environment, clear=True):
                with mock.patch.object(findings, "LOCK_DEADLINE_SECONDS", 0.2):
                    started = time.monotonic()
                    with self.assertRaises(findings.Failure) as failure:
                        findings.rewrite(self.file, decide)
                    waited = time.monotonic() - started
        finally:
            release.cancel()
            release.join()
            os.close(lock)
        self.assertGreaterEqual(waited, 0.2)
        self.assertLess(waited, 10)
        self.assertIn(str(self.file.parent), str(failure.exception))
        self.assertEqual(os.listdir(self.file.parent), ["plan.json"])
        self.assertEqual(self.file.read_bytes(), before)

    def test_twenty_writers_at_once_lose_nothing_and_leave_no_other_file(self):
        writers = [self.writer(f"r1-design-{number}") for number in range(1, 21)]
        for writer in writers:
            with writer:
                self.assertEqual(writer.wait(timeout=60), 0)
        expected = sorted(f"r1-design-{number}" for number in range(1, 21))
        self.assertEqual(sorted(finding["id"] for finding in self.held()), expected)
        self.assertEqual(os.listdir(self.file.parent), ["plan.json"])

    def test_a_rejected_answer_leaves_no_other_file_beside_the_findings(self):
        self.hold(stored("r1-design-1"))
        self.assertRejected(self.add(reported("r1-design-1")))
        self.assertDone(self.add(reported("r1-design-2")))
        self.assertEqual(os.listdir(self.file.parent), ["plan.json"])

    def test_a_file_that_exists_keeps_its_mode(self):
        self.hold(stored("r1-design-1"))
        self.file.chmod(0o600)
        mask = os.umask(0o022)  # Under which a new file would be 0644.
        try:
            self.assertDone(self.add(reported("r1-design-2")))
        finally:
            os.umask(mask)
        self.assertEqual(stat.S_IMODE(self.file.stat().st_mode), 0o600)
        self.assertEqual(len(self.held()), 2)

    def test_the_new_content_replaces_the_file_from_a_temporary_file_of_the_same_directory(self):
        before = self.hold(stored("r1-design-1"))
        answer = {"findings": [reported("r1-design-2")]}
        decide = functools.partial(findings.add, SCHEMA, answer=answer, round_found=1, lens="design")
        # The replacement fails: the file is as it was, and the temporary file is gone.
        with mock.patch.dict(os.environ, self.environment, clear=True):
            with mock.patch.object(findings.os, "replace", side_effect=OSError("refused")) as replace:
                with self.assertRaises(OSError):
                    findings.rewrite(self.file, decide)
        temporary, replaced = (Path(argument) for argument in replace.call_args.args)
        self.assertEqual((temporary.parent, replaced), (self.file.parent, self.file))
        self.assertNotEqual(temporary, self.file)
        self.assertEqual(os.listdir(self.file.parent), ["plan.json"])
        self.assertEqual(self.file.read_bytes(), before)


class Authority(CommandLine):
    """A copy of the skill with another schema file behaves as its file says; the original does not."""

    def assertEveryCommandFails(self, script: Path) -> None:
        self.assertFailed(self.script("schema", script=script))
        self.assertFailed(self.script("schema", "--role", "reviewer", script=script))
        self.assertFailed(self.add(reported("r1-design-1"), script=script))
        self.assertFailed(
            self.set("coordinator", update("r1-design-1", origin="coordinator"), script=script)
        )
        self.assertFailed(self.script("summary", "--file", str(self.file), script=script))

    def test_a_value_added_to_an_enumeration_is_accepted_and_counted_by_the_copy_alone(self):
        copy = self.copy(lambda schema: schema["properties"]["severity"]["enum"].append("critical"))
        critical = reported("r1-design-1", severity="critical")
        self.assertRejected(self.add(critical))
        self.assertDone(self.add(critical, script=copy))
        role = self.assertDone(self.script("schema", "--role", "reviewer", script=copy))
        severity = role["properties"]["findings"]["items"]["properties"]["severity"]
        self.assertEqual(severity["enum"], SEVERITIES + ["critical"])
        counted = self.assertDone(self.script("summary", "--file", str(self.file), script=copy))
        expected = [{"round": 1, "blocking": 0, "major": 0, "minor": 0, "critical": 1}]
        self.assertEqual(counted["rounds"], expected)
        # Open, and neither blocking nor major.
        self.assertEqual(counted["open_serious"], 0)
        self.assertRejected(self.script("summary", "--file", str(self.file)))

    def test_a_subject_added_to_the_file_is_accepted_by_the_copy_alone(self):
        copy = self.copy(lambda schema: schema["properties"]["subject"]["enum"].append("tests"))
        about_tests = reported("r1-design-1", subject="tests")
        self.assertRejected(self.add(about_tests))
        self.assertDone(self.add(about_tests, script=copy))

    def test_the_order_of_the_keys_of_a_finding_follows_the_file(self):
        def put_the_lens_first(schema):
            schema["properties"] = {"lens": schema["properties"]["lens"]} | schema["properties"]

        self.assertDone(self.add(reported("r1-design-1"), script=self.copy(put_the_lens_first)))
        expected = ["lens"] + [field for field in FIELDS if field != "lens"]
        self.assertEqual(list(self.held()[0]), expected)

    def test_the_lens_of_a_call_is_judged_by_the_pattern_of_the_file(self):
        letters_only = {"pattern": "^[a-z]+$(?!\\n)"}
        copy = self.copy(lambda schema: schema["properties"]["lens"].update(letters_only))
        self.assertWrongCall(self.add(lens="a-b", script=copy))
        self.assertFalse(self.file.parent.exists())
        self.assertDone(self.add(lens="a-b"))

    def test_the_number_of_an_id_is_judged_by_the_pattern_of_the_file_alone(self):
        any_digits = {"pattern": "^r[1-9][0-9]*-[a-z][a-z0-9-]*-[0-9]+$(?!\\n)"}
        copy = self.copy(lambda schema: schema["properties"]["id"].update(any_digits))
        with_a_leading_zero = reported("r1-design-01")
        self.assertRejected(self.add(with_a_leading_zero))
        self.assertDone(self.add(with_a_leading_zero, script=copy))

    def test_a_value_removed_from_an_enumeration_is_rejected_and_not_counted_by_the_copy(self):
        copy = self.copy(lambda schema: schema["properties"]["disposition"]["enum"].remove("deferred"))
        self.hold(stored("r1-design-1"))
        deferred = update("r1-design-1", disposition="deferred")
        self.assertRejected(self.set("coordinator", deferred, script=copy))
        counted = self.assertDone(self.script("summary", "--file", str(self.file), script=copy))
        self.assertEqual(list(counted["dispositions"]), DISPOSITIONS[:-1])
        self.assertDone(self.set("coordinator", deferred))

    def test_a_field_moved_from_one_role_to_another_follows_the_file(self):
        def move_line_to_the_coordinator(schema):
            schema["x-roles"]["reviewer"]["adds"].remove("line")
            schema["x-roles"]["coordinator"]["sets"]["line"] = {}

        copy = self.copy(move_line_to_the_coordinator)
        role = self.assertDone(self.script("schema", "--role", "reviewer", script=copy))
        expected = sorted(set(REVIEWER_FIELDS) - {"line"})
        self.assertEqual(sorted(role["properties"]["findings"]["items"]["required"]), expected)
        self.assertRejected(self.add(reported("r1-design-1"), script=copy))
        without = {key: value for key, value in reported("r1-design-1").items() if key != "line"}
        self.assertDone(self.add(without, script=copy))
        self.assertEqual(self.held(), [stored("r1-design-1", line=None)])
        self.assertDone(self.set("coordinator", update("r1-design-1", line=12), script=copy))
        self.assertEqual(self.held(), [stored("r1-design-1", line=12)])
        self.assertRejected(self.set("coordinator", update("r1-design-1", line=13)))
        self.assertRejected(self.add(without, lens="security"))

    def test_the_values_that_a_role_may_write_and_change_follow_the_file(self):
        def widen_the_fixer(schema):
            change = schema["x-roles"]["fixer"]["sets"]["disposition"]
            change["to"].append("deferred")
            change["from"].append("declined")

        copy = self.copy(widen_the_fixer)
        self.hold(stored("r1-design-1"), stored("r1-design-2", disposition="declined"))
        deferred = update("r1-design-1", disposition="deferred")
        reopened = update("r1-design-2", disposition="fixed")
        self.assertRejected(self.set("fixer", deferred))
        self.assertRejected(self.set("fixer", reopened))
        self.assertDone(self.set("fixer", deferred, reopened, script=copy))
        self.assertEqual([finding["disposition"] for finding in self.held()], ["deferred", "fixed"])
        role = self.assertDone(self.script("schema", "--role", "fixer", script=copy))
        written = role["properties"]["updates"]["items"]["properties"]["disposition"]["enum"]
        self.assertEqual(written, ["fixed", "declined", "deferred"])

    def test_a_role_that_may_change_a_field_from_no_value_changes_it_from_none(self):
        def empty_the_values_to_change_from(schema):
            schema["x-roles"]["fixer"]["sets"]["disposition"]["from"] = []

        copy = self.copy(empty_the_values_to_change_from)
        before = self.hold(stored("r1-design-1"))
        fixed = update("r1-design-1", disposition="fixed")
        errors = self.assertRejected(self.set("fixer", fixed, script=copy))
        self.assertEqual([error["path"] for error in errors], ["answer.updates[0].disposition"])
        self.assertEqual(self.file.read_bytes(), before)

    def test_a_role_added_to_the_file_is_a_role_of_the_copy_alone(self):
        def add_an_auditor(schema):
            schema["x-roles"]["auditor"] = {"sets": {"origin": {"to": ["coordinator"]}}}

        copy = self.copy(add_an_auditor)
        self.hold(stored("r1-design-1"))
        valid = update("r1-design-1", origin="coordinator")
        self.assertWrongCall(self.set("auditor", valid))
        self.assertWrongCall(self.script("schema", "--role", "auditor"))
        self.assertRejected(self.set("auditor", update("r1-design-1", origin="fix-round"), script=copy))
        self.assertRejected(
            self.set("auditor", update("r1-design-1", disposition="fixed"), script=copy)
        )
        self.assertDone(self.set("auditor", valid, script=copy))
        self.assertEqual(self.held(), [stored("r1-design-1", origin="coordinator")])
        role = self.assertDone(self.script("schema", "--role", "auditor", script=copy))
        self.assertEqual(sorted(role["properties"]["updates"]["items"]["properties"]), ["id", "origin"])

    def test_a_finding_that_its_completion_makes_invalid_is_rejected(self):
        copy = self.copy(lambda schema: schema["properties"]["origin"]["enum"].remove(None))
        errors = self.assertRejected(self.add(reported("r1-design-1"), script=copy))
        self.assertEqual(errors, [{"path": "answer.findings[0].origin", "rule": "enum"}])
        self.assertFalse(self.file.parent.exists())

    def test_a_value_that_a_role_may_write_and_that_the_field_does_not_allow_is_rejected(self):
        def let_the_fixer_abandon(schema):
            schema["x-roles"]["fixer"]["sets"]["disposition"]["to"].append("abandoned")

        copy = self.copy(let_the_fixer_abandon)
        before = self.hold(stored("r1-design-1"))
        errors = self.assertRejected(
            self.set("fixer", update("r1-design-1", disposition="abandoned"), script=copy)
        )
        self.assertEqual(errors, [{"path": "answer.updates[0].disposition", "rule": "enum"}])
        self.assertEqual(self.file.read_bytes(), before)

    def test_a_keyword_outside_the_subset_makes_every_command_fail_and_nothing_is_written(self):
        copy = self.copy(lambda schema: schema["properties"]["summary"].update({"maxLength": 3}))
        self.assertEveryCommandFails(copy)
        self.assertFalse(self.file.parent.exists())
        before = self.hold(stored("r1-design-1"))
        self.assertEveryCommandFails(copy)
        self.assertEqual(self.file.read_bytes(), before)

    def test_a_schema_file_that_the_script_cannot_enforce_whole_is_a_failure(self):
        def with_property(name, value):
            return lambda schema: schema["properties"]["summary"].update({name: value})

        def with_role(role, rights):
            return lambda schema: schema["x-roles"].update({role: rights})

        cases = {
            "another keyword outside the subset": with_property("const", "x"),
            "a keyword outside the subset at the top": lambda schema: schema.update(
                {"minProperties": 1}
            ),
            "a key that starts with x and not with x-": lambda schema: schema.update({"xnote": "text"}),
            "a keyword outside the subset below items": with_property("items", {"format": "date"}),
            "additional properties that are allowed": lambda schema: schema.update(
                {"additionalProperties": True}
            ),
            "a type that the subset does not name": with_property("type", "number"),
            "a list of types with an unknown one": with_property("type", ["string", "text"]),
            "no type in a list of types": with_property("type", []),
            "a pattern that is not a regular expression": with_property("pattern", "("),
            "a pattern that is not text": with_property("pattern", 3),
            "a minimum that is not an integer": with_property("minimum", "1"),
            "required names that are not a list": lambda schema: schema.update({"required": "id"}),
            "an enumeration that is not a list": with_property("enum", "open"),
            "a description that is not text": with_property("description", 3),
            "a property that is not a schema": lambda schema: schema["properties"].update(
                {"note": "text"}
            ),
            "a right that the script does not know": with_role("fixer", {"set": {"disposition": {}}}),
            "a role that adds a field that is no property": with_role(
                "reviewer", {"adds": ["id", "note"]}
            ),
            "a role that sets a field that is no property": with_role("fixer", {"sets": {"note": {}}}),
            "a limit that the script does not know": with_role(
                "fixer", {"sets": {"origin": {"only": []}}}
            ),
            "a role that both adds and sets": with_role(
                "reviewer", {"adds": REVIEWER_FIELDS, "sets": {"carry_over_of": {}}}
            ),
            "adds on a role other than the reviewer": with_role("auditor", {"adds": ["id", "lens"]}),
            "a role that sets the id": with_role("fixer", {"sets": {"id": {}}}),
            "no reviewer": lambda schema: schema["x-roles"].pop("reviewer"),
            "no roles": lambda schema: schema.pop("x-roles"),
            "no severity": lambda schema: schema["properties"].pop("severity"),
            # The rules of the script read these fields of every finding, and assume their types.
            "a field that a rule names and that is not required": lambda schema: schema[
                "required"
            ].remove("carry_over_of"),
            "no required fields": lambda schema: schema.pop("required"),
            "an id with no type": lambda schema: schema["properties"]["id"].pop("type"),
            "a round of another type": lambda schema: schema["properties"]["round_found"].update(
                {"type": "string"}
            ),
            "a carry-over of another type": lambda schema: schema["properties"]["carry_over_of"].update(
                {"type": "string"}
            ),
            "a severity that is not text": lambda schema: schema["properties"]["severity"][
                "enum"
            ].append(3),
            "a disposition that is not text": lambda schema: schema["properties"]["disposition"][
                "enum"
            ].append(None),
            "an empty schema": lambda schema: schema.clear(),
        }
        self.hold(stored("r1-design-1"))
        for label, change in cases.items():
            with self.subTest(label):
                copy = self.copy(change)
                self.assertFailed(self.script("schema", script=copy))
                self.assertFailed(self.script("summary", "--file", str(self.file), script=copy))

    def test_a_schema_file_that_is_not_json_or_is_missing_makes_every_command_fail(self):
        for content in ("not json " + MARKER, "[]", None):
            with self.subTest(content=content):
                copy = self.copy(lambda schema: None)
                if content is None:
                    copy.with_name("finding.schema.json").unlink()
                else:
                    copy.with_name("finding.schema.json").write_text(content)
                self.assertEveryCommandFails(copy)
                self.assertFalse(self.file.parent.exists())

    def test_a_copy_of_the_skill_runs_alone_and_isolated_from_the_site_of_python(self):
        copy = self.copy(lambda schema: None)
        self.assertRegex(str(copy), r" \(1\) ")
        arguments = ["add", "--file", str(self.file), "--round", "1", "--lens", "design"]
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(copy), *arguments],
            input=json.dumps({"findings": [reported("r1-design-1")]}),
            env=self.environment,
            cwd=self.scratch,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(self.assertDone(result), {"added": ["r1-design-1"], "findings": 1})


class Decisions(unittest.TestCase):
    """The decision of each command, with plain values and no file."""

    def test_add_completes_each_finding_of_an_answer(self):
        answer = {"findings": [reported("r2-design-1"), reported("r2-design-2", file=None, line=None)]}
        document, printed = findings.add(SCHEMA, None, answer, 2, "design")
        expected = [stored("r2-design-1"), stored("r2-design-2", file=None, line=None)]
        self.assertEqual(document, {"findings": expected})
        self.assertEqual([list(finding) for finding in document["findings"]], [FIELDS, FIELDS])
        self.assertEqual(printed, {"added": ["r2-design-1", "r2-design-2"], "findings": 2})

    def test_add_rejects_an_id_of_the_file_and_names_the_finding_of_the_answer(self):
        document = {"findings": [stored("r1-design-1")]}
        with self.assertRaises(findings.Rejected) as rejected:
            findings.add(SCHEMA, document, {"findings": [reported("r1-design-1")]}, 1, "design")
        self.assertEqual(
            [error["path"] for error in rejected.exception.errors], ["answer.findings[0].id"]
        )
        self.assertEqual(document, {"findings": [stored("r1-design-1")]})

    def test_set_applies_the_updates_of_a_role_to_a_copy(self):
        document = {"findings": [stored("r1-design-1"), stored("r2-design-1")]}
        answer = {"updates": [{"id": "r2-design-1", "carry_over_of": "r1-design-1"}]}
        changed, printed = findings.set_(SCHEMA, document, answer, "coordinator")
        expected = [stored("r1-design-1"), stored("r2-design-1", carry_over_of="r1-design-1")]
        self.assertEqual(changed, {"findings": expected})
        self.assertEqual(printed, {"updated": ["r2-design-1"]})
        self.assertEqual(document, {"findings": [stored("r1-design-1"), stored("r2-design-1")]})

    def test_set_rejects_what_the_role_may_not_write(self):
        document = {"findings": [stored("r1-design-1", disposition="declined")]}
        for update in (
            {"id": "r1-design-1", "disposition": "fixed"},
            {"id": "r1-design-1", "origin": None},
        ):
            with self.subTest(update=update), self.assertRaises(findings.Rejected):
                findings.set_(SCHEMA, document, {"updates": [update]}, "fixer")

    def test_the_round_and_the_disposition_of_a_new_finding_are_never_those_of_the_answer(self):
        schema = json.loads(json.dumps(SCHEMA))
        schema["x-roles"]["reviewer"]["adds"] += ["round_found", "disposition"]
        given = reported("r2-design-1") | {"round_found": 9, "disposition": "fixed"}
        document, _ = findings.add(schema, None, {"findings": [given]}, 2, "design")
        self.assertEqual(document, {"findings": [stored("r2-design-1")]})

    def test_set_fails_without_a_file(self):
        with self.assertRaises(findings.Failure):
            findings.set_(SCHEMA, None, {"updates": []}, "fixer")

    def test_the_summary_counts_open_and_serious_findings_only(self):
        document = {
            "findings": [
                stored("r1-design-1", severity="minor"),
                stored("r1-design-2", severity="blocking", disposition="ruled"),
                stored("r2-design-1", severity="major", disposition="deferred"),
                stored("r2-design-2", severity="blocking"),
            ]
        }
        counted = findings.summary(SCHEMA, document)
        self.assertEqual(counted["open_serious"], 1)
        expected = [
            {"round": 1, "blocking": 1, "major": 0, "minor": 1},
            {"round": 2, "blocking": 1, "major": 1, "minor": 0},
        ]
        self.assertEqual(counted["rounds"], expected)
        self.assertEqual(
            counted["dispositions"],
            dict.fromkeys(DISPOSITIONS, 0) | {"open": 2, "ruled": 1, "deferred": 1},
        )
        self.assertEqual(list(counted["dispositions"]), DISPOSITIONS)

    def test_the_schema_of_a_role_holds_no_field_that_the_role_does_not_write(self):
        schema = json.loads(json.dumps(SCHEMA))
        schema["x-roles"] = {
            "reviewer": {"adds": ["id", "lens"]},
            "clerk": {"sets": {"fix": {"to": ["Done"]}}},
        }
        reviewer = findings.role_schema(schema, "reviewer")["properties"]["findings"]["items"]
        self.assertEqual(reviewer["properties"], {"id": PROPERTIES["id"], "lens": PROPERTIES["lens"]})
        self.assertEqual(reviewer["required"], ["id", "lens"])
        clerk = findings.role_schema(schema, "clerk")["properties"]["updates"]["items"]
        self.assertEqual(
            clerk["properties"], {"id": PROPERTIES["id"], "fix": PROPERTIES["fix"] | {"enum": ["Done"]}}
        )
        self.assertEqual(clerk["required"], ["id"])


if __name__ == "__main__":
    unittest.main()
