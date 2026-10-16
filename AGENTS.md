# Working in this repository

This repository holds one marketplace, `shift-left`, and a few small plugins for
coding agents. They are written for Claude Code, and those that hold a skill are also
packaged as the Agent Plugins standard asks. `docs/harness-facts.md` records what was
observed about each client and about the standards, and how.

## Workflow

Every change follows the skill `workflow:plans`; load it before the first edit. In this
repository: plans are `docs/work/plans/NNN-slug.md`, not tracked; the checks are
`ci/gate.sh`; the extra steps are the plan's row in `docs/work/README.md`, whose rules
hold under `docs/work/`, added at step 1 and its link changed at step 7, and after step
6 the `version` of each root `plugin.json` that the branch adds set to `.version`.

The rules that every repository shares are in `instructions/global.md`, which the
user-level instructions import.

## A registered clone is live configuration

The clone that a user registers as a local-directory marketplace, and whose
`instructions/global.md` the user-level instructions import, is called the primary
checkout. What it holds reaches sessions in three ways:

- `instructions/global.md` is read from the clone at each session start, as it is on
  disk, uncommitted edits and the checked-out branch included.
- The plugins were seen to be read from the clone in place by a start of the CLI, and
  from a copy in the plugin cache by a session of the desktop app. That copy stays at
  the commit that was installed until `claude plugin update <plugin>@shift-left`
  takes the commit that the clone is at.
- Once `install.sh` has run from it, Codex reads its skills through links in
  `~/.agents/skills`, and `instructions/global.md` through a link at `AGENTS.md` of
  the Codex home, from the clone as it is on disk. VS Code is given a link to the same
  file in its user folder, not seen read. A skill that is added, moved or removed
  needs another run to get, change or lose its link.

So a merge into `main` changes the instructions and the skills of Codex at once, and
the plugins of a desktop session only after an update: in between, the instructions
can be newer than the plugins.

The owner pushes, and installs or updates the plugins.

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
- Portable core, client adapters. A remedy has a core that needs no particular
  client: a script with a decision function free of I/O and a contract on the command
  line, and a skill that says when to run it. A hook, an agent definition or a
  workflow is an adapter around the core, and it is the stronger enforcement where a
  client offers one. A client gets an adapter only once the owner uses it, and each
  adapter is tested through the documented contract of its client.
- The files of one client stay where that client reads them, and they are not private
  to it. Claude Code's are `.claude-plugin/`, `agents/` and `hooks/`, and other clients
  are documented to read `agents/` and `hooks/hooks.json` too, one of them after every
  tool call: the README has the table. So a hook kept in `hooks/hooks.json` checks the
  name of the tool and the shape of its input itself, exits 0 on an event that it does
  not recognise, and has a test that feeds it such events. What the Python hook of
  `quality-ratchet` does with such an event is recorded with its date in
  `docs/harness-facts.md`, under VS Code. A client with a namespace directory
  gets its own files there, such as `com.github.copilot/`, and only on the owner's
  word. Codex documents none: its data go under `extensions.com.openai` of the root
  manifest, and its hook files stay at the root of the plugin. A plugin that has both
  a root manifest and a hook therefore either tests that hook against the event that
  Codex documents, or declares its hooks under `extensions.com.openai`, which replaces
  the discovery of `hooks/hooks.json`, as `docs/harness-facts.md` records of the page
  of Codex. Every adapter is tested through the documented contract of its client, as
  a hook is.

## Layout

```
.claude-plugin/marketplace.json   one entry per plugin
plugins/<name>/                   one self-contained plugin each
plugins/<name>/plugin.json        the manifest of the standard, where there is a skill
instructions/global.md            user-level rules, imported from a user-level CLAUDE.md
install.sh                        the installer, for Claude Code, Codex and VS Code
tests/                            tests of the plugins' scripts, outside the plugins
tests/packaging/                  tests of the manifests and of the skills
docs/harness-facts.md             what was observed about each client and the standards
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

The gate runs every check of this section and four more, and the pipeline runs the
same script at each push. Its header describes each check, and says how to run one
alone and how it finds the CLI:

```
ci/gate.sh
```

The commands below are what four of its eight checks run: `tests`, `lint`, `manifests`
and `contained`. The four others have no command here: `dashes`, `private` and `version`
read the tracked files, and `messages` reads the commit messages that no tag reaches.

`$C` is the Claude Code CLI, as the shared rules set it.

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
"$C" plugin validate plugins/workflow
"$C" plugin validate plugins/learning
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
  input, an exit status, text on standard error.
- A test that needs a git repository, isolated as the shared rules ask, also removes
  every `GIT_*` variable, turns signing off and has its own Ruff configuration.

## Lint

`ruff.toml` carries an explicit rule list (`E`, `F`, `B`, `C901`), a line length of 104
and a McCabe limit of 10, so that nothing depends on the user-level configuration of
whoever runs Ruff. `ruff format` also formats the Python samples of Markdown files; the
guides of the `principles` skill are excluded from it, because they are kept as they
were written.

## Writing

- Nothing private in a tracked file or a commit message: no home directory path, no
  user name, no email address other than a commit identity, nothing from another
  repository. Write a real path as `<clone>` or `<scratch>`.
- Nobody edits `.version` but the pipeline, and the owner for a new minor or major
  version; the `version` of each root `plugin.json` under `plugins/` is edited in the
  same commit, since a test keeps them equal.
- The title of the version commit of the pipeline, `Version X.Y.Z`, is the one
  exception to the shared rule on titles.
- No other commit message holds a skip marker such as `[skip ci]`, which keeps the
  pipeline from running.

## When a hook or a guard wrongly blocks

Do not change the configuration to get past it. Say what was blocked and stop. The
owner disables the plugin, for example
`claude plugin disable quality-ratchet@shift-left`, and enables it again once the
cause is fixed.
