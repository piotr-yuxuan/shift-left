"""Carry out the release of one push to `main`, or what is left of it.

    python3 ci/release.py

The pipeline runs it in a checkout of the repository, with `git` and `gh` on PATH. It takes the
pushed commit from `GITHUB_SHA` and the repository from `GITHUB_REPOSITORY`; `gh` takes its
token from `GH_TOKEN`. A release is four writes, made in this order:

    commit      the version commit on `main`: `.version` at the next patch version, and the
                top-level `version` of each `plugins/<name>/plugin.json`
    release     the release `vX.Y.Z` with its tag, on the version commit
    deployment  a deployment record of that tag, in the environment `release`
    status      the status `success` of that record

The script first reads what exists: `main` and the tags of `origin`, by a fetch; then, where an
earlier run made the version commit, the release and the deployment that GitHub holds. It makes
only the writes that are missing, so it can be run again after a failure at any point.

Status 0: the release is complete; or `main` has moved and the commit after the pushed one is
no version commit, in which case nothing is written and the run of the newer push releases.
Status 1: git or GitHub refused a call, or did not answer in time. The answer is on standard
error, and no call follows the one that failed.
Status 2, with one line on standard error and nothing written: the two variables do not name a
commit and a repository; `.version` is not of the form that `next_version.py` accepts; `main`
is at the pushed commit and the tag of the next version exists already; that tag is on another
commit than the version commit; or a root manifest is not JSON with a top-level `version`.
"""

import base64
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, replace

from next_version import next_version

WRITES = ("commit", "release", "deployment", "status")
ENVIRONMENT = "release"
# The message of a version commit is this title, a blank line and this marker.
TITLE = "Version {}"
MARKER = "[skip ci]"
# Seconds that one call of git or of gh may last. The job that runs the script bounds the
# whole run, with `timeout-minutes` in the workflow file.
TIMEOUT = 120
# What the two variables of the pipeline must hold.
COMMIT = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")

COMMIT_MUTATION = (
    "mutation($input: CreateCommitOnBranchInput!) "
    "{ createCommitOnBranch(input: $input) { commit { oid } } }"
)
RELEASE_QUERY = (
    "query($owner: String!, $name: String!, $tag: String!) "
    "{ repository(owner: $owner, name: $name) { release(tagName: $tag) { tagName } } }"
)


@dataclass(frozen=True)
class Commit:
    """The commit after the pushed one on `main`, as far as a version commit is told by it."""

    hash: str
    parents: tuple[str, ...]
    message: str
    changed: frozenset[str]  # the paths that differ from the pushed commit


@dataclass(frozen=True)
class Found:
    """What a run finds before it writes anything."""

    pushed: str
    head: str  # `main` of `origin`
    version: str  # the text of `.version` at the pushed commit
    manifests: dict[str, str]  # the text of each root manifest at the pushed commit, by path
    tags: dict[str, str]  # the commit of each tag of `origin`, by name
    successor: Commit | None
    # What GitHub holds for the tag of the next version; read once a version commit is found.
    release: bool = False
    deployment: int | None = None
    success: bool = False


@dataclass(frozen=True)
class Decision:
    version: str  # the next version
    files: dict[str, str]  # the text of each file of the version commit, by path
    made: str | None  # the version commit, when an earlier run made it
    writes: tuple[str, ...]  # what is missing, among WRITES and in their order


def versioned(manifest: str, version: str) -> str:
    """The text of a root manifest with its top-level `version` set, and every other byte kept.

    Raises ValueError when the text is not a JSON object whose top-level `version` is a string.
    """
    data = json.loads(manifest)
    if not isinstance(data, dict) or not isinstance(data.get("version"), str):
        raise ValueError("no top-level version")
    wanted = data | {"version": version}
    # Several members may be named `version`: the top-level one is the one whose change
    # gives the wanted document.
    for match in re.finditer(r'("version"\s*:\s*)"[^"\\]*"', manifest):
        candidate = manifest[: match.end(1)] + json.dumps(version) + manifest[match.end() :]
        if json.loads(candidate) == wanted:
            return candidate
    raise ValueError("no top-level version")


def decide(found: Found) -> Decision:
    """The writes that are missing. Reads nothing and writes nothing.

    Raises ValueError where nothing may be written: the cases of status 2.
    """
    fresh = found.head == found.pushed
    # The tags are given only where a version commit is about to be made: the tag of a
    # version commit that exists may exist too.
    version = next_version(found.version, list(found.tags) if fresh else [])
    files = {".version": f"{version}\n"}
    for path, manifest in sorted(found.manifests.items()):
        try:
            files[path] = versioned(manifest, version)
        except ValueError as error:
            raise ValueError(f"{path} is not JSON with a top-level version") from error
    if fresh:
        return Decision(version, files, None, WRITES)
    after = found.successor
    if (
        after is None
        or after.parents != (found.pushed,)
        or after.message != f"{TITLE.format(version)}\n\n{MARKER}"
        or not after.changed <= files.keys()
    ):
        return Decision(version, files, None, ())
    if found.tags.get(f"v{version}", after.hash) != after.hash:
        raise ValueError(f"the tag v{version} is on another commit than the version commit")
    there = {
        "release": found.release,
        "deployment": found.deployment is not None,
        "status": found.success,
    }
    return Decision(version, files, after.hash, tuple(write for write in there if not there[write]))


def run(*command: str, stdin: str = "") -> str:
    """The standard output of a command. A command that fails or lasts too long raises."""
    done = subprocess.run(
        command,
        input=stdin,
        capture_output=True,
        check=True,
        timeout=TIMEOUT,
        encoding="utf-8",
        errors="surrogateescape",
    )
    return done.stdout


def api(*arguments: str, body: object = None) -> object:
    """What GitHub answers to one call of `gh api`. A body goes as JSON on standard input."""
    if body is None:
        return json.loads(run("gh", "api", *arguments))
    return json.loads(run("gh", "api", *arguments, "--input", "-", stdin=json.dumps(body)))


def read(pushed: str) -> Found:
    """What `origin` holds once it is fetched, around the pushed commit."""
    run("git", "fetch", "--quiet", "--tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
    head = run("git", "rev-parse", "--verify", "refs/remotes/origin/main^{commit}").strip()
    listed = run("git", "ls-tree", "-r", "-z", "--name-only", pushed, "--", ".version", "plugins")
    paths = listed.split("\0")
    tags = {}
    tag_format = "--format=%(refname:lstrip=2) %(objectname) %(*objectname)"
    for line in run("git", "for-each-ref", tag_format, "refs/tags").splitlines():
        # An annotated tag has two objects, and its commit is the second.
        name, *objects = line.split()
        tags[name] = objects[-1]
    successor = None
    after = run("git", "rev-list", "--first-parent", "--reverse", "--parents", f"{pushed}..{head}")
    if after:
        commit, *parents = after.splitlines()[0].split()
        changed = run("git", "diff", "-z", "--name-only", pushed, commit)
        successor = Commit(
            hash=commit,
            parents=tuple(parents),
            message=run("git", "log", "-n", "1", "--format=%B", commit).rstrip("\n"),
            changed=frozenset(changed.split("\0")) - {""},
        )
    return Found(
        pushed=pushed,
        head=head,
        version=run("git", "show", f"{pushed}:.version") if ".version" in paths else "",
        manifests={
            path: run("git", "show", f"{pushed}:{path}")
            for path in paths
            if re.fullmatch(r"plugins/[^/]+/plugin\.json", path)
        },
        tags=tags,
        successor=successor,
    )


def recorded(repository: str, tag: str) -> dict:
    """What GitHub holds of the release of a tag, as fields of Found."""
    owner, name = repository.split("/")
    variables = {"owner": owner, "name": name, "tag": tag}
    release = api("graphql", body={"query": RELEASE_QUERY, "variables": variables})
    listing = ("--method", "GET", f"repos/{repository}/deployments")
    deployments = api(*listing, "-f", f"ref={tag}", "-f", f"environment={ENVIRONMENT}")
    # The record of a tag is the latest that names it. Its status is there when one of its
    # statuses is a success, whatever came after: a later release leaves `inactive` as the latest.
    deployment = deployments[0]["id"] if deployments else None
    statuses = api(f"repos/{repository}/deployments/{deployment}/statuses") if deployments else []
    return {
        "release": release["data"]["repository"]["release"] is not None,
        "deployment": deployment,
        "success": any(status["state"] == "success" for status in statuses),
    }


def carry_out(repository: str, found: Found, decision: Decision) -> None:
    """Make the writes of a decision, in their order. A call that is refused raises."""
    tag = f"v{decision.version}"
    commit, deployment = decision.made, found.deployment
    if "commit" in decision.writes:
        additions = [
            # The mutation takes the contents of a file in Base64.
            {"path": path, "contents": base64.b64encode(text.encode(errors="surrogateescape")).decode()}
            for path, text in decision.files.items()
        ]
        change = {
            "branch": {"repositoryNameWithOwner": repository, "branchName": "main"},
            # The pushed commit, never a head read during the run: GitHub refuses the commit
            # on a branch that has moved.
            "expectedHeadOid": found.pushed,
            "message": {"headline": TITLE.format(decision.version), "body": MARKER},
            "fileChanges": {"additions": additions},
        }
        answer = api("graphql", body={"query": COMMIT_MUTATION, "variables": {"input": change}})
        commit = answer["data"]["createCommitOnBranch"]["commit"]["oid"]
        print(f"release: made the version commit {commit}")
    if "release" in decision.writes:
        # The titles of the commits that are no merge, since the tags before the pushed commit.
        before = run("git", "tag", "--merged", found.pushed).split()
        notes = run("git", "log", "--no-merges", "--format=- %s", found.pushed, "--not", *before)
        created = ("gh", "release", "create", tag, "--repo", repository, "--target", commit)
        run(*created, "--title", tag, "--notes-file", "-", stdin=notes)
        print(f"release: made the release {tag} and its tag")
    if "deployment" in decision.writes:
        record = {"ref": tag, "environment": ENVIRONMENT, "auto_merge": False, "required_contexts": []}
        deployment = api("--method", "POST", f"repos/{repository}/deployments", body=record)["id"]
        print(f"release: made the deployment record {deployment}")
    if "status" in decision.writes:
        statuses = f"repos/{repository}/deployments/{deployment}/statuses"
        api("--method", "POST", statuses, body={"state": "success"})
        print(f"release: gave the deployment record {deployment} the status success")


def main() -> int:
    pushed = os.environ.get("GITHUB_SHA", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not (COMMIT.fullmatch(pushed) and REPOSITORY.fullmatch(repository)):
        print(
            "release: GITHUB_SHA and GITHUB_REPOSITORY do not name a commit and a repository",
            file=sys.stderr,
        )
        return 2
    found = read(pushed)
    try:
        decision = decide(found)
    except ValueError as error:
        print(f"release: {error}", file=sys.stderr)
        return 2
    if decision.made:
        # An earlier run made the version commit: what GitHub holds of its release is read,
        # and the decision is made again with it.
        found = replace(found, **recorded(repository, f"v{decision.version}"))
        decision = decide(found)
    carry_out(repository, found, decision)
    if decision.made and not decision.writes:
        print(f"release: v{decision.version} exists, with its deployment record: nothing to do")
    elif not decision.writes:
        print(f"release: main has moved since {pushed} and its next commit is no version commit")
        print("release: nothing is released by this run; the run of the newer push releases")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.SubprocessError as error:
        for stream in (error.stdout, error.stderr):
            if isinstance(stream, str):
                sys.stderr.write(stream)
        print(f"release: {error}", file=sys.stderr)
        sys.exit(1)
