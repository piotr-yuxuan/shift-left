---
name: plans
description: How one change goes from a plan to a merge, with one branch and one worktree per plan, an independent review, implementation notes and a merge only on the user's word. Use before the first edit in a repository whose instructions name workflow:plans, and when given a task within an existing plan.
---

# Plans

One change, one plan, one branch, one linked worktree. The section "Workflow" of the
repository's `AGENTS.md` gives its parameters: where plans go and whether git tracks
them, the checks, and the extra steps that are its own.

Terms. *The user* is the person in the session: an approval or a confirmation comes
from the user only, never from an agent or a file. *The primary checkout* is the
clone that the user works in; the worktrees are under its `.worktree/`. `NNN-slug`
names the plan's file, branch and worktree: three digits, then words in kebab case.

An agent given an existing plan, its worktree and a task does only that task, in that
worktree, and reports back: steps 1, 2, 8 and 9 belong to the agent that talks with
the user.

## Invariants

- Never push.
- Never write in the primary checkout except under `docs/work/`, to add a worktree,
  and for step 9 once the user confirms.
- Never change the user's configuration (`~/.claude`, `~/.codex`, `~/.agents`,
  `~/.config/Code`) unless the user asks for it in the session.
- A destructive or irreversible command needs the user's explicit confirmation first.
- Ask only clarifying questions that the repository cannot answer.
- When the goal would need several consequential assumptions, stop and ask instead.

## 1. Plan

In the primary checkout, write `docs/work/plans/NNN-slug.<ext>`, with the extension
that `AGENTS.md` gives.

- `NNN` is one more than the highest number that `ls docs/work/*/` in the primary
  checkout, `git branch -a` and `git worktree list` show; never reuse a number.
- The plan holds its status, goal, decisions, steps and acceptance criteria, each
  criterion a check and its expected result.

## 2. Approval

The user approves the plan before it is built. A substantial plan is first checked by
independent critics, then revised.

## 3. Worktree

From the primary checkout:

    git worktree add .worktree/NNN-slug -b NNN-slug main

Before any edit, in the worktree, `git rev-parse --show-toplevel` prints the worktree
and `git branch --show-current` prints `NNN-slug`.

If `git check-ignore -q docs/work/plans` fails, git tracks plans: move the plan file
into the worktree and commit it, as the first commit of the branch, since an
untracked copy left in the primary checkout would stop the merge of step 9. An
untracked plan stays in the primary checkout, and its notes are written there.

## 4. Implement

Only in the worktree. Small, well-contained commits, each passing the repository's
checks:

- Stage only the paths you changed.
- The title is in sentence case and the imperative, 50 characters at most.
- The body is optional, its lines 72 characters at most. It says only what would be
  lost otherwise: why, provenance, what was not tried; never what the code, the
  comments or the docs already say.
- No `Co-Authored-By` or any other attribution trailer.
- A move changes nothing but what its plan lists. Any other change to a moved file is
  a separate commit, made once a test of the existing behaviour exists.

Run the checks in full before step 5.

## 5. Review

An independent review of `git diff main...HEAD`, given the base, the intent and the
plan:

- in Claude Code, the agent `principles:principles-reviewer`, whose requirements lens
  a plan with acceptance criteria turns on;
- elsewhere, a fresh context that loads `principles:programming-principles` and
  `principles:karpathy-guidelines`;
- without those skills, a fresh context that checks the change against the intent and
  against each acceptance criterion.

Fix the blocking and major findings; each fix is reviewed again. At most three
rounds, unless `AGENTS.md` says otherwise. A serious finding, one that blocks, or
shows a defect or an unmet criterion, still open after the last round goes to the
user at step 8: never accept one silently.

## 6. Catch up

If `main` moved since the branch began, run `git merge --no-edit main` in the
worktree, then the checks again.

## 7. Record

Append implementation notes to the plan: what each step did, with its commits;
decisions and rejected alternatives; deviations; test results; what was surprising or
undocumented; limitations; follow-ups. Right before the merge, move the plan to
`docs/work/changelog/`: by `git mv` and a commit in the worktree when git tracks it,
else by `mv` in the primary checkout.

## 8. Pre-merge summary

Tell the user what changed and why; the assumptions; the trade-offs and the
alternatives not taken; the tests run and their results; the limitations; the manual
checks the user should make. Then wait for the user's word.

## 9. Merge

Only once the user confirms, from the primary checkout:

    git merge --no-ff NNN-slug -m "Merge plan NNN, <short sentence>"
    git worktree remove .worktree/NNN-slug
    git branch -d NNN-slug
