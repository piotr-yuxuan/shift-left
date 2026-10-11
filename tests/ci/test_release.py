"""The release script: its decision as a table of cases, and the script whole.

The expectations come from the contract that the script states. A release is four writes, in
this order: the version commit, the release with its tag, the deployment record, its status.
A run makes only those that are missing, and none where `main` has moved with no version
commit. Status 1 when a call is refused, and no call follows it. Status 2, one line on standard
error and nothing written, for a version of another form, a tag that is in the way and a root
manifest with no top-level version.

The script whole runs in a clone of a scratch bare repository that plays `origin`, with a
stand-in `gh` first on PATH: it records each call and answers as the test tells it. Where a
case needs what GitHub would have done to `origin`, the test does it.

The tests need `git` 2.42 or later and `python3` on PATH.
"""

import base64
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CI = Path(__file__).resolve().parents[2] / "ci"
SCRIPT = CI / "release.py"
NEXT_VERSION = CI / "next_version.py"

PUSHED = "a" * 40
MADE = "b" * 40
OTHER = "c" * 40
WRITES = ("commit", "release", "deployment", "status")

# A root manifest with a second `version`, deeper, and an indent of four spaces.
MANIFEST = """\
{
    "name": "first",
    "extensions": {
        "version": "0.0.0"
    },
    "version": "0.0.0"
}
"""
MANIFEST_AT_0_0_2 = """\
{
    "name": "first",
    "extensions": {
        "version": "0.0.0"
    },
    "version": "0.0.2"
}
"""

STAND_IN = """\
import json
import os
import sys
from pathlib import Path

directory = Path(os.environ["GH_STAND_IN"])
call = {"arguments": sys.argv[1:], "stdin": sys.stdin.read()}
with (directory / "calls.jsonl").open("a") as calls:
    calls.write(json.dumps(call) + "\\n")
text = " ".join(call["arguments"]) + "\\n" + call["stdin"]
for answer in json.loads((directory / "answers.json").read_text()):
    if all(word in text for word in answer["when"]):
        sys.stdout.write(answer.get("stdout", ""))
        sys.stderr.write(answer.get("stderr", ""))
        sys.exit(answer.get("status", 0))
sys.exit("stand-in gh: the test gave no answer for this call")
"""


def loaded(script: Path):
    """The script as a module, for its decision function. It imports its neighbour by name."""
    sys.path.insert(0, str(script.parent))
    try:
        spec = importlib.util.spec_from_file_location(script.stem, script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(script.parent))
    return module


release = loaded(SCRIPT)


def found(**changes):
    """What a run finds when an earlier run made the version commit and nothing else.

    `.version` holds 0.0.1 at the pushed commit, and the tag of that version is elsewhere.
    """
    version_commit = release.Commit(
        hash=MADE,
        parents=(PUSHED,),
        message="Version 0.0.2\n\n[skip ci]",
        changed=frozenset({".version"}),
    )
    base = {
        "pushed": PUSHED,
        "head": MADE,
        "version": "0.0.1\n",
        "manifests": {},
        "tags": {"0.0.1": OTHER},
        "successor": version_commit,
    }
    return release.Found(**(base | changes))


def successor(**changes):
    return release.Commit(**(vars(found().successor) | changes))


class Decision(unittest.TestCase):
    def test_main_at_the_pushed_commit_gets_the_four_writes(self):
        decision = release.decide(found(head=PUSHED, successor=None))
        self.assertEqual(decision.writes, WRITES)
        self.assertEqual(decision.version, "0.0.2")
        self.assertEqual(decision.files, {".version": "0.0.2\n"})
        self.assertIsNone(decision.made)

    def test_a_version_commit_of_an_earlier_run_gets_what_is_missing(self):
        cases = (
            ({}, WRITES[1:]),
            ({"tags": {"0.0.2": MADE}}, WRITES[1:]),
            ({"release": True}, WRITES[2:]),
            ({"release": True, "deployment": 41}, WRITES[3:]),
        )
        for changes, writes in cases:
            with self.subTest(changes=changes):
                decision = release.decide(found(**changes))
                self.assertEqual(decision.writes, writes)
                self.assertEqual(decision.made, MADE)

    def test_a_version_commit_that_changed_a_root_manifest_too_is_one(self):
        changes = {
            "manifests": {"plugins/first/plugin.json": MANIFEST},
            "successor": successor(changed=frozenset({".version", "plugins/first/plugin.json"})),
        }
        decision = release.decide(found(**changes))
        self.assertEqual(decision.writes, WRITES[1:])
        self.assertEqual(decision.made, MADE)

    def test_a_release_that_is_complete_gets_no_write(self):
        decision = release.decide(found(release=True, deployment=41, success=True))
        self.assertEqual(decision.writes, ())
        self.assertEqual(decision.made, MADE)

    def test_main_that_moved_with_no_version_commit_gets_no_write(self):
        cases = {
            "another message": successor(message="Add a feature"),
            "the message of another version": successor(message="Version 0.0.3\n\n[skip ci]"),
            "a body of its own": successor(message="Version 0.0.2\n\n[skip ci]\n\nAnd more."),
            "two parents": successor(parents=(PUSHED, OTHER)),
            "another parent": successor(parents=(OTHER,)),
            "another file changed": successor(changed=frozenset({".version", "README.md"})),
            "no commit after the pushed one": None,
        }
        for name, after in cases.items():
            with self.subTest(name):
                decision = release.decide(found(successor=after))
                self.assertEqual(decision.writes, ())
                self.assertIsNone(decision.made)

    def test_what_may_not_be_written_is_refused(self):
        cases = {
            "a version of two numbers": found(version="1.0\n"),
            "a version of two numbers, main at the pushed commit": found(
                head=PUSHED, successor=None, version="1.0\n"
            ),
            "main at the pushed commit and the tag of the next version exists": found(
                head=PUSHED, successor=None, tags={"0.0.1": OTHER, "0.0.2": OTHER}
            ),
            "the tag of the next version on another commit": found(tags={"0.0.2": OTHER}),
            "a root manifest that is not JSON": found(manifests={"plugins/first/plugin.json": "{"}),
            "a root manifest with no top-level version": found(
                manifests={"plugins/first/plugin.json": '{"extensions": {"version": "0.0.0"}}'}
            ),
            "a root manifest whose version is a number": found(
                head=PUSHED, successor=None, manifests={"plugins/first/plugin.json": '{"version": 1}'}
            ),
        }
        for name, case in cases.items():
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    release.decide(case)

    def test_the_version_commit_sets_the_top_level_version_of_a_root_manifest(self):
        manifests = {"plugins/first/plugin.json": MANIFEST}
        decision = release.decide(found(head=PUSHED, successor=None, manifests=manifests))
        self.assertEqual(
            decision.files, {".version": "0.0.2\n", "plugins/first/plugin.json": MANIFEST_AT_0_0_2}
        )


class Whole(unittest.TestCase):
    """The script, in a clone of a scratch `origin`, with a stand-in `gh`."""

    def setUp(self):
        self.scratch = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        for name in ("home", "bin", "gh"):
            (self.scratch / name).mkdir()
        stand_in = self.scratch / "bin" / "gh"
        stand_in.write_text(f"#!{sys.executable}\n{STAND_IN}")
        stand_in.chmod(0o755)
        # Built from nothing, so that no variable and no configuration of the caller
        # reaches git or the script.
        self.environment = {
            "PATH": f"{self.scratch / 'bin'}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.scratch / "home"),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Tests",
            "GIT_AUTHOR_EMAIL": "tests@example.invalid",
            "GIT_COMMITTER_NAME": "Tests",
            "GIT_COMMITTER_EMAIL": "tests@example.invalid",
            "GH_STAND_IN": str(self.scratch / "gh"),
            "GITHUB_REPOSITORY": "owner/name",
        }
        self.origin = self.scratch / "origin.git"
        self.owner = self.scratch / "owner"
        self.runner = self.scratch / "runner"
        self.git(self.scratch, "init", "--quiet", "--bare", "--initial-branch=main", str(self.origin))
        self.git(self.scratch, "clone", "--quiet", str(self.origin), str(self.owner))
        # The release 0.0.1, then what the push holds: two commits and the merge of a branch.
        self.push("Fixture", **{".version": "0.0.0\n"})
        self.push("Version 0.0.1\n\n[skip ci]", **{".version": "0.0.1\n"})
        self.git(self.owner, "tag", "0.0.1")
        self.push("Add a feature", feature="one\n")
        self.git(self.owner, "switch", "--quiet", "--create", "topic")
        self.push("Fix the topic", topic="one\n")
        self.git(self.owner, "switch", "--quiet", "main")
        self.git(self.owner, "merge", "--quiet", "--no-ff", "--message=Merge branch 'topic'", "topic")
        self.pushed = self.push("Polish it", feature="two\n")
        self.answers()

    def git(self, directory: Path, *arguments: str) -> str:
        command = ["git", "-C", str(directory), *arguments]
        done = subprocess.run(command, env=self.environment, check=True, capture_output=True, text=True)
        return done.stdout.strip()

    def push(self, message: str, **files: str) -> str:
        """Commit `files` in the clone of the owner and push its branch and tags; the commit."""
        for path, text in files.items():
            (self.owner / path).parent.mkdir(parents=True, exist_ok=True)
            # As bytes, so that a file keeps the line ends that its case gives it.
            (self.owner / path).write_bytes(text.encode())
        self.git(self.owner, "add", "--all")
        self.git(self.owner, "commit", "--quiet", "--message", message)
        self.git(self.owner, "push", "--quiet", "--tags", "origin", "HEAD")
        return self.git(self.owner, "rev-parse", "HEAD")

    def answers(self, refused: str = "", release: bool = False, deployments=(), statuses=()) -> None:
        """Tell the stand-in what GitHub answers: it refuses the call that holds `refused`,
        and holds for 0.0.2 the release, the deployment records and the statuses given.

        It answers by what it is asked. A call that names another tag is told that this tag has
        no release. A list of the records that does not ask for those of 0.0.2 in the
        environment `release` gets the record 7, which is of another release and has a success.
        """
        made = {"data": {"createCommitOnBranch": {"commit": {"oid": MADE}}}}
        held = {"data": {"repository": {"release": {"tagName": "0.0.2"} if release else None}}}
        none = {"data": {"repository": {"release": None}}}
        the_records_asked_for = ["/deployments", "ref=0.0.2", "environment=release"]
        rules = [
            {"when": [refused or "nothing"], "status": 1, "stderr": "gh: Bad Gateway (HTTP 502)\n"},
            {"when": ["createCommitOnBranch"], "stdout": json.dumps(made)},
            {"when": ["release create"], "stdout": "https://github.invalid/owner/name/0.0.2\n"},
            {"when": ["POST", "/statuses"], "stdout": json.dumps({"state": "success"})},
            {"when": ["POST", "/deployments"], "stdout": json.dumps({"id": 41})},
            {"when": ["release(tagName", '"0.0.2"'], "stdout": json.dumps(held)},
            {"when": ["release(tagName"], "stdout": json.dumps(none)},
            {"when": ["/deployments/7/statuses"], "stdout": json.dumps([{"state": "success"}])},
            {"when": ["/statuses"], "stdout": json.dumps(list(statuses))},
            {"when": the_records_asked_for, "stdout": json.dumps(list(deployments))},
            {"when": ["/deployments"], "stdout": json.dumps([{"id": 7}])},
        ]
        (self.scratch / "gh" / "answers.json").write_text(json.dumps(rules))

    def release(self, **environment: str) -> subprocess.CompletedProcess[str]:
        """Run the script for the pushed commit, in a clone as a runner has it."""
        if not self.runner.exists():
            self.git(self.scratch, "clone", "--quiet", str(self.origin), str(self.runner))
        (self.scratch / "gh" / "calls.jsonl").write_text("")
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=self.runner,
            env=self.environment | {"GITHUB_SHA": self.pushed} | environment,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def calls(self) -> list[dict]:
        """The calls of the last run, each with the write that it is, or `read`."""
        calls = []
        for line in (self.scratch / "gh" / "calls.jsonl").read_text().splitlines():
            call = json.loads(line)
            text = " ".join(call["arguments"])
            if "createCommitOnBranch" in call["stdin"]:
                call["write"] = "commit"
            elif text.startswith("release create"):
                call["write"] = "release"
            elif "POST" in text:
                call["write"] = "status" if "/statuses" in text else "deployment"
            else:
                call["write"] = "read"
            calls.append(call)
        return calls

    def assertRefused(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(len(result.stderr.splitlines()), 1, result.stderr)
        self.assertEqual([call["write"] for call in self.calls() if call["write"] != "read"], [])

    def test_a_push_that_main_still_points_at_is_released(self):
        result = self.release()
        self.assertEqual(result.returncode, 0, result.stderr)
        commit, created, deployment, status = self.calls()
        self.assertEqual([call["write"] for call in self.calls()], list(WRITES))

        self.assertEqual(commit["arguments"][-2:], ["--input", "-"])
        change = json.loads(commit["stdin"])["variables"]["input"]
        branch = {"repositoryNameWithOwner": "owner/name", "branchName": "main"}
        self.assertEqual(change["branch"], branch)
        self.assertEqual(change["expectedHeadOid"], self.pushed)
        self.assertEqual(change["message"], {"headline": "Version 0.0.2", "body": "[skip ci]"})
        (addition,) = change["fileChanges"]["additions"]
        self.assertEqual(addition["path"], ".version")
        version = self.scratch / "version"
        version.write_bytes(base64.b64decode(addition["contents"], validate=True))
        self.assertEqual(version.read_text(), "0.0.2\n")
        command = [sys.executable, str(NEXT_VERSION), str(version)]
        accepted = subprocess.run(command, capture_output=True, text=True, timeout=60)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

        arguments = created["arguments"]
        self.assertEqual(arguments[:3], ["release", "create", "0.0.2"])
        options = dict(zip(arguments[3::2], arguments[4::2], strict=True))
        self.assertEqual(options["--target"], MADE)
        self.assertEqual(options["--title"], "0.0.2")
        self.assertEqual(options["--notes-file"], "-")
        # The titles since the tag before, the merge left out.
        notes = sorted(created["stdin"].splitlines())
        self.assertEqual(notes, ["- Add a feature", "- Fix the topic", "- Polish it"])

        self.assertIn("repos/owner/name/deployments", deployment["arguments"])
        self.assertEqual(deployment["arguments"][-2:], ["--input", "-"])
        self.assertEqual(
            json.loads(deployment["stdin"]),
            {"ref": "0.0.2", "environment": "release", "auto_merge": False, "required_contexts": []},
        )
        self.assertIn("repos/owner/name/deployments/41/statuses", status["arguments"])
        self.assertEqual(status["arguments"][-2:], ["--input", "-"])
        self.assertEqual(json.loads(status["stdin"]), {"state": "success"})

    def test_the_first_release_has_the_titles_of_the_whole_history(self):
        self.git(self.owner, "push", "--quiet", "origin", "--delete", "refs/tags/0.0.1")
        self.assertEqual(self.release().returncode, 0)
        notes = sorted(self.calls()[1]["stdin"].splitlines())
        titles = ["- Add a feature", "- Fix the topic", "- Fixture", "- Polish it", "- Version 0.0.1"]
        self.assertEqual(notes, titles)

    def test_a_release_that_stopped_after_its_commit_is_finished_by_a_second_run(self):
        self.answers(refused="release create")
        first = self.release()
        self.assertEqual(first.returncode, 1, first.stdout)
        self.assertEqual([call["write"] for call in self.calls()], ["commit", "release"])
        self.assertIn("HTTP 502", first.stderr)

        # What GitHub did at the first run: the version commit, on the pushed one.
        made = self.push("Version 0.0.2\n\n[skip ci]", **{".version": "0.0.2\n"})
        self.answers()
        second = self.release()
        self.assertEqual(second.returncode, 0, second.stderr)
        writes = [call for call in self.calls() if call["write"] != "read"]
        self.assertEqual([call["write"] for call in writes], list(WRITES[1:]))
        arguments = writes[0]["arguments"]
        self.assertEqual(arguments[arguments.index("--target") + 1], made)
        notes = sorted(writes[0]["stdin"].splitlines())
        self.assertEqual(notes, ["- Add a feature", "- Fix the topic", "- Polish it"])

    def test_a_tag_that_was_made_without_its_release_gets_its_release(self):
        made = self.push("Version 0.0.2\n\n[skip ci]", **{".version": "0.0.2\n"})
        self.git(self.owner, "tag", "0.0.2", made)
        self.git(self.owner, "push", "--quiet", "--tags", "origin")
        result = self.release()
        self.assertEqual(result.returncode, 0, result.stderr)
        writes = [call for call in self.calls() if call["write"] != "read"]
        self.assertEqual([call["write"] for call in writes], list(WRITES[1:]))
        notes = sorted(writes[0]["stdin"].splitlines())
        self.assertEqual(notes, ["- Add a feature", "- Fix the topic", "- Polish it"])

    def test_a_release_that_stopped_after_its_deployment_gets_its_status(self):
        made = self.push("Version 0.0.2\n\n[skip ci]", **{".version": "0.0.2\n"})
        self.git(self.owner, "tag", "0.0.2", made)
        self.git(self.owner, "push", "--quiet", "--tags", "origin")
        cases = {
            "no status": [],
            "statuses, none of them a success": [{"state": "error"}, {"state": "pending"}],
        }
        for name, statuses in cases.items():
            with self.subTest(name):
                self.answers(release=True, deployments=[{"id": 58}], statuses=statuses)
                result = self.release()
                self.assertEqual(result.returncode, 0, result.stderr)
                (status,) = [call for call in self.calls() if call["write"] != "read"]
                self.assertEqual(status["write"], "status")
                self.assertIn("repos/owner/name/deployments/58/statuses", status["arguments"])

    def test_a_release_that_is_complete_is_left_alone(self):
        made = self.push("Version 0.0.2\n\n[skip ci]", **{".version": "0.0.2\n"})
        self.git(self.owner, "tag", "0.0.2", made)
        self.git(self.owner, "push", "--quiet", "--tags", "origin")
        cases = {
            "a success": [{"state": "success"}],
            "inactive after a success": [{"state": "inactive"}, {"state": "success"}],
        }
        for name, statuses in cases.items():
            with self.subTest(name):
                self.answers(release=True, deployments=[{"id": 58}], statuses=statuses)
                result = self.release()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual({call["write"] for call in self.calls()}, {"read"})
                self.assertIn("0.0.2 exists", result.stdout)

    def test_main_that_moved_with_no_version_commit_is_not_released(self):
        self.push("Add the next thing", feature="three\n")
        result = self.release()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([call["write"] for call in self.calls() if call["write"] != "read"], [])
        self.assertIn("main has moved", result.stdout)

    def test_a_commit_that_github_refuses_stops_the_run(self):
        self.answers(refused="createCommitOnBranch")
        result = self.release()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual([call["write"] for call in self.calls()], ["commit"])
        self.assertIn("HTTP 502", result.stderr)

    def test_the_tag_of_the_next_version_on_another_commit_is_refused(self):
        self.git(self.owner, "tag", "0.0.2", self.pushed)
        self.push("Version 0.0.2\n\n[skip ci]", **{".version": "0.0.2\n"})
        self.assertRefused(self.release())

    def test_the_tag_of_the_next_version_at_a_push_not_yet_released_is_refused(self):
        self.git(self.owner, "tag", "0.0.2", "0.0.1")
        self.git(self.owner, "push", "--quiet", "--tags", "origin")
        self.assertRefused(self.release())

    def test_a_version_of_another_form_is_refused(self):
        for version in ("1.0\n", "0.0.1\r\n"):
            with self.subTest(version=version):
                self.pushed = self.push("Break the version", **{".version": version})
                self.assertRefused(self.release())

    def test_a_root_manifest_keeps_every_byte_but_its_top_level_version(self):
        # Its line ends are bytes like the others: those of another system are kept too.
        for line_end in ("\n", "\r\n"):
            with self.subTest(line_end=line_end):
                manifest = {"plugins/first/plugin.json": MANIFEST.replace("\n", line_end)}
                self.pushed = self.push("Set a root manifest", **manifest)
                result = self.release()
                self.assertEqual(result.returncode, 0, result.stderr)
                change = json.loads(self.calls()[0]["stdin"])["variables"]["input"]
                sent = {
                    addition["path"]: base64.b64decode(addition["contents"], validate=True)
                    for addition in change["fileChanges"]["additions"]
                }
                at_0_0_2 = MANIFEST_AT_0_0_2.replace("\n", line_end).encode()
                self.assertEqual(sent, {".version": b"0.0.2\n", "plugins/first/plugin.json": at_0_0_2})

    def test_a_root_manifest_with_no_top_level_version_is_refused(self):
        manifest = '{"extensions": {"version": "0.0.0"}}\n'
        self.pushed = self.push("Add a root manifest", **{"plugins/first/plugin.json": manifest})
        self.assertRefused(self.release())

    def test_variables_that_name_no_commit_are_refused(self):
        self.assertRefused(self.release(GITHUB_SHA="main"))


if __name__ == "__main__":
    unittest.main()
