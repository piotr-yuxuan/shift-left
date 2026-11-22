#!/usr/bin/env python3
"""Give a linked git worktree a codegraph index of its own.

    code_index.py <path>    act for the worktree that holds <path>, and print one line:
                            `indexed <root>`, `has an index <root>` or
                            `not indexed <path>: <reason>`
    code_index.py --hook    act on the event of a hook, read on standard input

codegraph answers from the nearest `.codegraph/` at or above a path, so a linked worktree with
none of its own is answered from the main worktree's index, as that branch stands. A worktree
is eligible when it is a linked worktree, the main worktree of its repository holds
`.codegraph/`, and `codegraph` is on PATH; nothing is done or printed for any other directory.
An eligible worktree without `.codegraph/` is indexed when git ignores `.codegraph/` in it, so
that the index does not show as untracked and leaves with the worktree when git removes it.

Events: after a `Bash` command that holds `worktree add` (`PostToolUse`), every eligible
worktree of the repository at `cwd` without an index is indexed, and each one is named in
`hookSpecificOutput.additionalContext`, the output of that event that reaches the model. At
`SessionStart`, an eligible worktree at `cwd` is indexed where it may be, and one line says
what it has. Any other event, input or argument changes nothing and prints nothing.

The status is 0 in every case, and never 2, the status by which a hook blocks: an error of git,
of codegraph or of this script ends with one line on standard error.
"""

import json
import shutil
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

INDEX = ".codegraph"
QUERY_BY_PATH = (
    "Query codegraph with that path as the project path; without it, the answers describe the"
    " main worktree, not this branch."
)
USAGE = "usage: code_index.py <path> | code_index.py --hook"


@dataclass(frozen=True)
class Facts:
    """What decides for one worktree, whose top level is `root`."""

    root: Path
    linked: bool
    main_indexed: bool
    codegraph: bool
    indexed: bool
    ignored: bool


def decide(facts: Facts) -> tuple[str, str]:
    """`skip` (not eligible), `has an index`, `not indexed` or `index`, and the reason."""
    if not facts.linked:
        return "skip", "not a linked worktree"
    if not facts.main_indexed:
        return "skip", f"the main worktree holds no {INDEX}/"
    if not facts.codegraph:
        return "skip", "codegraph is not on PATH"
    if facts.indexed:
        return "has an index", ""
    if not facts.ignored:
        return "not indexed", f"git does not ignore {INDEX}/ there"
    return "index", ""


def git(directory: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(directory), *arguments],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )


def worktree_list(directory: Path) -> list[list[str]]:
    """The records of `git worktree list --porcelain`, the main worktree's first."""
    listing = git(directory, "worktree", "list", "--porcelain", "-z")
    if listing.returncode != 0:
        return []
    return [record.split("\0") for record in listing.stdout.split("\0\0") if record]


def gather(path: Path) -> Facts | None:
    """The facts of the worktree that holds `path`, or None outside any worktree."""
    places = git(
        path,
        "rev-parse",
        "--show-toplevel",
        "--absolute-git-dir",
        "--path-format=absolute",
        "--git-common-dir",
    )
    if places.returncode != 0:
        return None
    root, git_dir, common = (Path(line) for line in places.stdout.splitlines())
    main = (worktree_list(root) or [[]])[0]
    # The first record names the main worktree, unless the repository is bare.
    main_indexed = (
        bool(main) and "bare" not in main and (Path(main[0].removeprefix("worktree ")) / INDEX).is_dir()
    )
    return Facts(
        root=root,
        linked=git_dir.resolve() != common.resolve(),
        main_indexed=main_indexed,
        codegraph=shutil.which("codegraph") is not None,
        indexed=(root / INDEX).is_dir(),
        ignored=git(root, "check-ignore", "-q", f"{INDEX}/").returncode == 0,
    )


def act(facts: Facts) -> tuple[str, str]:
    """Index where `decide` says so: `indexed`, or what `decide` said, with the reason."""
    action, reason = decide(facts)
    if action != "index":
        return action, reason
    folder = facts.root / INDEX
    try:
        folder.mkdir()  # The claim: of hooks run at once, only one makes the folder.
    except FileExistsError:
        return "has an index", ""
    indexed = False
    try:
        done = subprocess.run(
            ["codegraph", "init", "-y", "."],
            cwd=facts.root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        indexed = done.returncode == 0
    finally:
        if not indexed:  # The folder is this process's: a failed index leaves nothing behind.
            shutil.rmtree(folder, ignore_errors=True)
    if not indexed:
        return "not indexed", f"codegraph init ended with status {done.returncode}"
    return "indexed", ""


def on_session_start(cwd: Path) -> str | None:
    """The line that tells the session what its worktree has, or None if not eligible."""
    facts = gather(cwd)
    if facts is None:
        return None
    outcome, reason = act(facts)
    if outcome == "skip":
        return None
    if outcome == "not indexed":
        return (
            f"codegraph: this worktree, {facts.root}, is not indexed: {reason}. codegraph's"
            " answers here describe the main worktree, not this branch."
        )
    state = "has just been indexed" if outcome == "indexed" else "has an index of its own"
    return f"codegraph: this worktree, {facts.root}, {state}. {QUERY_BY_PATH}"


def on_worktree_add(cwd: Path) -> str | None:
    """The output that names to the model each worktree indexed, or None if there is none."""
    named = []
    for record in worktree_list(cwd)[1:]:
        facts = gather(Path(record[0].removeprefix("worktree ")))
        if facts is not None and act(facts)[0] == "indexed":
            named.append(f"codegraph: indexed the worktree {facts.root}. {QUERY_BY_PATH}")
    if not named:
        return None
    context = {"hookEventName": "PostToolUse", "additionalContext": "\n".join(named)}
    return json.dumps({"hookSpecificOutput": context})


def on_event(event: object) -> str | None:
    """What to print for a hook's event; None for an event that this script does not handle."""
    if not isinstance(event, dict) or not isinstance(event.get("cwd"), str):
        return None
    name, cwd = event.get("hook_event_name"), Path(event["cwd"])
    if name == "SessionStart":
        return on_session_start(cwd)
    tool_input = event.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if name == "PostToolUse" and event.get("tool_name") == "Bash" and isinstance(command, str):
        return on_worktree_add(cwd) if "worktree add" in command else None
    return None


def main(arguments: list[str]) -> None:
    if arguments == ["--hook"]:
        try:
            event = json.loads(sys.stdin.read())
        except ValueError:
            return
        output = on_event(event)
        if output:
            print(output)
    elif len(arguments) == 1 and not arguments[0].startswith("-"):
        path = Path(arguments[0])
        facts = gather(path)
        if facts is None:
            print(f"not indexed {path}: not in a git worktree")
            return
        outcome, reason = act(facts)
        if outcome in ("indexed", "has an index"):
            print(f"{outcome} {facts.root}")
        else:
            print(f"not indexed {facts.root}: {reason}")
    else:
        print(USAGE, file=sys.stderr)


if __name__ == "__main__":
    # A client that ends the hook at its timeout sends SIGTERM: as an exit, it unwinds
    # through `act`, which stops codegraph and removes the folder that would pass for an index.
    signal.signal(signal.SIGTERM, lambda _number, _frame: sys.exit(0))
    try:
        main(sys.argv[1:])
    except Exception as error:  # Fail open: no error of git, codegraph or this script blocks.
        print(f"code_index.py: {error}", file=sys.stderr)
    sys.exit(0)
