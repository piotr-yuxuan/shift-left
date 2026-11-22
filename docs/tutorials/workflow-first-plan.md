# Your first plan with `workflow:plans`

In this tutorial we take one small change through `workflow:plans`, in a practice
repository, from the request to the merge. On the way we will see everything the
workflow leaves behind: a plan and its checks script, a branch and its worktree, the
commits, and a merge commit that groups them. It takes about twenty minutes.

## Before we start

We need:

- git;
- Claude Code, with the marketplace `shift-left` added and the plugins `workflow` and
  `principles` installed, as the [README](../../README.md#install-in-claude-code)
  shows;
- no file `~/CLAUDE.md`: where one exists above the practice repository, Claude Code
  does not read the repository's `AGENTS.md`.

## Make a practice repository

In a terminal, we make a repository with one file to change:

```bash
mkdir ~/practice-plans
cd ~/practice-plans
git init -b main
printf 'Hello\n' > greeting.txt
```

It needs checks that every commit must pass. Ours is one line, which fails when
`greeting.txt` is missing or empty:

```bash
printf 'test -s greeting.txt\n' > check.sh
```

Then the section of `AGENTS.md` that asks the agent to follow the workflow:

```bash
cat > AGENTS.md <<'EOF'
## Workflow

Every change follows the skill `workflow:plans`; load it before the first edit. In
this repository: plans are `docs/work/plans/NNN-slug.md`, not tracked; the checks
are `sh check.sh`; there are no extra steps.
EOF
```

We have git ignore the plans and the worktrees, and commit:

```bash
printf '/docs/work/\n/.worktree/\n' > .gitignore
git add .
git commit -m "Start the practice repository"
```

Let us check:

```bash
git log --oneline
```

One commit, `Start the practice repository`.

## Ask for the change

We start Claude Code in the repository:

```bash
claude
```

and ask:

> Add a line `Bonjour` to greeting.txt.

When Claude Code asks for permission to run a command, we allow it.

The agent loads `workflow:plans`, writes a plan and stops to ask for our approval.

In a second terminal, in `~/practice-plans`, let us look:

```bash
ls docs/work/plans/
```

Two files: `001-<slug>.md` and `001-checks.sh`, where `<slug>` is a few words that the
agent chose, such as `001-add-bonjour.md`. We note that name: below, we write it
`001-slug`, and we replace it with ours.

We open the plan. Notice its parts: a status, the goal, the decisions, the steps, the
acceptance criteria, and what it leaves out.

The script holds the acceptance criteria. Nothing is built yet, so it fails:

```bash
bash docs/work/plans/001-checks.sh; echo "status $?"
```

It names the check that is not met, and the status is not 0.

## Approve the plan

Back in Claude Code, we approve:

> Approved, build it.

The agent creates a branch and a worktree for the plan. Let us check:

```bash
git worktree list
```

Two lines: the practice repository on `[main]`, and `.worktree/001-slug` on
`[001-slug]`.

The agent works in the worktree, not here. Our own copy is untouched:

```bash
cat greeting.txt
git diff --stat
```

`Hello` alone, and no change.

## Let it build and review

The agent commits in the worktree, runs the checks and the script, has the change
reviewed by an independent reviewer, and appends its notes to the plan. When it is done,
it gives us a summary: what changed and why, the assumptions, the tests and their
results, the limitations, and the manual checks to make. Then it waits.

Let us look at the branch:

```bash
git log --oneline main..001-slug
```

One commit or more, each with a short title in the imperative.

The summary asks us to check the change ourselves. We do, in the worktree:

```bash
cat .worktree/001-slug/greeting.txt
```

`Hello`, then `Bonjour`.

## Confirm the merge

In Claude Code:

> Merge it.

The agent moves the plan and its script to `docs/work/changelog/`, merges the branch,
and removes the worktree and the branch. Let us check each of these:

```bash
git log --graph --oneline
```

A merge commit at the top, `Merge plan 001, ...`, with the commits of the branch on a
line of their own beside `main`.

```bash
git worktree list
```

One line: the worktree is gone.

```bash
ls docs/work/changelog/
cat greeting.txt
```

`001-slug.md` and `001-checks.sh`, then `Hello` and `Bonjour`.

We open `docs/work/changelog/001-slug.md`. Notice the implementation notes at the end:
what each step did, with its commits, and the test results.

## What we did

We took one change through the whole workflow. The agent wrote a plan and stopped; we
approved it; it built the change on its own branch, in its own worktree, while our copy
stayed as it was; it had the change reviewed and told us what it had done; and it merged
only when we said so, as one merge commit. Nothing was pushed: the workflow never
pushes.

To set up a real repository, follow [How to adopt `workflow:plans` in a
repository](../how-to/workflow-adopt-in-a-repository.md). To learn why the workflow
works this way, read [About `workflow:plans`](../explanation/workflow-plans.md).

The practice repository can go:

```bash
rm -rf ~/practice-plans
```
