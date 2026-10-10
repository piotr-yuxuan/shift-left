# claude-plugin

A Claude Code marketplace, `piotr-yuxuan`, with a few small plugins that bring review
quality forward to the moment code is written. Each plugin can be adopted alone.

## Plugins

### `principles`

- The skill `principles:programming-principles`: sixteen design rules for clear,
  maintainable, verifiable code. Each rule has a guide with a definition, two worked
  examples and a review question, opened only when a decision depends on it.
- The agent `principles:principles-reviewer`: a fast, read-only review of one change
  against those rules, in one bounded pass.

It needs nothing else. The reviewer also names a skill of a companion plugin, see
below.

### `quality-ratchet`

A hook that runs after each edit of a Python file. It runs Ruff with the repository's
own configuration, plus McCabe complexity and the bugbear rules, on the edited file and
on its committed version, and reports to Claude only the problems that the edit
introduced. A function that is already over the complexity threshold may not grow.

It needs `python3` (3.11 or later) and `git` on `PATH`, and `ruff` on `PATH` or in the
`.venv` of the repository being edited. Without Ruff the hook reports its own failure
at each Python edit. For a file that is new or outside a git repository, every problem
counts as introduced.

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

### Optional companion

The reviewer agent also lists the skill `andrej-karpathy-skills:karpathy-guidelines`,
from another author's plugin, which `principles` does not declare as a dependency.
That plugin is `andrej-karpathy-skills` of the marketplace `karpathy-skills`, at
`https://github.com/forrestchang/andrej-karpathy-skills`; by the same pattern as
above, and as untested here:

```
claude plugin marketplace add forrestchang/andrej-karpathy-skills
claude plugin install andrej-karpathy-skills@karpathy-skills
```

Without it, Claude Code reports nothing about the missing skill when it validates and
loads the plugin. The agent itself was not run without it.

### If a hook wrongly blocks

Disable its plugin, and enable it again once the cause is fixed:

```
claude plugin disable quality-ratchet@piotr-yuxuan
claude plugin enable quality-ratchet@piotr-yuxuan
```

## Always-on instructions

A plugin cannot ship instructions that load into every session.
`instructions/global.md` holds the user-level rules that go with these plugins. To use
them, import the file from your user-level `CLAUDE.md`, with one line that gives its
absolute path:

```
@<clone>/instructions/global.md
```

Claude Code's documentation says that a user-level file imports without an approval
dialog, that a space in the path needs a backslash before it, and that Cowork sessions
skip such an import when the file lies outside their working directory.

## Other tools

The skill uses the standard `skills/<name>/SKILL.md` layout, which tools of other
vendors read. This was not tested with any of them.

## Licence

EUPL 1.2, see `LICENSE`.
