# About `workflow:plans`

`workflow:plans` fixes the life of one change: a plan the user approves, one branch and
one worktree, an independent review, notes, and a merge on the user's word. This page
says why it takes that shape, what each rule protects, and what was tried or weighed
instead. The [reference](../reference/workflow-plans.md) describes the rules themselves.

## The problem it answers

shift-left began from one question: with a coding agent, much of the time of a change
went into rounds of review and fixes after the first implementation, so what would move
that quality to the moment the code is first written, at a lower total cost and to the
same bar? Several of the answers concern the code, and live in the plugins
`principles` and `quality-ratchet`. The others concern the process around the code:
what is decided before the work, who decides it, what evidence counts, and when a
review stops. Those are this skill.

Before the skill, each repository kept its own copy of the process in its `AGENTS.md`.
The skill holds it once. A repository now names the skill
and gives only what is its own: the extension of its plans, whether git tracks them, its
checks and its extra steps.

## Why the primary checkout is left alone

In this repository the clone that the user registers is live configuration, as
[`AGENTS.md`](../../AGENTS.md) explains under "A registered clone is live
configuration": sessions read its plugins and its shared instructions as they are on
disk, uncommitted edits and the checked-out branch included. A half-made edit there, a
branch switched to try something, or a bad merge reaches every session at its next
start. So the work happens elsewhere, in a linked worktree per plan, and the primary
checkout changes only by the merge that the user confirms.

The rule names switching branch and stashing beside writing, because the checked-out
branch is itself part of what sessions read. The exceptions are narrow: `docs/work/`,
where plans are written; adding a worktree; and the confirmed merge.

Most repositories are not live configuration, and the rule costs them little: one
`git worktree add` per plan. What they gain is a checkout that stays theirs while an
agent works, and one place per plan where its state can be read.

## Why the user approves the plan, and critics read it first

A few of the serious findings of reviews of finished changes traced back to the plan or
the brief that the code was written from, rather than to the code. They were a
minority, but a defect of a plan is cheapest to fix before anything is built on it, so
a substantial plan is checked before it is approved, and revised.

The critics read with two lenses. The *evidence* lens asks whether each claim about the
code is true at the base, whether each list is complete, and whether the steps can pass
the checks in their order. The *design* lens asks whether the plan does its goal and no
more, and whether each check would fail were the plan not met. A plan that changes
behaviour or a contract gets one critic per lens, any other substantial plan one critic
with both lenses, and a small plan none.

Approval comes from the user, in the session, and never from an agent or a file. The
skill says "the user" rather than "the owner" so that it reads the same to anyone who
installs the plugin.

A plan that rests on behaviour nobody has observed, of a client, a tool or a platform,
is preceded by a probe, and revised to what the probe found: plans and briefs had stated
such behaviour wrongly before.

## Why plans are short and the criteria are a script

Reviews took a large share of what a plan cost, and a reviewer reads the whole of what
it is given. So a plan holds its decisions, steps, acceptance criteria and what it leaves out in
parts that stand alone, and the reviewer reads those parts only. The limit is "about"
400 lines because the same content runs longer in Org than in Markdown.

A plan names code by its symbol and takes no count at the base, because a line number
or a count goes stale at the next merge into `main`, while the plan is still in use.

The acceptance criteria are commands, written with the plan and before the build. A
check that the implementer writes after the work tends to re-run the evidence the
implementer already chose; commands fixed in advance, and approved with the plan, are
evidence that someone else chose. The script travels with the plan rather than living
untracked in the worktree, because `git worktree remove` refuses to remove a worktree
that holds an untracked file, unless forced.

The reviewer agent of `principles` runs no command that writes, and widening it for
this one caller was rejected. So a reviewer that may not run the script is given its
latest output verbatim, with the command that produced it.

## Why the review is independent and bounded

A builder that reviews its own work reviews the evidence it chose. An independent
reviewer, in a context of its own, does not share that blind spot. The skill names the
reviewer in order of preference, the agent `principles:principles-reviewer`, then a
fresh context with the principles skills, then a fresh context with the intent alone,
so that `workflow` still works when it is installed without `principles`. Every one of
them checks the change against the plan's acceptance criteria.

Reviewers were rarely wrong, but findings kept arriving after the first round, so review
is not an oracle that converges on its own. Rounds are bounded, at three unless the
repository says otherwise, and a serious finding still open after the last one goes to
the user. It is never accepted silently. Within a round, the reviewer's findings of its
own are limited to three, so that unmet criteria and problems of the code do not crowd
each other out.

The builder does not review its own diff before step 5: that would be one review too
many per plan.

## Why the merge is a merge commit, and nobody pushes

The merge is never a fast-forward, so that one merge commit groups the plan's commits
and gives the whole plan one handle to revert. Its title names the plan's number, so the
history leads back to the plan.

The agent never pushes. Pushing publishes, and in this repository every push to `main`
that passes the gate becomes a release, as the [README](../../README.md#releases) says.
The skill leaves that step to the user.

## Why a plan's number is its name

`NNN-slug` names the plan, its branch and its worktree, so that any of the three leads
to the others. The number is a name and not a place: the order in which plans run is
kept elsewhere, and plans refer to each other by number, so a plan that moves from
`plans/` to `changelog/` breaks nothing. A number is never reused. A new one is one more
than the highest that the plans, the branches and the worktrees show: a tracked plan
moves into its worktree, so the primary checkout alone would not show every number
taken.

## Tracked plans and untracked plans

In shift-left the plans are not tracked: they carry evidence drawn from private records. Tracking
them was weighed and found heavy, since every change of a plan's state would wait for a
merge, and every line would have to be read for private text before it could be
committed. Other repositories track theirs, and the skill serves both.

A tracked plan has to be the first commit of its branch, not a file left in the primary
checkout: `git merge` refuses to overwrite an untracked file, even one with the same
content, so the copy left behind would stop the merge of step 9.

## Why the notes, and the move to the changelog

The implementation notes record what the diff cannot: why each decision went the way it
did, what was rejected, what surprised, and what is left. A later session can then
reason about past plans from their files, without the conversation that produced them.

The plan moves to `docs/work/changelog/` only once the user has confirmed the merge,
right before it. Moved earlier, a plan would be filed as merged while the user could
still refuse it.

## Chains of plans

When several plans are approved to run one after another, only the next is drafted
while one is built. A plan drafted far ahead has to be checked again each time an
earlier one lands, and those checks cost more than drafting late. A minor finding of the
last round becomes a step of the next plan rather than the cause of another round.

## Why an agent given a task does only that task

Several agents may work under one plan. An agent given a plan, its worktree and a task,
and left to follow the whole skill, could start a second plan of its own, or wait for an
approval that nobody will give. So planning,
approval, the summary and the merge belong to the agent that talks with the user, and
any other agent does its task and reports back.

## What the skill does not try to do

It does not choose the checks: each repository names its own. It does not decide what
"substantial" means for a plan, or which findings block: those stay judgements of the
agent, under the user's eye. And it does not reach outside the repository: the
configuration of the user's clients is out of its bounds unless the user asks.
