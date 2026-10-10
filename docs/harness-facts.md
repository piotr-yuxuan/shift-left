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
    cached copy, `<config>/plugins/cache/piotr-yuxuan/principles/<commit>/skills/<name>`,
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
