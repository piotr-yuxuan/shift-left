# shift-left

[![GitHub Release](https://img.shields.io/github/v/release/piotr-yuxuan/shift-left)](https://github.com/piotr-yuxuan/shift-left/releases/latest)
[![CI](https://img.shields.io/github/actions/workflow/status/piotr-yuxuan/shift-left/ci.yml?branch=main)](https://github.com/piotr-yuxuan/shift-left/actions/workflows/ci.yml)
[![GitHub licence](https://img.shields.io/github/license/piotr-yuxuan/shift-left)](https://github.com/piotr-yuxuan/shift-left?tab=EUPL-1.2-1-ov-file#readme)
[![GitHub Issues](https://img.shields.io/github/issues/piotr-yuxuan/shift-left)](https://github.com/piotr-yuxuan/shift-left/issues)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-compatible-blue)](https://agentskills.io/specification)
[![Claude Code](https://img.shields.io/badge/Claude_Code-plugin_marketplace-D97757?logo=claude&logoColor=white)](https://code.claude.com/docs/en/discover-plugins)

<img align="right" width="320" src="./docs/social-media-preview.png" alt="A shift key running leftward and chasing a bug">

Small plugins that help a coding agent write code that would already pass review: design rules that it consults while
it works, a reviewer that it can call on its own change, and a hook that keeps lint and complexity from getting worse.
The skills are packaged both for Claude Code and for the open Agent Skills and Agent Plugins standards, which Codex,
Cursor and GitHub Copilot read. Each plugin can be installed on its own.

<br clear="right">

## The plugins

| Plugin | What it gives the agent | Needs |
|---|---|---|
| [`principles`](plugins/principles) | Two skills: sixteen design rules for clear, maintainable, verifiable code, and four guidelines against common LLM coding mistakes. A read-only reviewer agent that checks a change against both | nothing |
| [`quality-ratchet`](plugins/quality-ratchet) | A hook that runs Ruff after each Python edit and reports only the problems that the edit introduced | Python 3.14+, git, Ruff |
| [`basedpyright-lsp`](plugins/basedpyright-lsp) | Type diagnostics and symbol navigation in Python files | `basedpyright-langserver` |
| [`workflow`](plugins/workflow) | A skill for the life of a change: one plan, one branch and one worktree, an independent review, a merge only on your word | git |
| [`learning`](plugins/learning) | A learning mode, started only by you, in which the agent teaches rather than does | nothing |
| [`coordinator`](plugins/coordinator) | Scripts that record what reviews found and what workflow runs cost | Python 3.14+, git |

<details>
<summary>More about each plugin</summary>

**`principles`.** `programming-principles` holds the sixteen design rules, each with a guide. `karpathy-guidelines`
holds four: think before coding, simplicity first, surgical changes, goal-driven execution; it is copied unchanged
from another repository, under MIT. The agent `principles-reviewer` reviews one change against both skills in one
bounded pass. Give it a plan with acceptance criteria and it checks the change against them too.

**`quality-ratchet`.** After each edit of a Python file, it runs Ruff with the repository's own configuration, plus
McCabe complexity and the bugbear rules, on the edited file and on its committed version, and reports the difference.
A function already over the complexity threshold may not grow. It prefers the `.venv/bin/ruff` of the repository being
edited to the `ruff` on `PATH`. In a new file, or outside git, every problem counts as introduced.

**`basedpyright-lsp`.** Do not enable `pyright-lsp` at the same time, or diagnostics are reported twice.

**`workflow`.** The skill `plans`: small commits with fixed rules for their messages, a review by
`principles-reviewer` where it is installed and otherwise in a fresh context, notes appended to the plan. A repository
adopts it with a section of its `AGENTS.md`:

```
## Workflow

Every change follows the skill `workflow:plans`; load it before the first edit. In
this repository: plans are `docs/work/plans/NNN-slug.<ext>`, tracked or not; the
checks are <commands>; the extra steps are <only what is specific here>.
```

**`learning`.** The agent reserves the meaningful decision for you, teaches with worked examples, asks one question at
a time and gives the least help that moves you forward. Start it with `/learning:learning-mode` in Claude Code, or
`$learning:learning-mode` in Codex; the model never loads it of its own accord.

**`coordinator`.** The skill `instrument` brings `findings.py`, which keeps the findings of the reviews of one plan in
one JSON file checked against a schema, and `minutes.py`, which reads the wall and agent minutes of ended workflow runs
from the records that Claude Code keeps. `codebook.md` defines the labels given to a finding afterwards.

</details>

## Light on context

An agent's context is its working memory, so nothing here is loaded in full up front.

- A skill costs only its name and description until a task calls for it.
- `programming-principles` loads a one-line index of its sixteen principles: locality, separation of concerns, DRY,
  low complexity, cohesion, coupling, single responsibility, information hiding, useful abstractions, duplication over
  the wrong abstraction, YAGNI, decisions and effects, explicit invariants, resource ownership, readability and
  meaningful verification. The agent opens a principle's guide, with its definition, two worked examples and a review
  question, only when a decision depends on it.
- The reviewer works in a context of its own and hands back only its findings.
- The hook runs outside the model and reports only what an edit made worse.
- The learning mode never loads unless you start it.

## Install in Claude Code

Add the marketplace, then install the plugins that you want:

```bash
claude plugin marketplace add piotr-yuxuan/shift-left
claude plugin install principles@shift-left
claude plugin install quality-ratchet@shift-left
claude plugin install basedpyright-lsp@shift-left
claude plugin install workflow@shift-left
claude plugin install learning@shift-left
claude plugin install coordinator@shift-left
```

`claude plugin update <plugin>@shift-left` takes a new release later. These commands record the marketplace and the
plugins in your user `settings.json`, so the same lines set up a new machine.

<details>
<summary>From a clone, for one session, or turning a plugin off</summary>

`claude plugin marketplace add <clone>` registers a local clone instead. The CLI then reads the plugins from the clone
in place, and the desktop app from a copy made at install time: after a change in the clone, run
`claude plugin update <plugin>@shift-left` and restart the session.

To try one plugin for one session, with nothing installed:

```bash
claude --plugin-dir <clone>/plugins/principles
```

If a hook gets in your way, disable its plugin, and enable it again later:

```bash
claude plugin disable quality-ratchet@shift-left
claude plugin enable quality-ratchet@shift-left
```

</details>

## Codex, Cursor and GitHub Copilot

`principles`, `workflow`, `learning` and `coordinator` each carry a `plugin.json` of the
[Agent Plugins](https://agent-plugins.org/specification) standard, and their skills follow
[Agent Skills](https://agentskills.io/specification), so each client can add them as its own documentation describes.
`install.sh`, at the root of a clone, also links the skills and the shared instructions where Codex and VS Code read
them.

<details>
<summary>Install with <code>install.sh</code>, for Claude Code, Codex and VS Code</summary>

```bash
<clone>/install.sh
```

It needs bash 4.4 or later and `python3`.

- **Claude Code**: it registers the clone as a marketplace and installs, or updates, each plugin. It checks that your
  user-level `CLAUDE.md` imports the shared instructions, and prints the line to add if not.
- **Codex**: it links each skill as `~/.agents/skills/<name>`, and the shared instructions as `AGENTS.md` of the Codex
  home, `~/.codex` or `CODEX_HOME`.
- **VS Code**: it prints one entry of the setting `chat.pluginLocations` per plugin for you to add, and links the shared
  instructions as `prompts/shift-left.instructions.md` in the user folder of stable VS Code. VS Code also reads the
  skill links in `~/.agents/skills`.

Of its own it makes links and nothing else; the Claude Code commands that it runs change that client's configuration.
It refuses, with its reason, when the place of a link is taken; its header lists every case. Run it again after each commit, so that Claude Code takes the commit too; Codex follows the links at once.
Clones of other marketplaces laid out the same way can be named as arguments.

To turn off a linked skill in Codex, keep its link and add this to `config.toml` of the Codex home, `<home>` being your
home directory:

```toml
[[skills.config]]
path = "<home>/.agents/skills/<name>/SKILL.md"
enabled = false
```

</details>

<details>
<summary>What works where</summary>

*Tested*: tried in that client. *Documented*: the client's documentation, or the list of compatible clients of Agent
Plugins, says that the client reads it; not yet tried here. *Not read*: its documentation says that it is not.
*Unknown*: no information yet.

| | Claude Code | Codex | Cursor | GitHub Copilot in VS Code | GitHub Copilot CLI |
|---|---|---|---|---|---|
| The five skills | tested | tested for `principles`, through `install.sh`; documented for the others | documented | documented | documented |
| The reviewer agent of `principles` | tested | unknown | unknown | not read | not read |
| The hook of `quality-ratchet` | tested | documented | unknown | documented; runs after every tool call there, not only after an edit | documented |
| The language server of `basedpyright-lsp` | tested | unknown | unknown | unknown | unknown |
| The shared instructions | tested | tested, through `install.sh` | unknown | unknown | unknown |

Where the reviewer agent is not available, `workflow` asks for the review in a fresh context instead. `minutes.py` of
`coordinator` reads records that only Claude Code writes. [`docs/harness-facts.md`](docs/harness-facts.md) records how
each fact was established, with the version of the client and the date.

</details>

## Shared instructions

[`instructions/global.md`](instructions/global.md) holds the owner's own always-on rules, written for every client:
which skills to load, code quality, commits and writing, and a few invariants such as never pushing. A plugin cannot
ship instructions that load into every session, so it belongs to no plugin: adopt what fits, since parts of it are
personal. In Claude Code, import it from your user-level `CLAUDE.md` with one line, a space in the path escaped with a
backslash:

```
@<clone>/instructions/global.md
```

## Releases

Every push to `main` that passes `ci/gate.sh` becomes a release: the pipeline raises the patch number in `.version`,
then tags and releases that commit. For Claude Code a plugin's version is its commit, so
`claude plugin update <plugin>@shift-left` takes the latest release. `basedpyright-lsp` keeps a version of its own,
1.0.0, which a release does not move.

## Licence

EUPL 1.2, see [`LICENSE`](LICENSE). The skill `karpathy-guidelines` of `principles` is under MIT, as the notice beside
it says.
