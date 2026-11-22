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
- Never write, switch branch, stash or merge in the primary checkout except under
  `docs/work/`, to add a worktree, and for step 9 once the user confirms.
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
- The plan holds its status, goal, decisions, steps, acceptance criteria and what it
  leaves out, in at most about 400 lines. The last four stand alone for the review of
  step 5; context and evidence go in a section of their own.
- Name code by its symbol, such as a function, a type or a test; give a line number
  only where no symbol names the place. Take no count at the base: the next merge
  makes both stale.
- The acceptance criteria are a script beside the plan, `NNN-checks.sh`, run by its
  path from the worktree's root: each check exits non-zero and names itself when the
  plan is not met, and the plan lists the checks in one line each. Behaviour is
  checked by tests that the steps name, which the script runs by name; the
  repository's checks stay outside it. A criterion that no command can check is
  listed as manual, with why. A plan drafted without a script keeps its criteria as
  written, in the script's stead.
- A plan may make one move on a concept whose code its change edits, when that
  concept does its job worse than what the move gives: retire it into another,
  existing or added, split it, or another move that `principles:concept-design`
  names, where it is installed. A decision names the concept, what replaces it,
  what the move gains and costs, and the change that edits it, as the plan's
  section *Concepts* does too where the repository's plans have one. Fewer and
  sharper concepts make every later change cheaper, so such a move is worth a
  larger diff than the request alone needs; once approved, it is part of the
  request that each changed line traces to. Any other concept that the plan
  notices becomes a follow-up of step 7.

## 2. Approval

The user approves the plan before it is built. A substantial plan is first checked by
independent critics, then revised: two, one per lens, when it changes behaviour or a
contract, else one with both lenses. The *evidence* lens checks each claim about the
code at the base, each list in the plan for completeness, and that the steps pass the
checks in their order; the *design* lens, that the plan does its goal and no more,
save a move on a concept that meets every condition of step 1, which the lens checks
one by one (a single move, on a concept whose code the change edits and that does its
job worse, declared in a decision); that each decision holds against the principles
and the repository's rules; and that each check would fail were the plan not met.

## 3. Worktree

From the primary checkout:

    git worktree add .worktree/NNN-slug -b NNN-slug main

Before any edit, in the worktree, `git rev-parse --show-toplevel` prints the worktree
and `git branch --show-current` prints `NNN-slug`.

If `git check-ignore -q docs/work/plans/NNN-slug.<ext>` fails in the primary checkout,
git tracks plans: move the plan and its script into the worktree and commit them, as
the first commit of the branch, since an untracked copy left there would stop the
merge of step 9. An untracked plan stays in the primary checkout, with its notes and
its script.

## 4. Implement

Only in the worktree. Small, well-contained commits, each passing the repository's
checks:

- Stage only the paths you changed.
- The title is in sentence case and the imperative, 50 characters at most.
- The body is optional, its lines 72 characters at most. It says only what would be
  lost otherwise: why, provenance, what was not tried; never what the code, the
  comments or the docs already say.
- No `Co-Authored-By` or any other attribution trailer.
- A move of code changes nothing but what its plan lists. Any other change to a moved
  file is a separate commit, made once a test of the existing behaviour exists.
- A move on a concept that the plan declares comes first, so that the requested change
  is easy: make the change easy, then make the easy change. Its commits change no
  behaviour: existing tests change only where they name or build what the move
  replaces, and no assertion changes otherwise; behaviour that no test covers is
  pinned first, as before another change to a moved file. By its last commit no code,
  test or current document uses a retired name, or a split name in its old sense;
  records keep theirs, and so does a name read outside the repository, such as an
  option or a field of a format, unless a decision says how it changes.

Run the checks in full, and `NNN-checks.sh`, before step 5 and after each fix; keep
the script's latest output, with its command.

## 5. Review

An independent review of the diff `git diff main...HEAD`, the plan and its script
left out of it where git tracks them:

- in Claude Code, the agent `principles:principles-reviewer`, whose requirements lens
  a plan with acceptance criteria turns on;
- elsewhere, a fresh context that loads `principles:programming-principles` and
  `principles:karpathy-guidelines`;
- without those skills, a fresh context that checks the change against the intent.

Whoever reviews is given the base, the intent and the plan's decisions, steps,
acceptance criteria and what it leaves out, and opens the rest of the plan only where
a finding depends on it. It runs `NNN-checks.sh` once at the tip, a failing check
being a finding; a reviewer that may not run commands that write is given its latest
output verbatim, with its command.

Whoever reviews also checks the change against each acceptance criterion of the plan,
with at most three findings of its own. It reads each commit of a declared move on a
concept on its own, with `git log -p main..HEAD`, and checks that it changes no
assertion and no behaviour; a breach is a finding over and above its three. Fix the
blocking and major findings; each fix is reviewed again. At most three rounds, unless
`AGENTS.md` says otherwise. A serious finding, one that blocks, or shows a defect or
an unmet criterion, still open after the last round goes to the user at step 8: never
accept one silently.

## 6. Catch up

If `main` moved since the branch began, run `git merge --no-edit main` in the
worktree, then the checks and `NNN-checks.sh` again.

## 7. Record

Append implementation notes to the plan: what each step did, with its commits;
decisions and rejected alternatives; deviations; test results; what was surprising or
undocumented; limitations; follow-ups. Once the user confirms the merge at step 8,
and right before it, move the plan and its script to `docs/work/changelog/`: by
`git mv` and a commit in the worktree when git tracks them, else by `mv` in the
primary checkout.

## 8. Pre-merge summary

Tell the user what changed and why; the assumptions; the trade-offs and the
alternatives not taken; the tests run and their results; the limitations; the move on
a concept, if any, with its commits; the manual checks the user should make. Then
wait for the user's word.

## 9. Merge

Only once the user confirms, from the primary checkout, never by a fast-forward, so
that the merge commit groups the plan's commits and gives them one revertable handle:

    git merge --no-ff NNN-slug -m "Merge plan NNN, <short sentence>"
    git worktree remove .worktree/NNN-slug
    git branch -d NNN-slug

## Chains of plans

When the user approves several plans to be built one after another:

- Draft only the next plan while one is built. Its builder first checks it against
  its predecessor as merged.
- Before a plan that rests on behaviour not yet observed is built, a probe observes
  that behaviour, and the plan is revised to what the probe found.
- A revision that changes a decision or a criterion goes back to the user, as at
  step 2.
- A minor finding of the last round becomes a step of the next plan, recorded at
  step 7, rather than the cause of another round; with no next plan, it is a
  follow-up of step 7.
