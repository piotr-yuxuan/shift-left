# shift-left

A Claude Code marketplace, `shift-left`, with a few small plugins that bring review
quality forward to the moment code is written. Each plugin can be adopted alone.

## Plugins

### `principles`

- The skill `principles:programming-principles`: sixteen design rules for clear,
  maintainable, verifiable code. Each rule has a guide with a definition, two worked
  examples and a review question, opened only when a decision depends on it.
- The skill `principles:karpathy-guidelines`: four guidelines against the common
  mistakes of a language model that writes code: think before coding, simplicity
  first, surgical changes, goal-driven execution. It is copied unchanged from another
  repository, under another licence: see the notice beside it.
- The agent `principles:principles-reviewer`: a fast, read-only review of one change
  against both skills, in one bounded pass.

It needs nothing else.

### `quality-ratchet`

A hook that runs after each edit of a Python file. It runs Ruff with the repository's
own configuration, plus McCabe complexity and the bugbear rules, on the edited file and
on its committed version, and reports to Claude only the problems that the edit
introduced. A function that is already over the complexity threshold may not grow; it
is also reported when it is renamed, or when it shrinks and stays over the threshold.

It needs `python3` (3.11 or later) and `git` on `PATH`, and Ruff: the `.venv/bin/ruff`
of the repository being edited when there is one, otherwise the `ruff` on `PATH`.
Without Ruff the hook reports its own failure at each Python edit. For a file that is
new or outside a git repository, every problem counts as introduced.

### `basedpyright-lsp`

Type diagnostics after each edit and navigation by symbol for `.py` and `.pyi` files,
from the basedpyright language server.

It needs `basedpyright-langserver` on `PATH`. Do not enable `pyright-lsp` at the same
time, or diagnostics are reported twice.

### `coordinator`

The skill `coordinator:instrument`: two scripts that an agent runs from the directory
of the skill, so that what a plan cost and what its review found are read from data.

- `findings.py` keeps the findings of the reviews of one plan in one JSON file. One
  schema file, `finding.schema.json`, is the authority on the fourteen fields of a
  finding, on their values and on which role writes which: reviewer, fixer or
  coordinator. The script prints the schema of the answer of each role, rejects an
  answer that breaks the schema or a rule, and summarises the file. It writes a file
  whole or not at all, and only where git ignores it, since findings can quote
  private code.
- `minutes.py` reads the cost of ended workflow runs from the records that Claude
  Code keeps: wall minutes and agent minutes per stage, the agents that did not
  finish, and two bounds of the coordinator's minutes from the transcript of the main
  session.
- `codebook.md` defines the labels that a rater gives to a finding afterwards:
  category, origin, knowable and cheapest preventer.

It needs `python3` (3.11 or later) on `PATH`; `findings.py` also needs `git` and a
POSIX system. The shape of the run records and of the transcripts was observed with
Claude Code 2.1.288, see `docs/harness-facts.md`. `minutes.py` refuses a run record
in which a key that it reads is missing or has another type, and a transcript that
holds `user` or `assistant` records of which none starts a turn. It does not refuse a
value that it does not know: an entry of an unknown type is ignored, and an agent in
a state other than `done` counts as not finished. A later version of Claude Code that
renames such a value gives wrong figures, so see the facts again after an upgrade.

## Install

These commands are untested until this repository is first pushed. What was tested is
an install from a local clone and from a local git source.

```
claude plugin marketplace add piotr-yuxuan/shift-left
claude plugin install principles@shift-left
claude plugin install quality-ratchet@shift-left
claude plugin install basedpyright-lsp@shift-left
claude plugin install coordinator@shift-left
```

The same commands recreate a user configuration on a new machine: they record the
marketplace and the enabled plugins in the user's `settings.json`.

From a local clone, `claude plugin marketplace add <clone>` registers the directory
itself. A start of the CLI was then seen to read the plugins from the clone in place,
and a session of the desktop app from a copy made at install time. After a change in
the clone, refresh that copy to the commit of the clone, then restart the session:

```
claude plugin update principles@shift-left
claude plugin update quality-ratchet@shift-left
claude plugin update coordinator@shift-left
```

### If a hook wrongly blocks

Disable its plugin, and enable it again once the cause is fixed:

```
claude plugin disable quality-ratchet@shift-left
claude plugin enable quality-ratchet@shift-left
```

## Always-on instructions

A plugin cannot ship instructions that load into every session.
`instructions/global.md` holds the user-level rules that go with these plugins. The
file belongs to no plugin, so installing a plugin does not bring it: clone this
repository, or copy the file, then import it from your user-level `CLAUDE.md` with one
line that gives its absolute path, here from a clone:

```
@<clone>/instructions/global.md
```

Claude Code's documentation says that a user-level file imports without an approval
dialog, that a space in the path needs a backslash before it, and that Cowork sessions
skip such an import when the file lies outside their working directory.

## Other tools

The skills use the standard `skills/<name>/SKILL.md` layout, which tools of other
vendors read. This was not tested with any of them.

## Licence

EUPL 1.2, see `LICENSE`. One file is under MIT: the skill `karpathy-guidelines` of the
`principles` plugin, as the notice beside it says.
