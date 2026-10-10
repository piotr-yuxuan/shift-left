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

- **A plugin of a marketplace added from a local directory loads in place.** Seen. A
  throwaway marketplace in a directory, with one plugin holding one skill, was added
  and installed. A second and a third skill were then added to the source directory,
  with no reinstall.
  - `installed_plugins.json` records an install path inside the plugin cache,
    `<config>/plugins/cache/<marketplace>/<plugin>/<version>`, and that directory
    holds a copy made at install time.
  - A session does not read that copy: the log of a debug start names the source
    directory as the skills path and counts three skills, when the copy holds fewer.
    The log names the source directory for `hooks/hooks.json` as well; for agents and
    language servers it gives a count and no path.
  - `plugin details` reads the source directory too. `plugin update` refreshes the
    copy from the source.

  So a clone registered this way is live configuration, uncommitted edits and the
  checked-out branch included.
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
  working directory. Not yet seen here; an import through a symbolic link in the path
  is not documented.
- **`AGENTS.md` is read when no `CLAUDE.md` exists in the working directory or above
  it.** Doc: memory page, "When Claude Code reads AGENTS.md". The user-level
  `CLAUDE.md` does not count for that check. Every `AGENTS.md` in the working
  directory and the directories above it is read, so a session in a linked worktree
  below a checkout reads both files.

## Hooks

- **The plugin root in a hook command.** Doc: plugin manifest reference, "Environment
  variables": `${CLAUDE_PLUGIN_ROOT}` resolves inline anywhere in a hook's `command`
  and is also exported to the hook process; in a shell-form command it goes inside
  double quotes, so that a path with spaces stays one word. Seen, as a test of this
  repository: with the variable replaced by a directory whose name holds spaces and
  parentheses, the command of `plugins/quality-ratchet/hooks/hooks.json` runs the
  script under bash, and without the quotes it does not.
- **A hook after an edit runs in the main session and in a subagent.** Seen, with the
  hook registered in the user settings, before it moved into a plugin. In a scratch git
  repository, the main session and a subagent each made one edit that added one
  bugbear problem to a file of their own; neither was told about the hook. The
  transcript of each holds exactly one record with the report for its file: an
  attachment of type `hook_blocking_error` for the event `PostToolUse`. The same probe
  for the hook as shipped by the plugin, and for an agent started by a workflow, is
  still to run.

## Removing

- **Removing a local-directory marketplace leaves its directory alone.** Seen.
- **Uninstalling leaves the cached copy behind.** Seen: after `plugin uninstall`, the
  directory under `plugins/cache` is still there. Whether a later session removes it
  was not observed.
- **The CLI keeps the mode of `settings.json`.** Seen: a file of mode 600 keeps it
  through `plugin install`, `uninstall`, `marketplace add` and `marketplace remove`.
