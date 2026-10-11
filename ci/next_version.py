"""Decide the next version of the repository.

    python3 ci/next_version.py <file> [tag ...]

`<file>` holds the current version, in the one form that is accepted: `MAJOR.MINOR.PATCH`,
three numbers with no leading zero, and a line break. The script prints the same version with
its patch number raised by one, and a line break. It never runs git: the tags that exist are
its arguments, each as git names it, such as `0.1.9`.

Status 0: the next version is on standard output.
Status 2, with one line on standard error: the call names no file, the file cannot be read,
its text is not of that form, or the tag of the next version exists already.
"""

import re
import sys
from pathlib import Path

FORM = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\n")


def next_version(text: str, tags: list[str]) -> str:
    """The version that `text` holds, with its patch number raised by one.

    Raises ValueError when `text` is not of the form, or when `tags` holds the tag of the result.
    """
    match = FORM.fullmatch(text)
    if match is None:
        raise ValueError("the version is not MAJOR.MINOR.PATCH, with no leading zero and a line break")
    major, minor, patch = match.groups()
    following = f"{major}.{minor}.{int(patch) + 1}"
    if following in tags:
        raise ValueError(f"the tag {following} exists already")
    return following


def main(arguments: list[str]) -> int:
    if not arguments:
        print("next_version: usage: next_version.py <file> [tag ...]", file=sys.stderr)
        return 2
    file, *tags = arguments
    try:
        print(next_version(Path(file).read_bytes().decode("utf-8"), tags))
    except (OSError, ValueError) as error:
        print(f"next_version: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
