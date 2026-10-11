# Working in this repository

This repository holds one Claude Code marketplace, `shift-left`, and a few small
plugins. `docs/harness-facts.md` records what was observed about Claude Code and how.

## A registered clone is live configuration

The clone that a user registers as a local-directory marketplace, and whose
`instructions/global.md` the user-level instructions import, is called the primary
checkout. What it holds reaches sessions in two ways:

- `instructions/global.md` is read from the clone at each session start, as it is on
  disk, uncommitted edits and the checked-out branch included.
- The plugins were seen to be read from the clone in place by a start of the CLI, and
  from a copy in the plugin cache by a session of the desktop app. That copy stays at
  the commit that was installed until `claude plugin update <plugin>@shift-left`
  takes the commit that the clone is at.

So a merge into `main` changes the instructions at once, and the plugins of a desktop
session only after an update: in between, the instructions can be newer than the
plugins.

- Never write, switch branch, stash or merge in the primary checkout, except under
  `docs/work/` and to add a worktree.
- One plan, one branch, one linked worktree, named after the plan:
  `git worktree add .worktree/NNN-slug -b NNN-slug`.
- Never push, and never change the user's Claude Code configuration directory. The
  owner merges into `main`, pushes, and installs or updates the plugins.
- To try a command that changes a configuration, use a scratch one:
  `env -i HOME=<scratch>/home PATH="$PATH" CLAUDE_CONFIG_DIR=<scratch>/config "$C" ...`

## Rules for plugins

- A plugin is self-contained. Other people receive a copy of one plugin's directory
  without the rest of the repository, so no file of a plugin reaches outside its
  plugin. Two plugins that need the same few lines each keep a copy. A workflow that
  needs a script of another plugin declares that plugin as a dependency inside the
  marketplace.
- Hooks fail open. A hook that crashes or lacks a tool never blocks work. A guard
  before a tool call denies only by an explicit decision, and its command turns every
  other failure, a missing script included, into "allow". Every hook has a timeout
  that covers its worst case; the Python hook of `quality-ratchet` is the one recorded
  exception: its timeout of 90 seconds is below its worst case.
- A move changes nothing but what its plan lists. Any other content change to a moved
  file is a separate commit, made only after a test of the existing behaviour exists.

## Layout

```
.claude-plugin/marketplace.json   one entry per plugin
plugins/<name>/                   one self-contained plugin each
instructions/global.md            user-level rules, imported from a user-level CLAUDE.md
tests/                            tests of the plugins' scripts, outside the plugins
docs/harness-facts.md             what was observed about Claude Code
ruff.toml                         lint and format configuration
.version                          the version of the marketplace, raised by the pipeline
ci/                               the gate, and the scripts of a release
.github/workflows/ci.yml          the pipeline: the gate, then a release from main
docs/work/                        ignored: plans, notes, measurements
.worktree/                        ignored: one linked worktree per plan
```

`instructions/global.md` is not named `CLAUDE.md` or `AGENTS.md`, so that a session
working here does not load it a second time as project instructions.

## Commands

Before a handoff, an agent runs the gate, which runs every check of this section. The
pipeline runs the same script at each push. Its header says how to run one check alone,
and how it finds the CLI:

```
ci/gate.sh
```

The checks below are what it runs, each as a single command.

`C` is the Claude Code CLI. In a desktop session `claude` is not on `PATH` and the CLI
is at `$CLAUDE_CODE_EXECPATH`, so set it at the start of each command:

```
C="${CLAUDE_CODE_EXECPATH:-claude}"
```

Tests, which need `git` 2.42 or later, `ruff`, `bash` and `python3` on `PATH`:

```
python3 -m unittest discover -s tests -t .
```

Lint and format:

```
ruff check . && ruff format --check .
```

Manifests; each command must exit 0:

```
"$C" plugin validate .
"$C" plugin validate plugins/principles
"$C" plugin validate plugins/quality-ratchet
"$C" plugin validate plugins/coordinator
```

Self-containment of the plugins. The first command prints nothing; the second prints
16, the links from the guides back to their skill:

```
git grep -n -F '../' -- plugins | grep -v -F '](../SKILL.md)'
git grep -c -F '](../SKILL.md)' -- plugins | wc -l
```

The scope of a branch is read with three dots, since `main` gains a commit at each
release and two dots would list `.version`:

```
git diff --stat main...HEAD
```

## Tests

- Python `unittest` from the standard library, in `tests/` at the root.
- A script that is a hook is tested through its real contract: an event on standard
  input, an exit status, text on standard error. Expectations come from the documented
  contract, not from the code.
- A test that needs a git repository creates it isolated: every `GIT_*` variable
  removed, no global or system configuration, no signing, the identity
  `tests@example.invalid` passed by environment, and its own Ruff configuration, so
  that no test reads the user's home.

## Lint

`ruff.toml` carries an explicit rule list (`E`, `F`, `B`, `C901`), a line length of 104
and a McCabe limit of 10, so that nothing depends on the user-level configuration of
whoever runs Ruff. `ruff format` also formats the Python samples of Markdown files; the
guides of the `principles` skill are excluded from it, because they are kept as they
were written.

## Writing

- Small commits with sentence-case imperative titles.
- No Unicode dash in anything written for the repository, the licence text excepted.
- Nothing private in a tracked file or a commit message: no home directory path, no
  user name, no email address other than a commit identity, nothing from another
  repository. Write a real path as `<clone>` or `<scratch>`.
- A commit message carries no `Co-Authored-By` trailer.
- Nobody edits `.version` but the pipeline, and the owner for a new minor or major
  version.
- The title of the version commit of the pipeline, `Version X.Y.Z`, is the one
  exception to the rule on titles.
- No other commit message holds a skip marker such as `[skip ci]`, which keeps the
  pipeline from running.

## When a hook or a guard wrongly blocks

Do not change the configuration to get past it. Say what was blocked and stop. The
owner disables the plugin, for example
`claude plugin disable quality-ratchet@shift-left`, and enables it again once the
cause is fixed.
