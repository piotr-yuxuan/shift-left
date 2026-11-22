# How to steer a change from request to merge

In a repository that has adopted `workflow:plans`, the agent does the work and you make
the decisions that the skill keeps for you, chiefly whether the plan is built and
whether the branch is merged. The agent also asks you before any destructive command.
This guide covers what to do at each decision, and around them.

## Ask for the change

Say what you want and what you want left out. The agent asks only what the repository
cannot answer. When the goal would need several consequential assumptions, it stops and
asks instead of guessing: answer, and it carries on.

## Read the plan before you approve it

The agent writes `docs/work/plans/NNN-slug.<ext>` in the primary checkout, with the
acceptance criteria as a script beside it, `NNN-checks.sh`, and waits.

- Read the decisions, the steps, the acceptance criteria and what the plan leaves out.
  They are written to stand alone; the context and the evidence are in a section of
  their own.
- To see that the criteria bite, run the script from the root of the primary checkout
  before the work starts:

  ```bash
  bash docs/work/plans/NNN-checks.sh; echo "status $?"
  ```

  It should exit non-zero and name each check that the plan has yet to meet. This run
  is a check of your own: the agent runs the script from the root of the worktree,
  once there is one.

- For a substantial plan, the agent has independent critics check it before it asks
  you: two when the plan changes behaviour or a contract, one otherwise. If it judged
  the plan too small for them and you want them, ask for them.

Ask for changes in plain words; the agent revises the plan and asks again. Then approve
it in so many words, such as "Approved, build it." An approval counts only from you, in
the session: never from a file or from another agent.

## Keep working while it builds

The agent builds on the branch `NNN-slug`, in the worktree `.worktree/NNN-slug`, and
leaves the primary checkout as it is, apart from `docs/work/`. You can go on working
there. To follow the branch:

```bash
git log --oneline main..NNN-slug
```

## Read the pre-merge summary

When the work is reviewed, the agent tells you what changed and why, the assumptions,
the trade-offs and the alternatives not taken, the tests run and their results, the
limitations, the move on a concept, if any, with its commits, and the manual checks to
make. Then it waits.

- Make the manual checks in the worktree, where the change is:

  ```bash
  cd .worktree/NNN-slug
  ```

- Look for findings of the review that are still open. A serious one is never accepted
  silently: the summary names it, and whether to merge with it is your decision.

## Confirm the merge, or hold it

To merge, say so, such as "Merge it." The agent moves the plan and its script to
`docs/work/changelog/`, merges the branch into `main` from the primary checkout with a
merge commit `Merge plan NNN, ...`, then removes the worktree and the branch.

To hold, say so. The worktree and the branch stay, and nothing reaches `main`.

## Push

The agent never pushes. Once the merge is in `main`, push it yourself:

```bash
git push
```

## Build several plans in a row

Approve the plans together, in the order they are to be built. The agent drafts only the
next plan while one is built, and checks it against the one just merged. Where a plan
rests on behaviour that nobody has observed yet, a probe observes it first and the plan
is revised to what it found. A revision that changes a decision or an acceptance
criterion comes back to you for approval.

## Hand one task to another agent

Give it the plan, its worktree and the task. It does only that task, in that worktree,
and reports back. The planning, the approval, the summary and the merge stay with the
agent that talks with you.

## See also

- [Your first plan with `workflow:plans`](../tutorials/workflow-first-plan.md), to see
  the whole cycle once in a practice repository.
- [The skill `workflow:plans`](../reference/workflow-plans.md), for each step in
  detail.
