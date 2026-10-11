# Facts about the clients and the standards

What the plugins of this repository rely on, with how each fact was established, so
that it can be established again. There is one section per client, then one for the
two standards that the plugins are packaged for. Each fact carries its client, the
version, the date and the method, or takes them from the head of its section. Run the
probes of a client again after an upgrade of it that touches plugins or hooks.

- *Seen* means observed on a machine, in a running client or tool, by the method
  given.
- *Static* means read in the files of an installed client, or run from them outside
  the client, and not observed in a running one.
- *Doc* means the documentation page was read on that date; the page and its section
  are named. Where the head of a section says so, the page was read as page text.

## Claude Code

Unless an entry says otherwise: Claude Code 2.1.288 on Linux, on 2026-10-10.

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

### Configuration and credentials

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

### Where a plugin is loaded from

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

### A marketplace that changes its name

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

### Skills that an agent names

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

### Instructions

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

### Hooks

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

### Scripts that a skill brings

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

### Workflow runs and transcripts

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

### Other tools

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

### Removing

- **Removing a local-directory marketplace leaves its directory alone.** Seen: a
  throwaway marketplace was added from a directory, its plugin installed and
  uninstalled, and the marketplace removed; the directory held the same six files
  before and after.
- **Uninstalling leaves the cached copy behind.** Seen: after `plugin uninstall`, the
  directory under `plugins/cache` is still there. Whether a later session removes it
  was not observed.
- **The CLI keeps the mode of `settings.json`.** Seen: a file of mode 600 keeps it
  through `plugin install`, `uninstall`, `marketplace add` and `marketplace remove`.

### Probe Q1: a root manifest of the standard beside Claude Code's

Seen on 2026-10-11, Claude Code 2.1.288, with scratch commands, on two clones of this
repository made with `git clone --no-local`. *Before* is at the commit just before
the one that adds a root `plugin.json` to `principles` and to `coordinator`. *After*
is four commits later: it has the two root manifests, each with a `version` of
`0.0.0`; one word of a docstring and two sentences of the skill `instrument` differ
too.

- **Claude Code validates and shows its own manifest, with or without a root one.**
  On both clones `plugin validate .` and `plugin validate plugins/<name>` exit 0, and
  the second names `.claude-plugin/plugin.json` as the manifest that it validates.
  After `plugin marketplace add <clone>` and `plugin install <plugin>@shift-left` for
  the four plugins, `plugin details` of each prints the same description, source and
  component inventory on both clones. The description is the one of
  `.claude-plugin/plugin.json`, and not the shorter one of the root manifest. Below
  the line `Projected token cost` one estimate differs, that of the skill whose text
  changed.
- **A start loads the same components with and without a root manifest.** The log of
  a debug start reads `hooks/hooks.json` of `quality-ratchet`, counts 2 skills and 1
  agent for `principles` and 1 skill for `coordinator`, and loads 1 language server
  from `basedpyright-lsp`: the same lines on both clones, two of them in another
  order.
- **A plugin directory given with `--plugin-dir` loads for one session.** With no
  marketplace and no install, a debug start with `--plugin-dir <clone>/plugins/<name>`
  for `principles`, `coordinator` and `quality-ratchet` logs the same counts and the
  same hook file, on both clones. The log says of each directory that the
  `.claude-plugin` at its top marks it as one plugin.
- **A cached copy holds the root manifest and loads the same.** *After* again, each
  of three plugins installed from a `git-subdir` source over `file://` to a local
  bare clone, which is how other people receive a plugin: the skills paths and the
  hook file that the log names are under `<config>/plugins/cache/`, the copies of
  `principles` and `coordinator` there hold the root `plugin.json`, and the counts
  are the same.
- **The version of a root manifest is not the version that Claude Code lists.** On
  *after*, `plugin list` shows `principles` and `coordinator` at the first twelve
  characters of the commit, and at that commit followed by a hash when they come
  from the `git-subdir` source: nowhere at `0.0.0`.

The check to repeat after an upgrade of Claude Code, on a clone: the validation
commands of `AGENTS.md`; `plugin marketplace add <clone>`, `plugin install`,
`plugin details` and `plugin list`; a debug start, whose log is searched for
`Read hooks.json for plugin`, `Loaded <n> skills from plugin` and
`Loaded <n> agents from plugin`. A version that came to read the root manifest would
show there first: in the description that `plugin details` prints, in the version
that `plugin list` prints, in the counts of the log.

## VS Code

Nothing below was seen in a running VS Code: no window was opened and no account was
used. The page is "Agent plugins in VS Code",
`code.visualstudio.com/docs/agent-customization/agent-plugins`, dated 2026-10-07 and
read as page text on 2026-10-11.

- **A root `plugin.json` that declares the schema of the standard sets the format of
  the plugin.** Doc: "Plugin formats". VS Code detects the format of a plugin from
  its manifests. A root `plugin.json` whose `$schema` is the one of the standard
  gives the plugin the semantics of Agent Plugins; `.claude-plugin/plugin.json` is
  the manifest of the Claude format, `.plugin/plugin.json` that of a legacy format,
  and a root `plugin.json` with no such schema that of the Copilot format, the
  default. "Cross-tool compatibility": a plugin that does not declare the schema
  keeps the discovery rules of its own format.
- **In the Agent Plugins format, agents and hooks come from `com.github.copilot/`.**
  Doc: "Plugin manifest (plugin.json)". Skills are found in `skills/` and servers of
  the Model Context Protocol in `mcp.json`, and the manifest lists neither. What is
  Copilot's own lives in the directory `com.github.copilot/` at the root of the
  plugin: `agents/`, `commands/`, `rules/` and `hooks/hooks.json`. "Hook file
  location": the hook file is `com.github.copilot/hooks/hooks.json` in the Agent
  Plugins format, `hooks/hooks.json` in the Claude format, and `hooks.json` at the
  root in the Copilot format. "Reference plugin paths in hook commands" gives
  `agents/reviewer.md` as an agent that a plugin of the Claude format brings. So, by
  the page, `agents/principles-reviewer.md` of `principles` was read while the plugin
  had only Claude Code's manifest, and is no longer read now that it has a root
  manifest. Nobody saw the agent run in VS Code, before or after.
- **Probe Q2a: the format and the directories that the installed VS Code reads, for
  each plugin of this repository.** Static, on 2026-10-11, VS Code 1.140.0, the one
  installed, and again 1.139.1, with the same result. VS Code was not started. From
  `resources/app/out/vs/workbench/workbench.desktop.main.js` of the package, one
  region was cut out as it is written there, from the constant that holds the
  address of the manifest schema to the end of the function that resolves the paths
  of a component, and with it the two functions that read a JSON file and test that
  a file exists. It was run in `node` on each plugin directory of the two clones of
  probe Q1. Three things were written for the run and are not the code of VS Code:
  a file service on the `fs` of node; four helpers that join, normalise, compare and
  parse, with `JSON.parse` in the place of a reader that also takes comments; and
  the list of the components with the default path of each, copied from the method
  of the same bundle that builds a plugin.

  | Plugin | Before the root manifests | With them |
  |--------|---------------------------|-----------|
  | `principles` | Claude format, from `.claude-plugin/plugin.json`. Skills from `skills/`, agents from `agents/`, hooks from `hooks/hooks.json`, which it has not | Agent Plugins format, from the root `plugin.json`. Skills from `skills/`. Agents from `com.github.copilot/agents` and hooks from `com.github.copilot/hooks/hooks.json`, and it has neither |
  | `coordinator` | Claude format. Skills from `skills/`; it has no `agents/` and no hook file | Agent Plugins format. Skills from `skills/` |
  | `quality-ratchet` | Claude format. Hooks from `hooks/hooks.json`, which it has | the same: it has no root manifest |
  | `basedpyright-lsp` | the default format, since no manifest is found; none of the paths of that format exists in it | the same |

  So `agents/principles-reviewer.md` is read before the root manifest and no longer
  with it. A path that the root manifest declares for agents under
  `extensions["com.github.copilot"]` is kept when it stays inside
  `com.github.copilot/`, and dropped when it leaves it: `../agents` was dropped. The
  test of `$schema` takes any address that starts with
  `https://agent-plugins.org/schemas/` and ends with `/plugin.schema.json`. This
  shows what is read, never that a component works. The check to repeat after an
  upgrade of VS Code is this run.

  The script of that run is not in the repository: the run is made again from this
  description. Minified names change with each version, so each piece is found by
  what its code holds, the same in the two versions. The region starts at the `var`
  that is given the address of the manifest schema and ends with the function that
  holds `e.exclusive||` and `for(let r of e.paths)`. In it, the function that picks
  the format is the `async function` of two parameters whose body starts with
  `return await` and tests the root manifest, then `.plugin/plugin.json`, then
  `.claude-plugin/plugin.json`; the one that reads the manifest starts with
  `if(o.format===3)`; the one that reads what a manifest declares for a component
  starts with `if(s.manifestExtensionNamespace)`; the one that gives the paths of a
  component starts with `let r=o.componentPaths?.[e]`. The two functions outside the
  region stand together: one returns what `o.readFile(s)` gave, parsed, the other
  `await o.resolve(s),!0`. The default path of each component is read in the method
  that calls one function with `"commands"`, `"skills"`, `"agents"`, `"rules"`,
  `"automations"`, `"hooks"` and `"mcpServers"`, in that order, the last with
  `".mcp.json"`; the run left `"automations"` out. When a piece is not found the
  bundle has another shape, and the run reports nothing. Whoever makes the run again
  checks first that each directory exists: the code of VS Code reads a directory that
  does not exist as a plugin with no manifest, as it reads `basedpyright-lsp`.
- **A marketplace file is looked for at four paths.** Static, the same bundles, by
  reading: `marketplace.json`, `.plugin/marketplace.json`,
  `.github/plugin/marketplace.json` and `.claude-plugin/marketplace.json`, listed in
  that order. That bundle nowhere names `lspServers`, the field by which the entry of
  `basedpyright-lsp` declares its language server; a bundle of the built-in
  extension `copilot` does. The extension `copilot` is among the built-in ones.
- **On the Local harness a hook runs whatever its matcher says.** Doc: "Hooks in
  plugins" and "Hook configuration format". What a hook is given and how it is
  configured depend on the harness of the session, and the page describes the Local
  one. Its parser accepts the hook configuration of Claude Code, matchers included,
  and ignores the value of a matcher, so that every command nested under an event
  runs. The page tells authors to check the input of the event inside the script.
  A hook of a Claude-format plugin gets `${CLAUDE_PLUGIN_ROOT}` expanded in its
  command and set in its environment.
- **How a plugin is added.** Doc. "Configure plugin marketplaces": the setting
  `chat.plugins.marketplaces` names marketplaces, each a git repository, as
  `owner/repo`, as a git address, or as a `file:///` address of a repository already
  cloned on disk; for the schema of the entries the page sends to the documentation
  of Claude Code. "Use local plugins": the setting `chat.pluginLocations` maps the
  path of a plugin directory to enabled or disabled. "Install a plugin from source":
  the command `Chat: Install Plugin From Source` takes the address of a git
  repository.
- **A version that does not update.** Doc: "Troubleshooting", "Plugin version does
  not update": the page tells authors to raise `version` in `plugin.json`, and in the
  entry of the marketplace file where there is one, before they push. "Update
  plugins": an update pulls the changes of the cloned marketplace repositories.
- **The name of a skill is plain.** Doc: "Troubleshooting", "Skills from a plugin do
  not load": the `name` of a skill has no namespace prefix and equals the name of
  its directory, and a skill with an invalid name is skipped in silence. The page
  does not say how VS Code names a skill of a plugin to its agent.

## GitHub Copilot CLI

Nothing was seen: the client is not installed on the machine of these probes. The
page is "GitHub Copilot CLI plugin reference",
`docs.github.com/en/copilot/reference/copilot-cli-reference/cli-plugin-reference`,
read as page text on 2026-10-11.

- **A root manifest of the standard takes precedence over the other manifests.**
  Doc: "File locations". For Agent Plugins 1.0.0 or 1.1.0 the manifest is
  `plugin.json` at the root of the plugin, and it takes precedence over
  `.plugin/plugin.json` and `.claude-plugin/plugin.json`. The manifest of a legacy
  plugin is looked for at `.plugin/plugin.json`, `plugin.json`,
  `.github/plugin/plugin.json` and `.claude-plugin/plugin.json`, in that order.
- **Agents and hooks come from the root of a legacy plugin, and from
  `com.github.copilot/` of an Agent Plugins one.** Doc: "File locations": for a
  legacy plugin, agents from `agents/` and hooks from `hooks.json` or
  `hooks/hooks.json`. "Components": for a plugin of the standard, skills from the
  immediate subdirectories of `skills/` that hold a `SKILL.md`, servers from
  `mcp.json`, and the components that are its own from `com.github.copilot/`:
  `agents/`, `commands/`, `rules/`, `hooks/hooks.json` and `lsp.json`. The section
  says that these places hold for plugins of the standard only, and that a legacy
  plugin keeps its own. So, by the page, `agents/principles-reviewer.md` of
  `principles` was read while the plugin had only Claude Code's manifest, and is no
  longer read now that it has a root manifest. Nobody saw the agent run in this
  client, before or after.
- **The marketplace file and its sources.** Doc: "File locations": `marketplace.json`,
  `.plugin/marketplace.json`, `.github/plugin/marketplace.json` and
  `.claude-plugin/marketplace.json`, checked in that order. "Plugin source types":
  the source of an entry is a relative path, or an object that names a repository
  on GitHub or a git address.
- **A language server needs `fileExtensions`.** Doc: "LSP server configuration": the
  field `fileExtensions`, from file extensions to language names, is required. The
  entry of `basedpyright-lsp` has `extensionToLanguage` in its place.
- **What its install command takes.** Doc: "Plugin specification for install
  command": a plugin of a registered marketplace, as `plugin@marketplace`; a
  repository on GitHub, or a subdirectory of one; a git address; a local path.
- **A project or personal skill wins over a skill of a plugin.** Doc: "Loading order
  and precedence": for agents and skills the first found wins, and a skill of a
  plugin with the name of a project or personal one is ignored in silence. Skills
  are told apart by the `name` of their `SKILL.md`.

## Codex

Nothing was seen: no probe ran. The page is "Package your plugin",
`developers.openai.com/plugins/build/plugins`, read as page text on 2026-10-11.

- **The root `plugin.json` is the portable entry point, and other manifests are
  accepted.** Doc: "Plugin structure": the page calls the root `plugin.json` the
  portable entry point, and says that legacy and Claude-compatible manifests are
  accepted too. "Add OpenAI-specific metadata": what is Codex's own goes under
  `extensions.com.openai` of the root manifest.
- **`hooks/hooks.json` of a plugin is discovered by default.** Doc: "Bundled MCP
  servers and lifecycle hooks". Lifecycle hooks are supported for plugins installed
  by hand in the desktop app. A hook of a plugin is skipped until the user has
  reviewed and trusted it. `hooks/hooks.json` is discovered by default when the
  manifest defines no hooks; hooks defined under `extensions.com.openai` replace
  that discovery and do not add to it. A hook command is given `PLUGIN_ROOT` and
  `PLUGIN_DATA`, and `CLAUDE_PLUGIN_ROOT` and `CLAUDE_PLUGIN_DATA` for
  compatibility. On the page `com.openai` is each time a key of a manifest and never
  a directory: "Plugin structure" keeps the hook files and the other files of Codex
  at the root of the plugin.
- **Marketplace files.** Doc: "How local marketplaces work": a marketplace file is
  read from `.agents/plugins/marketplace.json` of a repository, from
  `.claude-plugin/marketplace.json` of a repository as a legacy-compatible place,
  and from a personal file under the home directory. "Marketplace metadata": the
  source of a local entry may be a plain path, and every entry is asked to carry a
  policy and a category. "Add a marketplace from the CLI":
  `codex plugin marketplace add` takes `owner/repo`, a git address or the root
  directory of a local marketplace, and the page sends the install and the test of
  a local plugin to the desktop app.

## The standards

### Agent Plugins 1.0.0

Read as page text on 2026-10-11: the specification, `agent-plugins.org/specification`,
which gives its version as 1.0.0 and its status as published; its manifest schema,
`agent-plugins.org/schemas/1.0.0/plugin.schema.json`; and its list of compatible
clients, `agent-plugins.org/compatible-clients`.

- **A plugin is a directory with a `plugin.json` at its root.** Doc: specification,
  4.1 "General requirements" and 5.1 "Location and loading". There is one portable
  manifest per plugin, and no other file replaces, supplements or overrides its
  fields.
- **The schema of the manifest is closed.** Doc: specification, 5.2 "Manifest
  object", and the schema file. The fields allowed at the top are `$schema`, `name`,
  `version`, `description`, `author`, `homepage`, `repository`, `license`, `keywords`
  and `extensions`. `$schema` and `name` are required. `$schema` is the address of
  the schema file. `name` has 1 to 64 characters and matches
  `^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$`. `version`, `description`,
  `homepage`, `repository` and `license` are strings, with no pattern. `author` is an
  object that holds only `name`, `email` and `url`, each a string. `keywords` is a
  list of strings. Each value of `extensions` is an object.
- **What a client does with a manifest that breaks the schema.** Doc: specification,
  5.2 and 8.1 "Manifest extension data". A field at the top that the schema does not
  know is reported and ignored, and the plugin still loads. So is an `extensions`
  that is not an object. Any other fault is fatal: the client rejects the plugin and
  loads none of its components.
- **Two kinds of portable component, at fixed places.** Doc: specification, 7.1
  "Skills": each immediate child directory of `skills/` that holds a `SKILL.md` is
  one skill, with no deeper search; a skill that does not follow Agent Skills is
  skipped, and the others load. 6.1 "Fixed locations" and 7.2 "MCP servers": a
  `mcp.json` at the root. "Design Decisions", "Why only Agent Skills and MCP in
  v1?": commands, hooks, agents, rules and language servers are left out as too
  specific to each client.
- **What belongs to one client has a namespace.** Doc: specification, 8.1 and 8.2
  "Extension directories". Data of one client go under `extensions.<namespace>` of
  the manifest, and its files in a directory at the top of the plugin named after
  the namespace, a reversed domain name; a client ignores the namespaces that it
  does not implement. Claude Code's files in this repository, `.claude-plugin/`,
  `agents/` and `hooks/`, are in no such directory: Claude Code is not a client of
  the standard and would not find them there.
- **The version of a plugin.** Doc: specification, 5.4 "Metadata fields" and 10.2
  "Plugin versions". It is a string; Semantic Versioning is recommended and not
  required; a client may use it to tell whether an update exists and whether a
  cache is stale.
- **The clients on the list.** Doc: the list of compatible clients: OpenHands, GitHub
  Copilot, NanoClaw, Grok Bot, ChatGPT and Codex, Cursor, VS Code, OpenClaw, Hermes
  Agent and Kiro, each shown with Agent Skills among what it loads. Claude Code is
  not on it. The entry reads GitHub Copilot and does not name its CLI.

### Agent Skills

Read as page text on 2026-10-11: the specification, `agentskills.io/specification`.

- **The front matter of a `SKILL.md`.** Doc: "SKILL.md format", "Frontmatter". `name`
  and `description` are required; `license`, `compatibility`, `metadata` and
  `allowed-tools` are optional. `name` has 1 to 64 characters, lower-case letters,
  digits and hyphens only, no hyphen at either end and no two hyphens in a row, and
  equals the name of the directory of the skill. `description` has 1 to 1024
  characters. `compatibility` has 1 to 500. `metadata` maps text to text.
- **A plain value of the subset that the tests read is the same string to a YAML
  reader.** Seen on 2026-10-11, Python 3.14.7 and yq 4.54.1. The tests of
  `tests/packaging/` read the front matter as lines `<key>: <value>` and accept a
  value only when it starts with an ASCII letter, holds no colon followed by a space,
  no colon at its end and no `#` after a space, has printable characters only and no
  space at either end, and is not a word that YAML reads as a boolean or as null.
  12000 distinct values that this rule accepts, drawn at random from the special
  characters of YAML, were written as such lines and read by `yq`: each came back as
  the same string.
