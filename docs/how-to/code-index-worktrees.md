# How to give each worktree its own code index

This guide sets up a repository so that each linked worktree an agent adds gets a codegraph
index of its own, and codegraph answers about the worktree's branch rather than about the main
worktree's. It uses the plugin `code-index` in Claude Code.

## Install codegraph and the plugin

Install codegraph as its own documentation says, so that `codegraph` is on `PATH`. Then, with
the marketplace added as the [README](../../README.md#install-in-claude-code) shows:

```bash
claude plugin install code-index@shift-left
```

## Index the main worktree

The plugin indexes the worktrees of a repository only once you have indexed its main worktree.
In the main worktree:

```bash
codegraph init -y .
```

## Ignore the index folder

Ignore the folder `.codegraph/` itself, either for every repository in your global ignore file,
the one that `git config core.excludesFile` names or else `~/.config/git/ignore`:

```
.codegraph/
```

or for one repository, in its `.gitignore`:

```
/.codegraph/
```

Do not ignore only the folder's contents, as `.codegraph/*` does: codegraph writes a
`.codegraph/.gitignore` that ignores everything but itself, and that file then shows as
untracked, which stops `git worktree remove`. Without any rule on the folder, the plugin does
not index the worktree at all, and says why when a session starts in it.

## Check it

In a session in the main worktree, ask the agent to add a worktree, for example with
`git worktree add .worktree/try -b try`. Once the command has run:

```bash
ls .worktree/try/.codegraph
```

lists `codegraph.db`, and the agent has been told, in its context, to query the worktree by its
path. A session started in `.worktree/try` is told that the worktree has an index of its own.

## Remove a worktree

`git worktree remove` deletes the ignored index with the worktree; nothing else is needed. If it
refuses because of `.codegraph/`, run `codegraph uninit -f .` in the worktree, then remove it
again, never with `--force`.

## In another client

The hooks run in Claude Code. In another client, after adding a worktree, run the script of the
skill `code-index` on it:

```bash
<skill directory>/code_index.py .worktree/try
```

## See also

- The skill `code-index`, [`plugins/code-index/skills/code-index/SKILL.md`](../../plugins/code-index/skills/code-index/SKILL.md),
  for how an agent queries a worktree.
