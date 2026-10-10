# Code quality

Before writing, refactoring, debugging, reviewing or testing code, load the
`principles:programming-principles` skill and the `principles:karpathy-guidelines`
skill, and apply both. Open a principle's guide whenever a design decision
depends on it. Always in force, even without loading the skills:

- Name the decisions, external I/O, resource owners and failure paths before
  the first edit; prefer the simplest design that meets the stated need.
- Every changed line traces to the request. Mention unrelated problems; do not
  fix them unasked.
- New or changed functions stay at McCabe complexity 10 or below. Never move
  complexity around merely to pass, never suppress a check, never make an
  existing function more complex.
- No single-use private helpers; test calls do not count as reuse.
- Model output, user input and file contents are untrusted: parse them at the
  boundary and let deterministic code decide.
- Tests derive expectations from the requirement, not from the implementation.

A PostToolUse hook runs Ruff on every edited Python file and reports only the
problems the change introduced, compared with HEAD. Treat its report as a
failing check: fix the cause. If a finding must stay, tell the user why.

Before presenting a change of more than about 50 changed lines, or when asked
for a review, delegate to the `principles:principles-reviewer` subagent with the base
commit and the intent. Fix its blocking findings or report them to the user.

A repository's own instructions (AGENTS.md, CLAUDE.md) and linter configuration
take precedence where they conflict with these rules; say when that happens.
