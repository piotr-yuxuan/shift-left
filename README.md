# claude-plugin

A Claude Code marketplace, `piotr-yuxuan`, with a few small plugins that bring review
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

## Install

These commands are untested until this repository is first pushed. What was tested is
an install from a local clone and from a local git source.

```
claude plugin marketplace add piotr-yuxuan/claude-plugin
claude plugin install principles@piotr-yuxuan
claude plugin install quality-ratchet@piotr-yuxuan
claude plugin install basedpyright-lsp@piotr-yuxuan
```

The same commands recreate a user configuration on a new machine: they record the
marketplace and the enabled plugins in the user's `settings.json`.

From a local clone, `claude plugin marketplace add <clone>` registers the directory
itself. Claude Code then loads the plugins in place, so an edit in the clone applies
at the next session.

### If a hook wrongly blocks

Disable its plugin, and enable it again once the cause is fixed:

```
claude plugin disable quality-ratchet@piotr-yuxuan
claude plugin enable quality-ratchet@piotr-yuxuan
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
