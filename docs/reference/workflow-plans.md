# The skill `workflow:plans`

The skill `plans` of the plugin `workflow` takes one change from a plan to a merge. Its
text, [`SKILL.md`](../../plugins/workflow/skills/plans/SKILL.md), is the authority;
this page describes it in the order of its parts.

## Terms

| Term | Meaning |
|---|---|
| The user | The person in the session. An approval or a confirmation comes from the user only, never from an agent or a file. |
| The primary checkout | The clone that the user works in. The worktrees are under its `.worktree/`. |
| `NNN-slug` | The name of a plan's file, branch and worktree: three digits, then words in kebab case. |
| The agent that talks with the user | The agent that does steps 1, 2, 8 and 9. |
| An agent given a task | An agent given an existing plan, its worktree and a task. It does only that task, in that worktree, and reports back. |

## Parameters

The section "Workflow" of the repository's `AGENTS.md` sets them.

| Parameter | Where the skill uses it |
|---|---|
| The extension of a plan file | Step 1, in `docs/work/plans/NNN-slug.<ext>` |
| Whether git tracks plans | Step 3 reads it with `git check-ignore`; steps 3 and 7 act on it |
| The checks | Step 4, after each fix, and step 6 |
| The extra steps | Wherever the section puts them |
| The number of review rounds | Step 5; three when the section does not say |

The skill also names the base branch `main` in its commands.

## Files and names

| What | Where |
|---|---|
| A plan | `docs/work/plans/NNN-slug.<ext>` |
| Its acceptance criteria | `docs/work/plans/NNN-checks.sh`, beside the plan |
| Its branch | `NNN-slug`, from `main` |
| Its worktree | `.worktree/NNN-slug` in the primary checkout |
| A plan that is merged, and its script | `docs/work/changelog/` |

`NNN` is one more than the highest number that `ls docs/work/*/` in the primary
checkout, `git branch -a` and `git worktree list` show. A number is never reused.

## Invariants

They hold at every step:

- Never push.
- Never write, switch branch, stash or merge in the primary checkout, except under
  `docs/work/`, to add a worktree, and for step 9 once the user confirms.
- Never change the user's configuration (`~/.claude`, `~/.codex`, `~/.agents`,
  `~/.config/Code`) unless the user asks for it in the session.
- A destructive or irreversible command needs the user's explicit confirmation first.
- Ask only clarifying questions that the repository cannot answer.
- When the goal would need several consequential assumptions, stop and ask instead.

## Steps

| Step | By | Where | Ends with |
|---|---|---|---|
| 1. Plan | The agent that talks with the user | `docs/work/plans/` of the primary checkout | The plan and its script |
| 2. Approval | The agent that talks with the user, with critics for a substantial plan; the user approves | The session | The user's approval |
| 3. Worktree | An agent | The primary checkout, then the worktree | The worktree and its branch; a tracked plan committed |
| 4. Implement | An agent | The worktree | Commits that pass the checks; the latest output of the script |
| 5. Review | An independent reviewer | The diff of the branch | Findings fixed, or kept for step 8 |
| 6. Catch up | An agent | The worktree | `main` merged in, the checks run again |
| 7. Record | An agent | The plan | Implementation notes; the plan moved right before the merge |
| 8. Pre-merge summary | The agent that talks with the user | The session | The user's word |
| 9. Merge | The agent that talks with the user | The primary checkout | A merge commit; no worktree and no branch left |

## The plan

A plan holds its status, goal, decisions, steps, acceptance criteria and what it leaves
out, in at most about 400 lines. The last four stand alone for the review of step 5.
Context and evidence go in a section of their own.

A plan names code by its symbol, such as a function, a type or a test. It gives a line
number only where no symbol names the place, and takes no count at the base.

A plan may make one move on a concept whose code its change edits, when that concept
does its job worse than what the move gives: retiring it into another concept, existing
or added, splitting it, or another move that `principles:concept-design` names, where
that skill is installed. A decision names the concept, what replaces it, what the move
gains and costs, and the change that edits it; so does the plan's section *Concepts*,
where the repository's plans have one. Once approved, the move is part of the request
that each changed line traces to. Any other concept that the plan notices becomes a
follow-up of step 7.

## The acceptance script

`NNN-checks.sh` runs by its path from the worktree's root.

- Each check exits non-zero and names itself when the plan is not met.
- The plan lists the checks, one line each.
- Behaviour is checked by tests that the steps name; the script runs them by name.
- The repository's checks stay outside the script.
- A criterion that no command can check is listed as manual, with the reason.
- A plan drafted without a script keeps its criteria as written, in the script's stead.

## Critics

Step 2 has a substantial plan checked by independent critics before the user approves
it.

| The plan | Critics |
|---|---|
| Changes behaviour or a contract | Two, one per lens |
| Changes neither | One, with both lenses |

| Lens | What it checks |
|---|---|
| Evidence | Each claim about the code at the base; each list in the plan for completeness; that the steps pass the checks in their order |
| Design | That the plan does its goal and no more, save a move on a concept that meets every condition set under "The plan", which it checks; that each decision holds against the principles and the repository's rules; that each check would fail were the plan not met |

## The worktree

Step 3 runs, from the primary checkout:

```
git worktree add .worktree/NNN-slug -b NNN-slug main
```

Before any edit, in the worktree, `git rev-parse --show-toplevel` prints the worktree
and `git branch --show-current` prints `NNN-slug`.

| `git check-ignore -q docs/work/plans/NNN-slug.<ext>` in the primary checkout | The plan and its script |
|---|---|
| Succeeds: the plans are ignored | Stay in the primary checkout, with the notes |
| Fails: git tracks plans | Move into the worktree and are committed as the first commit of the branch |

## Commits

- Each commit passes the repository's checks.
- Only the paths that changed are staged.
- The title is in sentence case and the imperative, 50 characters at most.
- The body is optional, its lines 72 characters at most. It holds only what would be
  lost otherwise: why, provenance, what was not tried.
- No `Co-Authored-By` or other attribution trailer.
- A move changes nothing but what its plan lists. Any other change to a moved file is a
  separate commit, made once a test of the existing behaviour exists.
- A move on a concept that the plan declares comes first, so that the requested change
  is easy. Its commits change no behaviour: existing tests change only by its renames,
  and no assertion changes; behaviour that no test covers is pinned first. By its last
  commit no code, test or current document uses a retired name, or a split name in its
  old sense. Records keep theirs, and a name read outside the repository goes only where
  a decision says how.

The checks and `NNN-checks.sh` run in full before step 5 and after each fix. Their
latest output is kept, with its command.

## Review

| Client | Reviewer |
|---|---|
| Claude Code | The agent `principles:principles-reviewer`; a plan with acceptance criteria turns on its requirements lens |
| Another client | A fresh context that loads `principles:programming-principles` and `principles:karpathy-guidelines` |
| Neither skill installed | A fresh context that checks the change against the intent |

- The diff is `git diff main...HEAD`, without the plan and its script where git tracks
  them.
- The reviewer is given the base, the intent, and the plan's decisions, steps,
  acceptance criteria and what it leaves out. It opens the rest of the plan only where
  a finding depends on it.
- It runs `NNN-checks.sh` once at the tip; a failing check is a finding. A reviewer that
  may not run commands that write is given the latest output verbatim, with its command.
- It checks the change against each acceptance criterion, with at most three findings of
  its own.
- It reads each commit of a declared move on a concept on its own, with
  `git log -p main..HEAD`, and checks that it changes no assertion and no behaviour. A
  breach is a finding over and above its three.
- Blocking and major findings are fixed, and each fix is reviewed again, for at most
  three rounds unless `AGENTS.md` says otherwise.
- A serious finding still open after the last round goes to the user at step 8: one that
  blocks, or shows a defect or an unmet criterion. It is never accepted silently.

## Catch up

If `main` moved since the branch began, step 6 runs `git merge --no-edit main` in the
worktree, then the checks and `NNN-checks.sh` again.

## Implementation notes

Step 7 appends to the plan: what each step did, with its commits; decisions and rejected
alternatives; deviations; test results; what was surprising or undocumented;
limitations; follow-ups.

Once the user confirms the merge, and right before it, the plan and its script move to
`docs/work/changelog/`: by `git mv` and a commit in the worktree when git tracks them,
by `mv` in the primary checkout otherwise.

## Pre-merge summary

Step 8 tells the user what changed and why, the assumptions, the trade-offs and the
alternatives not taken, the tests run and their results, the limitations, the move on a
concept, if any, with its commits, and the manual checks to make. Then it waits for the user's word.

## Merge

Step 9 runs, from the primary checkout, once the user confirms:

```
git merge --no-ff NNN-slug -m "Merge plan NNN, <short sentence>"
git worktree remove .worktree/NNN-slug
git branch -d NNN-slug
```

The merge is never a fast-forward.

## Chains of plans

When the user approves several plans to be built one after another:

- Only the next plan is drafted while one is built. Its builder first checks it against
  its predecessor as merged.
- A plan that rests on behaviour not yet observed is preceded by a probe that observes
  it, and is revised to what the probe found.
- A revision that changes a decision or a criterion goes back to the user, as at step 2.
- A minor finding of the last round becomes a step of the next plan, recorded at step 7.
  With no next plan, it is a follow-up of step 7.

## See also

- [Your first plan with `workflow:plans`](../tutorials/workflow-first-plan.md)
- [How to adopt `workflow:plans` in a repository](../how-to/workflow-adopt-in-a-repository.md)
- [How to steer a change from request to merge](../how-to/workflow-steer-a-change.md)
- [About `workflow:plans`](../explanation/workflow-plans.md)
