#!/usr/bin/env python3
"""Keep the findings of the reviews of one plan in one JSON file, under one schema.

    findings.py schema [--role ROLE]
    findings.py add --file FILE --round N --lens L      < the answer of one reviewer
    findings.py set --file FILE --role ROLE             < the answer of a fixer or of the coordinator
    findings.py summary --file FILE

`finding.schema.json`, beside this script, is the one authority on the fields of a finding, on
their values and, under "x-roles", on which role writes which field. It is read at each run and
must be written in the subset of JSON Schema that KEYWORDS lists.

A findings file is {"findings": [...]}. It is written only where git ignores it, whole or not at
all, under a lock on its directory.

Exit 0: done; the result is on standard output.
Exit 1: an answer or the findings file was read and rejected. Standard output holds
{"errors": [{"path": ..., "rule": ...}]}, and nothing was written. A path starts with "answer" or
with "file"; a rule is a keyword of the schema or the words of a rule of this script. No error
shows a value that it met.
Exit 2: the script could not do its job, or the call was wrong; standard output is empty.
"""

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
import sys
import time
from collections import Counter
from functools import partial
from pathlib import Path

SCHEMA_FILE = Path(__file__).with_name("finding.schema.json")

# The variables that choose a configuration file of git, and neither a repository nor a rule.
KEPT_FOR_GIT = ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_NOSYSTEM")

# How long a writer waits for the lock on the directory of the findings file before it gives up.
LOCK_DEADLINE_SECONDS = 60

TYPES = {
    "string": lambda value: isinstance(value, str),
    # In Python a bool is an int; in JSON true is not a number.
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "boolean": lambda value: isinstance(value, bool),
    "null": lambda value: value is None,
    "object": lambda value: isinstance(value, dict),
    "array": lambda value: isinstance(value, list),
}

# What the code itself needs of the schema file, written in the subset: the fields that its rules
# name, the values that the summary counts, and the role whose answer `add` takes.
SCHEMA_FORM = {
    "type": "object",
    "required": ["properties", "x-roles"],
    "properties": {
        "properties": {
            "type": "object",
            "required": [
                "id",
                "file",
                "line",
                "lens",
                "round_found",
                "disposition",
                "carry_over_of",
                "severity",
            ],
            "properties": {
                "severity": {"type": "object", "required": ["enum"]},
                "disposition": {"type": "object", "required": ["enum"]},
            },
        },
        "x-roles": {
            "type": "object",
            "required": ["reviewer"],
            "properties": {"reviewer": {"type": "object", "required": ["adds"]}},
        },
    },
}


class Failure(Exception):
    """The script cannot do its job: status 2, and one line on standard error."""


class Rejected(Exception):
    """An answer or a findings file breaks the schema or a rule: status 1, and the errors."""

    def __init__(self, errors: list[dict]):
        super().__init__(errors)
        self.errors = errors


def reject_if(errors: list[dict]) -> None:
    if errors:
        raise Rejected(errors)


def among(value, options: list) -> bool:
    """Whether `value` is one of `options` as JSON compares them: true is not 1."""
    return any(type(value) is type(option) and value == option for option in options)


def type_names(expected) -> list:
    """The type names of a "type" keyword, which is one name or a list of names."""
    return expected if isinstance(expected, list) else [expected]


def nothing(value, schema: dict, path: str) -> list[dict]:
    """The check of a keyword that only describes."""
    return []


def type_errors(value, schema: dict, path: str) -> list[dict]:
    if any(TYPES[name](value) for name in type_names(schema["type"])):
        return []
    return [{"path": path, "rule": "type"}]


def property_errors(value, schema: dict, path: str) -> list[dict]:
    if not isinstance(value, dict):
        return []
    errors = []
    for name, property_schema in schema["properties"].items():
        if name in value:
            errors += validate(value[name], property_schema, f"{path}.{name}")
    return errors


def required_errors(value, schema: dict, path: str) -> list[dict]:
    if not isinstance(value, dict):
        return []
    return [
        {"path": f"{path}.{name}", "rule": "required"}
        for name in schema["required"]
        if name not in value
    ]


def additional_errors(value, schema: dict, path: str) -> list[dict]:
    """The error of an object with a key that "properties" does not name. The key is not shown."""
    if not isinstance(value, dict) or value.keys() <= schema.get("properties", {}).keys():
        return []
    return [{"path": path, "rule": "additionalProperties"}]


def item_errors(value, schema: dict, path: str) -> list[dict]:
    if not isinstance(value, list):
        return []
    errors = []
    for index, item in enumerate(value):
        errors += validate(item, schema["items"], f"{path}[{index}]")
    return errors


def enum_errors(value, schema: dict, path: str) -> list[dict]:
    return [] if among(value, schema["enum"]) else [{"path": path, "rule": "enum"}]


def pattern_errors(value, schema: dict, path: str) -> list[dict]:
    """Searched, not matched, and only in a string. `$` also matches before a final line break,
    so a pattern of the schema file that must reach the end is written `$(?!\\n)`."""
    if not isinstance(value, str) or re.search(schema["pattern"], value):
        return []
    return [{"path": path, "rule": "pattern"}]


def minimum_errors(value, schema: dict, path: str) -> list[dict]:
    """Checked only on an integer: NaN, which Python reads from JSON, is below no minimum."""
    if not TYPES["integer"](value) or value >= schema["minimum"]:
        return []
    return [{"path": path, "rule": "minimum"}]


def compiles(pattern) -> bool:
    try:
        re.compile(pattern)
    except (re.error, TypeError):
        return False
    return True


# The subset of JSON Schema that the schema file is written in, and all that this script checks.
# For each keyword: whether its value is written as the subset allows, and the check that it asks
# for, which returns the errors of a value. A key that starts with "x-" is outside the table.
KEYWORDS = {
    "$schema": (TYPES["string"], nothing),
    "title": (TYPES["string"], nothing),
    "description": (TYPES["string"], nothing),
    "type": (
        lambda expected: (
            bool(type_names(expected))
            and all(isinstance(name, str) and name in TYPES for name in type_names(expected))
        ),
        type_errors,
    ),
    "properties": (TYPES["object"], property_errors),
    "required": (
        lambda names: isinstance(names, list) and all(isinstance(name, str) for name in names),
        required_errors,
    ),
    "additionalProperties": (lambda allowed: allowed is False, additional_errors),
    "items": (TYPES["object"], item_errors),
    "enum": (TYPES["array"], enum_errors),
    "pattern": (compiles, pattern_errors),
    "minimum": (TYPES["integer"], minimum_errors),
}


def validate(value, schema: dict, path: str) -> list[dict]:
    """The errors of `value` against `schema`, which is written in the subset."""
    errors = []
    for keyword in schema:
        if not keyword.startswith("x-"):
            errors += KEYWORDS[keyword][1](value, schema, path)
    return errors


def outside_subset(schema, path: str):
    """Yield the path of each keyword of `schema` that the subset lacks or writes otherwise."""
    if not isinstance(schema, dict):
        yield path
        return
    for keyword, expected in schema.items():
        if keyword.startswith("x-"):
            continue
        if keyword not in KEYWORDS or not KEYWORDS[keyword][0](expected):
            yield f"{path}.{keyword}"
        elif keyword == "properties":
            for name, property_schema in expected.items():
                yield from outside_subset(property_schema, f"{path}.properties.{name}")
        elif keyword == "items":
            yield from outside_subset(expected, f"{path}.items")


def usable(schema) -> dict:
    """`schema`, the content of the schema file, when this script can enforce all of it.

    A rule that the code would ignore is a failure: a keyword outside the subset, or a right under
    "x-roles" that is not in the form {"adds": [fields]} or {"sets": {field: {"from", "to"}}}.
    """
    faults = [{"path": path, "rule": "outside the subset"} for path in outside_subset(schema, "schema")]
    faults = faults or validate(schema, SCHEMA_FORM, "schema")
    if not faults:
        change = {
            "type": "object",
            "properties": {"from": {"type": "array"}, "to": {"type": "array"}},
            "additionalProperties": False,
        }
        rights = {
            "type": "object",
            "properties": {
                "adds": {"type": "array", "items": {"enum": list(schema["properties"])}},
                "sets": {
                    "type": "object",
                    "properties": dict.fromkeys(schema["properties"], change),
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
        }
        for role in schema["x-roles"]:
            faults += validate(schema["x-roles"][role], rights, f"schema.x-roles.{role}")
    if faults:
        raise Failure(f"{SCHEMA_FILE}: {faults[0]['path']}: {faults[0]['rule']}")
    return schema


def listing(key: str, items: dict) -> dict:
    """The schema of an object whose one key holds a list of `items`."""
    return {
        "type": "object",
        "properties": {key: {"type": "array", "items": items}},
        "required": [key],
        "additionalProperties": False,
    }


def role_schema(schema: dict, role: str) -> dict:
    """The schema of the answer of `role`, derived from its rights under "x-roles".

    A role that adds answers {"findings": [...]}, each finding with the fields that it adds, all
    required. Any other role answers {"updates": [...]}, each update with `id` and the fields that
    the role sets, limited to the values that it may write.
    """
    properties, rights = schema["properties"], schema["x-roles"][role]
    if "adds" in rights:
        key, required = "findings", rights["adds"]
        fields = {field: properties[field] for field in rights["adds"]}
    else:
        key, required = "updates", ["id"]
        fields = {"id": properties["id"]}
        for field, change in rights.get("sets", {}).items():
            fields[field] = properties[field] | ({"enum": change["to"]} if "to" in change else {})
    items = {
        "type": "object",
        "properties": fields,
        "required": required,
        "additionalProperties": False,
    }
    return listing(key, items)


def rule_errors(entries: list[tuple[str, dict]]) -> list[dict]:
    """The errors of findings that each hold the schema, against the rules that no schema states.

    `entries` pairs each finding with its path. An id is unique, `line` is null where `file` is
    null, and `carry_over_of` is null or the id of a finding of an earlier round.
    """
    errors, by_id = [], {}
    for path, finding in entries:
        if finding["id"] in by_id:
            errors.append({"path": f"{path}.id", "rule": "unique among the findings"})
        by_id.setdefault(finding["id"], finding)
        if finding["file"] is None and finding["line"] is not None:
            errors.append({"path": f"{path}.line", "rule": "null when file is null"})
    for path, finding in entries:
        earlier = finding["carry_over_of"]
        if earlier is None:
            continue
        # A finding is not of an earlier round than itself.
        if earlier not in by_id or by_id[earlier]["round_found"] >= finding["round_found"]:
            rule = "null, or the id of a finding of an earlier round"
            errors.append({"path": f"{path}.carry_over_of", "rule": rule})
    return errors


def entries_of(schema: dict, document) -> list[tuple[str, dict]]:
    """The findings of the content of a findings file, each with its path, once the whole is valid."""
    reject_if(validate(document, listing("findings", schema), "file"))
    entries = [
        (f"file.findings[{index}]", finding) for index, finding in enumerate(document["findings"])
    ]
    reject_if(rule_errors(entries))
    return entries


def document_of(schema: dict, entries: list[tuple[str, dict]]) -> dict:
    """The content of a findings file: every finding with its keys in the order of the schema."""
    order = schema["properties"]
    return {
        "findings": [
            {name: finding[name] for name in order if name in finding} for _, finding in entries
        ]
    }


def add(schema: dict, document, answer, round_found: int, lens: str) -> tuple[dict, dict]:
    """The findings file once the answer of one reviewer is added, and what to print.

    `document` is the content of the file, or None when there is no file yet. Each finding takes
    the round as `round_found`, "open" as `disposition`, and null for every other field that the
    reviewer does not add.
    """
    entries = entries_of(schema, {"findings": []} if document is None else document)
    reject_if(validate(answer, role_schema(schema, "reviewer"), "answer"))
    expected_id = re.compile(rf"r{round_found}-{re.escape(lens)}-[1-9][0-9]*")
    errors, added = [], []
    for index, given in enumerate(answer["findings"]):
        path = f"answer.findings[{index}]"
        finding = dict.fromkeys(schema["properties"]) | given
        finding |= {"round_found": round_found, "disposition": "open"}
        if finding["lens"] != lens:
            errors.append({"path": f"{path}.lens", "rule": "the lens given to add"})
        if not (isinstance(finding["id"], str) and expected_id.fullmatch(finding["id"])):
            rule = "r<round>-<lens>-<number>, with the round and the lens given to add"
            errors.append({"path": f"{path}.id", "rule": rule})
        errors += validate(finding, schema, path)
        entries.append((path, finding))
        added.append(finding["id"])
    reject_if(errors)
    reject_if(rule_errors(entries))
    return document_of(schema, entries), {"added": added, "findings": len(entries)}


def set_(schema: dict, document, answer, role: str) -> tuple[dict, dict]:
    """The findings file once the updates of one answer of `role` are applied, and what to print.

    `document` is the content of the file, or None when there is no file: `set` creates none.
    """
    if document is None:
        raise Failure("set changes a findings file, and this one does not exist")
    entries = entries_of(schema, document)
    reject_if(validate(answer, role_schema(schema, role), "answer"))
    rights = schema["x-roles"][role].get("sets", {})
    positions = {finding["id"]: position for position, (_, finding) in enumerate(entries)}
    errors, updated = [], []
    for index, update in enumerate(answer["updates"]):
        path = f"answer.updates[{index}]"
        # Popped, so that a second update of the same finding finds nothing.
        position = positions.pop(update["id"], None)
        if position is None:
            rule = "the id of a finding of the file, once in an answer"
            errors.append({"path": f"{path}.id", "rule": rule})
            continue
        finding = entries[position][1]
        if len(update) == 1:
            errors.append({"path": path, "rule": "sets at least one field"})
        for field in sorted(update.keys() - {"id"}):
            if "from" in rights[field] and not among(finding.get(field), rights[field]["from"]):
                rule = "the role does not change this field from its current value"
                errors.append({"path": f"{path}.{field}", "rule": rule})
        entries[position] = (path, finding | update)
        errors += validate(entries[position][1], schema, path)
        updated.append(update["id"])
    reject_if(errors)
    reject_if(rule_errors(entries))
    return document_of(schema, entries), {"updated": updated}


def summary(schema: dict, document) -> dict:
    """The counts of a findings file: per round and severity, per disposition, and open and serious."""
    findings = [finding for _, finding in entries_of(schema, document)]
    properties = schema["properties"]
    by_round = Counter((finding["round_found"], finding["severity"]) for finding in findings)
    by_disposition = Counter(finding["disposition"] for finding in findings)
    return {
        "rounds": [
            {"round": number}
            | {severity: by_round[number, severity] for severity in properties["severity"]["enum"]}
            for number in sorted({finding["round_found"] for finding in findings})
        ],
        "dispositions": {name: by_disposition[name] for name in properties["disposition"]["enum"]},
        # Serious means blocking or major.
        "open_serious": sum(
            finding["disposition"] == "open" and finding["severity"] in ("blocking", "major")
            for finding in findings
        ),
    }


def parse(data: bytes, name):
    """The JSON value that `data` holds in UTF-8; `name` says in a failure where it was read.

    A value that could not be written back is a failure here, before any effect: an escape of JSON
    can name half of a surrogate pair, which UTF-8 does not hold.
    """
    try:
        # `int` refuses NaN and Infinity, which are not JSON and which Python would accept.
        value = json.loads(data.decode("utf-8"), parse_constant=int)
        json.dumps(value, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise Failure(f"{name}: half of a surrogate pair, which UTF-8 does not hold") from None
    except (ValueError, RecursionError):
        # RecursionError: lists or objects nested deeper than Python reads.
        raise Failure(f"{name}: not JSON") from None
    return value


def rewrite(path: Path, decide):
    """Replace the findings file `path` by what `decide` makes of it, and return what to print.

    `decide` takes the content of the file, or None when there is no file, and returns the new
    content and what to print. Nothing is created unless git says that it ignores `path` and the
    temporary file beside it that the write goes through: findings can quote a private repository,
    so a wrong yes would put private text in a commit. The directory of the file is locked from the
    read to the replacement, so that writers wait for each other and no lock file is left; a writer
    that waits LOCK_DEADLINE_SECONDS for the lock gives up with a failure. A file that exists keeps
    its mode.
    """
    nearest = path.parent
    while not nearest.is_dir():
        nearest = nearest.parent
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith("GIT_") or name in KEPT_FOR_GIT
    }
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    for candidate in (path, temporary):
        command = ["git", "check-ignore", "-q", str(candidate)]
        try:
            subprocess.run(
                command, cwd=nearest, env=environment, capture_output=True, timeout=10, check=True
            )
        except (OSError, subprocess.SubprocessError):
            raise Failure(f"{candidate}: git does not say that it ignores this file") from None
    if nearest != path.parent:
        decide(None)  # An answer that is rejected leaves no directory behind.
        path.parent.mkdir(parents=True, exist_ok=True)
    lock = os.open(path.parent, os.O_RDONLY)
    try:
        deadline = time.monotonic() + LOCK_DEADLINE_SECONDS
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    held = f"locked by another process for {LOCK_DEADLINE_SECONDS} seconds"
                    raise Failure(f"{path.parent}: {held}") from None
                time.sleep(0.05)
        existing = path.stat() if path.exists() else None
        document, output = decide(None if existing is None else parse(path.read_bytes(), path))
        try:
            text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
            temporary.write_text(text, encoding="utf-8")
            if existing is not None:
                os.chmod(temporary, stat.S_IMODE(existing.st_mode))
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    finally:
        os.close(lock)
    return output


def allowed(form: dict, convert=str):
    """A type for argparse: the argument, converted, when it holds `form`. Its error shows no value."""

    def argument(text: str):
        try:
            value = convert(text)
        except ValueError:
            value = None
        if validate(value, form, "argument"):
            raise argparse.ArgumentTypeError("not a value that finding.schema.json allows here")
        return value

    return argument


def main() -> int:
    try:
        source = SCHEMA_FILE.read_bytes()
        schema = usable(parse(source, SCHEMA_FILE))
        roles, properties = schema["x-roles"], schema["properties"]
        parser = argparse.ArgumentParser(
            prog="findings.py", description="Keep the findings of the reviews of one plan in one file."
        )
        commands = parser.add_subparsers(dest="command", required=True)
        command = commands.add_parser(
            "schema", help="print the schema file, or the schema of an answer"
        )
        command.add_argument("--role", type=allowed({"enum": list(roles)}))
        command = commands.add_parser(
            "add", help="add the answer of one reviewer, read on standard input"
        )
        command.add_argument("--file", required=True, type=Path)
        command.add_argument("--round", required=True, type=allowed(properties["round_found"], int))
        command.add_argument("--lens", required=True, type=allowed(properties["lens"]))
        command = commands.add_parser(
            "set", help="apply the updates of one answer, read on standard input"
        )
        command.add_argument("--file", required=True, type=Path)
        setters = [role for role in roles if "sets" in roles[role]]
        command.add_argument("--role", required=True, type=allowed({"enum": setters}))
        command = commands.add_parser("summary", help="count the findings of a file")
        command.add_argument("--file", required=True, type=Path)
        arguments = parser.parse_args()
        if arguments.command == "schema" and arguments.role is None:
            output = source.decode("utf-8")
        elif arguments.command == "schema":
            output = json.dumps(role_schema(schema, arguments.role), indent=2) + "\n"
        elif arguments.command == "summary":
            document = parse(arguments.file.read_bytes(), arguments.file)
            output = json.dumps(summary(schema, document)) + "\n"
        else:
            answer = parse(sys.stdin.buffer.read(), "standard input")
            if arguments.command == "add":
                decide = partial(
                    add, schema, answer=answer, round_found=arguments.round, lens=arguments.lens
                )
            else:
                decide = partial(set_, schema, answer=answer, role=arguments.role)
            output = json.dumps(rewrite(arguments.file.resolve(), decide)) + "\n"
    except Rejected as rejected:
        print(json.dumps({"errors": rejected.errors}))
        return 1
    except (Failure, OSError) as failure:
        print(f"findings.py: {failure}", file=sys.stderr)
        return 2
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
