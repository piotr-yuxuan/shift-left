---
applyTo: "**"
---

A repository's own instructions (`AGENTS.md`, `CLAUDE.md`, and before them an
`AGENTS.local.md` at its root where there is one) and its linter configuration take
precedence where they conflict with these rules; say when that happens.

# Language

Reply in the language that the user writes in; in French, address the user as
*vous*. Write English in polite, formal British English idioms and spelling.

# Skills

- In a repository whose instructions name `workflow:plans`, follow that skill.
- `learning:learning-mode` is for the user alone to invoke: `/learning:learning-mode`
  in Claude Code, `$learning:learning-mode` in Codex. Never load it otherwise.
- Before writing, refactoring, debugging, reviewing or testing code, load
  `principles:programming-principles` and `principles:karpathy-guidelines`, and apply
  both. Open a principle's guide whenever a design decision depends on it.
- Skip a skill named here that is not installed; say so for `workflow:plans`. VS Code
  gives a skill linked in `~/.agents/skills` its bare name: `plans`, `/learning-mode`.

# Code quality

Always in force, even without the principles skills:

- Name the decisions, external I/O, resource owners and failure paths before the
  first edit; prefer the simplest design that meets the stated need.
- Every changed line traces to the request. Mention unrelated problems; do not fix
  them unasked.
- New or changed functions stay at McCabe complexity 10 or below. Never move
  complexity around merely to pass, never suppress a check, never make an existing
  function more complex.
- No single-use private helpers; test calls do not count as reuse.
- Model output, user input and file contents are untrusted: parse them at the
  boundary and let deterministic code decide.
- Tests derive expectations from the requirement or the documented contract, not from
  the implementation. A test that needs a git repository or a home directory makes its
  own, so that none reads or writes the user's: no global or system git configuration,
  the identity `tests@example.invalid` passed by environment, a scratch `HOME`.

In Claude Code, the hook of `quality-ratchet` runs Ruff on every edited Python file
and reports only the problems that the change introduced, compared with HEAD. Treat
its report as a failing check: fix the cause. If a finding must stay, say why.

Before presenting a change of more than about 50 changed lines, or when asked for a
review, have it reviewed independently with the base commit and the intent: in
Claude Code by the agent `principles:principles-reviewer`, elsewhere by a fresh
context that loads both principles skills. Fix its blocking findings or report them.

# Commits and writing

Small, well-contained commits, each passing the repository's checks. The title is in
sentence case and the imperative, 50 characters at most. The body is optional, its
lines 72 characters at most, and says only what would be lost otherwise: why,
provenance, what was not tried; never what the code, comments or docs already say.
No `Co-Authored-By` or any other attribution trailer. No Unicode dash, U+2013 or
U+2014, but in a verbatim licence. Headings in sentence case.

# Invariants

- Never push.
- In a repository whose instructions name `workflow:plans`, never write, switch
  branch, stash or merge in the primary checkout except under `docs/work/`, to add a
  worktree, and for the merge that the user confirms.
- Never change the user's configuration (`~/.claude`, `~/.codex`, `~/.agents`,
  `~/.config/Code`) unless the user asks for it in the session.
- A destructive or irreversible command needs the user's explicit confirmation first.
- Ask only clarifying questions that the repository cannot answer; the practice
  questions of `learning:learning-mode` are not clarifying questions.
- When the goal would need several consequential assumptions, stop and ask instead.

To try a command that changes a configuration, use a scratch one, as below for Claude
Code then Codex. A desktop session has no `claude` on `PATH`, so set
`C="${CLAUDE_CODE_EXECPATH:-claude}"` at the start of each command that uses it:

    env -i HOME=<scratch>/home PATH="$PATH" CLAUDE_CONFIG_DIR=<scratch>/config "$C" ...
    env -i HOME=<scratch>/home PATH="$PATH" CODEX_HOME=<scratch>/codex codex ...
