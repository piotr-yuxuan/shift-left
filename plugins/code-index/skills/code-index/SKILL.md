---
name: code-index
description: Get codegraph answers about a linked git worktree rather than about the main worktree. Use before a codegraph query about files of a linked worktree, after adding a worktree in a client without the hooks of this plugin, and when git refuses to remove a worktree because of its .codegraph folder.
---

# Code index

codegraph answers from the nearest `.codegraph/` at or above the path it is given. A linked
worktree inside the main worktree, such as `.worktree/<name>`, has none of its own until one is
made, so until then it is answered from the main worktree's index: that branch's files, not its
own.

- Before a codegraph query about files of a linked worktree, pass the worktree's path as the
  project path. Without it, the session's default project answers.
- Such a query answers for the branch only where the worktree holds `.codegraph/`. Where it does
  not, take no answer for the branch's file: read the file.
- In Claude Code, the hooks of this plugin index a worktree after a command that adds it and
  when a session starts in it, where the main worktree holds `.codegraph/` and git ignores
  `.codegraph/`, and they say so in the context. In another client, after adding a worktree,
  run the script beside this file:

      <this skill's directory>/code_index.py <worktree>

  It prints `indexed <root>`, `has an index <root>` or `not indexed <path>: <reason>`.
- If `git worktree remove` refuses a worktree because of `.codegraph/`, as it does where a rule
  ignores only the folder's contents, such as `.codegraph/*`: run `codegraph uninit -f .` in the
  worktree, then remove it again. Never remove it with `--force`, which would also discard every
  other untracked file in it.
