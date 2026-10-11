#!/usr/bin/env python3
"""PostToolUse hook: report Ruff problems that an edit introduced in a Python file.

The edited file is compared with its version at HEAD, so pre-existing problems are
not reported, and a function already over the complexity threshold may not grow.
Ruff uses the repository's own configuration, plus C901 (McCabe complexity, threshold
from that configuration or Ruff's default of 10) and B (bugbear).

Exit 0: nothing new. Exit 2: the report on stderr goes back to the agent.
Exit 1: the hook itself failed; the user sees the message.
"""

import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

EXTRA_RULES = "C901,B"


def ruff_problems(ruff: str, root: Path, relative: str, source: bytes) -> list[dict]:
    result = subprocess.run(
        [ruff, "check", "--no-cache", "--exit-zero", "--output-format", "json"]
        + ["--extend-select", EXTRA_RULES, "--stdin-filename", relative, "-"],
        cwd=root,
        input=source,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip())
    return json.loads(result.stdout)


def main() -> int:
    event = json.load(sys.stdin)
    path = Path(event.get("tool_input", {}).get("file_path", ""))
    if path.suffix != ".py" or not path.is_file():
        return 0
    found = subprocess.run(
        ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    root = Path(found.stdout.strip()) if found.returncode == 0 else path.parent
    relative = str(path.resolve().relative_to(root.resolve()))
    ruff = str(root / ".venv/bin/ruff") if (root / ".venv/bin/ruff").exists() else shutil.which("ruff")
    if ruff is None:
        print("python_quality_ratchet: ruff not found on PATH or in .venv", file=sys.stderr)
        return 1
    committed = subprocess.run(
        ["git", "-C", str(root), "show", f"HEAD:{relative}"], capture_output=True
    )
    before = committed.stdout if committed.returncode == 0 else b""
    try:
        known = Counter(
            (problem["code"], problem["message"])
            for problem in ruff_problems(ruff, root, relative, before)
        )
        current = ruff_problems(ruff, root, relative, path.read_bytes())
    except (RuntimeError, json.JSONDecodeError, subprocess.TimeoutExpired) as error:
        print(f"python_quality_ratchet: ruff failed on {relative}: {error}", file=sys.stderr)
        return 1
    introduced = []
    for problem in current:
        key = (problem["code"], problem["message"])
        if known[key]:
            known[key] -= 1
        else:
            introduced.append(problem)
    if not introduced:
        return 0
    print(
        f"Ruff found problems introduced in {relative} (compared with HEAD; "
        "pre-existing ones are not shown):",
        file=sys.stderr,
    )
    for problem in introduced:
        where = problem["location"]
        code = problem["code"] or "syntax"
        print(f"  {where['row']}:{where['column']} {code} {problem['message']}", file=sys.stderr)
    print(
        "Fix them without suppressing a rule or moving complexity merely to pass. "
        "If one must stay, explain why to the user.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
