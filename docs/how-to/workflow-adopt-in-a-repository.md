# How to adopt `workflow:plans` in a repository

This guide sets up a git repository so that a coding agent takes every change through
`workflow:plans`: a plan you approve, a branch and a worktree for it, an independent
review, and a merge on your word.

## Install the plugins

In Claude Code, with the marketplace added as the [README](../../README.md#install-in-claude-code)
shows:

```bash
claude plugin install workflow@shift-left
claude plugin install principles@shift-left
```

`principles` gives the review of step 5 its reviewer agent. Without it, the review is
made in a fresh context instead. For Codex, Cursor and GitHub Copilot, see the
README's section [Codex, Cursor and GitHub Copilot](../../README.md#codex-cursor-and-github-copilot).

## Check the name of the base branch

The skill branches from `main`, catches up with `main` and merges into `main`, by that
name:

```bash
git branch --list main
```

If this prints nothing, rename the default branch to `main` before the first plan.

## Decide whether git tracks the plans

Plans live in `docs/work/plans/`, and merged plans in `docs/work/changelog/`. The skill
asks git whether a plan is ignored, and acts on the answer.

- If the plans are private working papers, ignore them. Add to `.gitignore`:

  ```
  /docs/work/
  ```

  They then stay in the primary checkout, with their notes and checks scripts, and no
  commit holds them.

- If you want the plans in the history, leave `docs/work/plans/` and
  `docs/work/changelog/` unignored. The agent then commits each plan and its script as
  the first commit of its branch, and moves them to `docs/work/changelog/` with
  `git mv` before the merge.

## Ignore the worktrees

The worktrees are created under `.worktree/` in the primary checkout. Add to
`.gitignore`:

```
/.worktree/
```

Without it, `git status` in the primary checkout lists `.worktree/` as untracked.

## Write the section "Workflow"

Add this section to the repository's `AGENTS.md`, then fill it in:

```
## Workflow

Every change follows the skill `workflow:plans`; load it before the first edit. In
this repository: plans are `docs/work/plans/NNN-slug.<ext>`, tracked or not; the
checks are <commands>; the extra steps are <only what is specific here>.
```

- `<ext>` is the extension of the plan files, such as `md` or `org`.
- Replace `tracked or not` with `tracked` or `not tracked`, whichever matches your
  `.gitignore`.
- The checks are the commands that every commit must pass, given as the agent runs them
  from the root of a worktree: the tests, the linters, a build.
- The extra steps are what this repository asks that the skill does not: a row to add to
  an index, a version to keep in step, a file to classify. Leave out anything the skill
  already does. With none, write that there are none.

If reviews should stop after a number of rounds other than three, say so in the same
section.

If the repository also has a `CLAUDE.md`, put the section there: Claude Code reads
`AGENTS.md` only where no `CLAUDE.md` exists in the working directory or above it, as
[`docs/harness-facts.md`](../harness-facts.md) records.

## Make the checks pass on `main`

Every commit of a plan must pass the checks, so a check that already fails on `main`
blocks every plan. Run each command on `main` and fix what fails before the first plan.

## Try it

Commit the changes above, start a session in the repository and ask for a small change.
The agent should write `docs/work/plans/001-<slug>.<ext>` and its `001-checks.sh`, then
stop and ask for your approval. [How to steer a change from request to
merge](workflow-steer-a-change.md) takes it from there.

## See also

- [The skill `workflow:plans`](../reference/workflow-plans.md), for every parameter and
  path.
- [About `workflow:plans`](../explanation/workflow-plans.md), for why the workflow is
  the way it is.
