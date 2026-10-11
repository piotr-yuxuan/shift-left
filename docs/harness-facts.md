# Facts about the Claude Code harness

What the plugins of this repository rely on, with how each fact was established, so
that it can be established again. Run the probes again after an upgrade that touches
plugins or hooks.

Unless an entry says otherwise: Claude Code 2.1.288 on Linux, on 2026-10-10.

- *Seen* means observed on a machine, by the method given.
- *Doc* means the documentation page was read on that date; the page and its section
  are named.

Conventions: `C` is the CLI, set with `C="${CLAUDE_CODE_EXECPATH:-claude}"`, because in
a desktop session `claude` is not on `PATH`. A *scratch command* runs against a
configuration that is not the user's:

```
env -i HOME=<scratch>/home PATH="$PATH" CLAUDE_CONFIG_DIR=<scratch>/config "$C" ...
```

A *debug start* is a scratch command that starts a session with a debug log, with no
credentials. The session fails at its first request, after it has loaded its plugins,
and the log says where each component was read from:

```
... "$C" -p "ok" --max-turns 1 --debug-file <scratch>/debug.log
```

## Configuration and credentials

- **A scratch configuration is separate.** Seen: with a scratch command,
  `plugin marketplace list` shows only the built-in directory and none of the
  marketplaces of the user's own configuration.
- **Plugin commands need no credentials.** Seen for `plugin validate`, `list`,
  `details`, `install`, `update`, `enable`, `disable`, `uninstall`, and for
  `plugin marketplace add`, `list` and `remove`.
- **`HOME` alone also moves the default configuration.** Seen: with `HOME` set to a
  scratch directory and no `CLAUDE_CONFIG_DIR`, the CLI uses `.claude` in that
  directory.
- **The global file follows the variable.** Seen: with `CLAUDE_CONFIG_DIR` set, the CLI
  keeps `.claude.json` inside that directory; without it, in the home directory, next
  to `.claude`. Plugin commands write usage counters there.
- **`plugin validate` exits 0 with warnings.** Seen: a manifest with no `version` and
  no `author` passes with two warnings.

## Where a plugin is loaded from

- **A plugin of a marketplace added from a local directory: a CLI start reads it in
  place, a session of the desktop app reads a cached copy.** Seen, in two settings.
  - *A debug start of the CLI, with a scratch configuration.* A throwaway marketplace
    in a directory, with one plugin holding one skill, was added and installed. A
    second and a third skill were then added to the source directory, with no
    reinstall. `installed_plugins.json` records an install path inside the plugin
    cache, `<config>/plugins/cache/<marketplace>/<plugin>/<version>`, and that
    directory holds a copy made at install time. The session does not read that copy:
    its log names the source directory as the skills path and counts three skills,
    when the copy holds fewer. The log names the source directory for
    `hooks/hooks.json` as well; for agents and language servers it gives a count and
    no path.
  - *A session of the desktop app, with the user's configuration,* and this
    repository registered from a clone. A loaded skill gives its base directory as the
    cached copy, `<config>/plugins/cache/<marketplace>/principles/<commit>/skills/<name>`,
    in the main session and in an agent that names the skill. The report of the hook
    names its command in the cached copy of `quality-ratchet`, and its plugin as
    `quality-ratchet@inline`.
  - `plugin details` reads the source directory. `plugin update` refreshes the copy
    from the source: for a clone that moved to another commit it reports both commits
    and makes a new directory for the new one.

  So in a desktop session the plugins are those of the commit that was installed or
  last updated, and a merge in the clone reaches them only after `plugin update`.
  Whether a CLI session with the user's own configuration reads in place, as the
  scratch one does, was not observed.
- **The path is kept as it was given.** Seen: a marketplace added through a path that
  holds a symbolic link is recorded, and read, through that path. A path with spaces
  and parentheses works.
- **A plugin from a git source loads from a cached copy.** Seen: a marketplace whose
  entries have a `git-subdir` source (`url`, `path`, `ref`), pointing at a local bare
  repository through a `file://` URL. The CLI accepts it and copies the plugin's
  directory alone into the cache; a debug start reads `hooks/hooks.json` and the
  skills from that copy. A hook script keeps its executable bit. This is how other
  people receive a plugin. An install from the published repository is untested until
  the first push.
- **Versions.** Seen: a plugin with no `version` gets the first twelve characters of
  the commit when its marketplace is a git checkout, that commit followed by a hash
  when it comes from a `git-subdir` source, and `unknown` when the marketplace is a
  plain directory. An entry with a `version` keeps it.
- **A marketplace entry is the manifest when the plugin has none.** Seen: the entry of
  `basedpyright-lsp` declares its language server, the plugin directory holds no
  `plugin.json`, and `plugin details` lists the server. Doc: plugin manifest
  reference, "Marketplace entries and the manifest".

## A marketplace that changes its name

`<old>` and `<new>` stand for the name in `marketplace.json` before and after the
change.

- **A registration keeps the name it was made under.** Seen on 2026-10-11, Claude
  Code 2.1.288, with scratch commands. A clone of this repository was added as a
  marketplace while its `marketplace.json` named it `<old>`, and three of its plugins
  were installed. A commit that names it `<new>` was then checked out in the clone.
  `plugin marketplace list` still shows `<old>`, and `plugin list --json` shows each
  `<plugin>@<old>` enabled with no error. `plugin update <plugin>@<old>` takes the new
  commit, and a plugin that was not installed yet installs as `<plugin>@<old>`.
  `plugin install <plugin>@<new>` fails with "not found in marketplace", and
  `plugin update` and `plugin disable` of `<plugin>@<new>` exit 1. A debug start in
  the clone still reads `hooks/hooks.json` from the clone and registers the hook, and
  its log counts the skills, the agent and the language server.
- **The new name is taken by removing the marketplace and adding it again.** Seen on
  2026-10-11, Claude Code 2.1.288, with scratch commands, from the state of the entry
  above. In this order, `plugin uninstall <plugin>@<old>` for each plugin,
  `plugin marketplace remove <old>`, `plugin marketplace add <clone>` and
  `plugin install <plugin>@<new>` for each plugin: every command exits 0.
  `settings.json` then holds only the ids `<plugin>@<new>` and the marketplace
  `<new>`; a key that these commands do not own, and the mode of the file, are as
  before. The directory `<config>/plugins/cache/<old>/` stays behind, and each version
  directory in it has gained a file `.orphaned_at`. `plugin uninstall` of a plugin
  that is not installed exits 1. `plugin marketplace remove` alone also uninstalls the
  plugins of the marketplace, and says so: seen with a throwaway marketplace. It then
  deletes the folder `<config>/plugins/data/<plugin>-<marketplace>/` of each of them,
  and says that it deletes their data where it can; after
  `plugin uninstall --keep-data` the removal leaves that folder: seen with the same
  marketplace and a folder made by hand, with one file in it. A start removes the
  file `.orphaned_at` from a cached copy that `installed_plugins.json` names again:
  seen with the same marketplace, by one debug start made once `settings.json`,
  `installed_plugins.json` and `known_marketplaces.json` were put back from copies
  made before the uninstall; until that start the file was still there.
- **A plugin may have the name of its marketplace.** Seen on 2026-10-11, Claude Code
  2.1.288, with scratch commands: a throwaway marketplace in a directory, whose one
  plugin has the name of the marketplace, passes `plugin validate`, and the plugin
  installs as `<name>@<name>`. `plugin list --json` shows it enabled with no error.

## Skills that an agent names

- **A missing skill is not reported.** Seen: an agent whose `skills:` list names one
  skill of its own plugin as `plugin:skill` and one that does not exist. `plugin
  validate` passes, `plugin details` lists the agent, and the log of a debug start
  says nothing about the missing skill. Whether such an agent then runs normally was
  not observed.
- **An agent receives the skills that its `skills:` list names.** Seen, in a session
  of the desktop app: the reviewer agent of `principles`, told to make no tool call,
  quoted one bullet of one skill word for word and gave the four section titles of the
  other. Its transcript holds no tool call but the one that returns its answer, and
  shows both skills under their `plugin:skill` names.

## Instructions

- **A plugin cannot ship always-on instructions.** Doc: plugin manifest reference,
  "Standard layout": "A `CLAUDE.md` at the plugin root isn't loaded as context". The
  same page says that of a plugin's settings only `agent` and `subagentStatusLine`
  take effect.
- **A user-level `CLAUDE.md` may import a file anywhere, with no approval dialog.**
  Doc: memory page, "Import additional files": relative and absolute paths are allowed,
  a space in a path needs a backslash before it, and imports of user-scope files load
  without the dialog that project files get. The same section says that Cowork
  sessions skip an import of a user-scope file that resolves outside the session's
  working directory. Seen, in a session of the desktop app's Code tab: a user-level
  `CLAUDE.md` that is one import line, an absolute path that goes through a symbolic
  link to a directory, loads the file, and the session lists it among the user's
  instructions. The Cowork case was not observed.
- **`AGENTS.md` is read when no `CLAUDE.md` exists in the working directory or above
  it.** Doc: memory page, "When Claude Code reads AGENTS.md". The user-level
  `CLAUDE.md` does not count for that check. Every `AGENTS.md` in the working
  directory and the directories above it is read, so a session in a linked worktree
  below a checkout reads both files. Seen: a session whose working directory was a
  checkout with no `AGENTS.md` received the `AGENTS.md` of a linked worktree below it
  when it first read a file there.

## Hooks

- **The plugin root in a hook command.** Doc: plugin manifest reference, "Environment
  variables": `${CLAUDE_PLUGIN_ROOT}` resolves inline anywhere in a hook's `command`
  and is also exported to the hook process; in a shell-form command it goes inside
  double quotes, so that a path with spaces stays one word. Seen, as a test of this
  repository: with the variable replaced by a directory whose name holds spaces and
  parentheses, the command of `plugins/quality-ratchet/hooks/hooks.json` runs the
  script under bash, and without the quotes it does not.
- **A hook after an edit runs in the main session and in a subagent, whether user
  settings or a plugin register it.** Seen twice in a session of the desktop app:
  with the hook in the user settings, then with the hook shipped by the plugin. In a
  scratch git repository, the main session and a subagent each made one edit that
  added one bugbear problem to a file of their own; neither was told about the hook.
  Each time, the transcript of each gained exactly one record with the report for its
  file: an attachment of type `hook_blocking_error` for the event `PostToolUse`. The
  same probe for an agent started by a workflow is still to run.

## Scripts that a skill brings

- **An agent that loads a skill of a plugin is told where the skill is, and can run
  the files beside it.** Seen, in a session of the desktop app, with a skill of
  another plugin: on loading the skill, the main session, a subagent and an agent
  started by a workflow were each shown one line,
  "Base directory for this skill: <absolute path>", and each could list and run files
  under that path. The path is in the cached copy of the plugin, at the commit that
  was installed or last updated (see "Where a plugin is loaded from"). The same with
  a skill of `coordinator` is still to be seen, after its first install.
- **The shell of an agent has no variable that names the plugin or the project.**
  Seen: `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PROJECT_DIR` are unset in the shell of an
  agent. Doc: plugin manifest reference, "Where each variable resolves": the variables
  are not in the environment of the commands that Claude runs through its shell tool,
  in the main session or in a subagent, and a `${...}` reference in the body of a
  skill is replaced by the path when the skill is loaded. That replacement was not
  observed, and the skill of `coordinator` does not use it.
- **A `bin/` directory.** Doc: plugin manifest reference, "Standard layout": the
  files of a plugin's `bin/` directory are on the `PATH` of the shell tool while the
  plugin is enabled. Not observed, and no plugin of this repository relies on it.

## Workflow runs and transcripts

What `minutes.py` of `coordinator` reads. Seen in the records that the harness keeps
for the sessions of one machine; `<project>` stands for the directory that it keeps
for a project, and `<session>` for the identifier of a session.

The script refuses a run record in which a key that it reads is missing or has
another type, a `done` agent with no `durationMs` included. In a transcript it
refuses a line that is not a JSON object, except a last line that does not parse; a
`timestamp` that it reads and that is not a date with an offset; and `user` or
`assistant` records of which none starts a turn. A version of the harness that drops
or retypes a key of the run record, that retypes a `timestamp` that the script
reads, that drops the `timestamp` of the `user` records that start turns or of every
`user` and `assistant` record, or that drops `turnOrigin`, shows as a failure.

The script does not refuse a value that it does not know: an entry of
`workflowProgress` of a type other than `workflow_phase` and `workflow_agent` is
ignored, an agent in a state other than `done` counts as not finished, and a
transcript record of another type or subtype is no event and no stop record. Nor
does it refuse a `user` or `assistant` record with no `timestamp`, which is no
event. A version of the harness that renames one of these values, or that drops the
`timestamp` of the `assistant` records alone, gives wrong figures with status 0, so
see these facts again after an upgrade.

- **A run record exists only once its run has ended.** Seen, 41 run records: the
  record of a workflow run is `<project>/<session>/workflows/<runId>.json`. The
  transcripts of the agents of the run are in
  `<project>/<session>/subagents/workflows/<runId>/`, and the transcript of the main
  session is `<project>/<session>.jsonl`. The copy of the script of the run may be
  under the directory of another project.
- **What a run record holds.** Seen, 41 run records and 546 agents: `runId`, `status`
  (`completed` or `killed`), `startTime` and `durationMs` in milliseconds, and
  `workflowProgress`, a list of entries. An entry of type `workflow_phase` has `index`
  and `title`. An entry of type `workflow_agent` has `phaseTitle`, `state`,
  `startedAt`, and `durationMs` exactly when its `state` is `done`. The top-level
  `timestamp` is the end of the run. The record names no version of the harness. Its
  `label`, `promptPreview`, `resultPreview`, `summary`, `logs`, `result`, `script` and
  `error` hold text of the session, which may be private.
- **A killed run.** Seen, 7 killed runs: an agent that was running when its run was
  killed stays with `state` `progress` and no `durationMs`. A phase that was declared
  and never reached has a phase entry and no agent.
- **Agents, phases and runs overlap.** Seen: the agents of one phase overlap without
  starting together, phases overlap each other, the runs of one session overlap, and
  labels repeat inside a run. `durationMs` counts from `startedAt`: an agent can wait
  in a queue for minutes before it starts. An agent that the harness tried again, and
  a run that was resumed, were not seen.
- **The records of a main transcript.** Seen, 6 transcripts: records of type `user`
  and `assistant` carry `timestamp`, an ISO 8601 string that ends in `Z`. So do
  records of type `system`, `attachment` and `queue-operation`; records of other
  types carry none. The order of the lines is not the order of time. No record gives
  the duration of a turn. The transcript of a session is being written while that
  session reads it.
- **The turns of the main session.** Seen: a turn starts at a `user` record that has
  the key `turnOrigin`, and ends at a `system` record of subtype `stop_hook_summary`,
  which carries a `timestamp`; 91 of 91 completed turns have both. The values of
  `turnOrigin` seen in the 6 transcripts are `human`, `task_notification` and `peer`.
  Whether the stop record exists when no Stop hook is configured is not known.
- **Subagent records are not mixed into the main transcript.** Seen: `isSidechain` is
  false on every record of the 6 transcripts.
- **What the workflow tool answers.** Seen, in the 6 transcripts: the result of the
  workflow tool is a structured object with `runId`, `taskId`, `transcriptDir` and
  `scriptPath`. The run record is `workflows/<runId>.json` three directories above
  `transcriptDir`, for 41 of 41 runs that had ended.
- **A workflow script cannot read a file.** Doc: the skill `workflow-authoring` that
  the harness bundles and loads in a session, where it describes the body of a script:
  no access to the file system or to the Node.js API. Seen, in an earlier workflow
  run: a script that read a file failed at that read.
- **An agent call of a workflow script can carry a JSON Schema.** Seen: the harness
  validates the answer of the agent against the schema that the script passes. Which
  keywords of the schema the harness enforces was not determined.
- **A message that the user sends while a workflow runs is shown to its agents.**
  Seen, in a run of two agents: a message that the user sent to the main session
  during the run appeared in the context of both agents, and each reported it as a
  request that it had not carried out.

## Other tools

What the scripts of `coordinator` and their tests rely on outside Claude Code.

- **`git check-ignore` answers for a file that does not exist yet.** Seen, git
  2.54.0, in a scratch repository: `git check-ignore -q <absolute path>`, run from the
  nearest directory above the path that exists, exits 0 for a path that an ignore
  rule covers, 1 for a path that none covers and 128 outside a repository, whether or
  not the file and its parents exist. An ignore rule given through
  `GIT_CONFIG_COUNT`, `GIT_CONFIG_KEY_0` and `GIT_CONFIG_VALUE_0` changes the answer.
  A repository that is reached through a symbolic link is answered for; a path that
  enters the repository through a symbolic link from outside exits 128.
- **`git worktree remove` deletes the ignored files of the worktree.** Seen, git
  2.54.0, in a scratch repository: a linked worktree that held one ignored file and
  no other change was removed without `--force`, and the file with it.
- **Three traps of Python.** Seen, Python 3.14: `isinstance(True, int)` is true;
  `json.loads` accepts `NaN`; `re.search` lets `$` match before a final line break.
- **`datetime.fromisoformat` reads a `Z` suffix.** Seen, Python 3.14. Doc: library
  reference, `datetime.fromisoformat`, "Changed in version 3.11": from that version.
- **A lock on a directory.** Seen, Linux, local file system: `fcntl.flock` on a
  descriptor of a directory excludes another process that locks the same directory,
  the `flock` command included, and creates no file.
- **jq prints a number as it was written.** Seen, jq 1.8.2: `30.0` stays `30.0`, so it
  does not compare equal to `30` as text.

## Removing

- **Removing a local-directory marketplace leaves its directory alone.** Seen: a
  throwaway marketplace was added from a directory, its plugin installed and
  uninstalled, and the marketplace removed; the directory held the same six files
  before and after.
- **Uninstalling leaves the cached copy behind.** Seen: after `plugin uninstall`, the
  directory under `plugins/cache` is still there. Whether a later session removes it
  was not observed.
- **The CLI keeps the mode of `settings.json`.** Seen: a file of mode 600 keeps it
  through `plugin install`, `uninstall`, `marketplace add` and `marketplace remove`.
