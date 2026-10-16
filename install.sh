#!/usr/bin/env bash
# Installs the plugins of clones of marketplaces for the clients of this machine. It links the
# shared rules, instructions/global.md of the clone that holds this script, for Codex and VS
# Code, and checks that the instructions of the user for Claude Code import them. Run it again
# after each commit of a clone: each of its steps can be repeated.
#
#     install.sh [clone ...]
#
# A clone is named by an absolute path or by a path from the working directory. With no
# argument, the clone is the one that holds this script. Of its own, it makes links and the
# directories that hold them, and nothing else: it moves, removes, copies and edits nothing.
# The commands of the Claude Code CLI that it runs change the configuration of Claude Code, as
# each of them says. It needs bash 4.4 or later, and python3 on PATH to read the JSON files.
#
# Before it changes anything, it reads the marketplace file, .claude-plugin/marketplace.json, of
# each clone, and looks for every refusal. For each it prints `refused <place>: <reason>` on
# standard error; it then prints nothing on standard output and exits 1. It refuses:
#
#   - a clone in which no marketplace file can be read that names one plugin or more, each by
#     a name of printable characters;
#   - shared rules that are not a file that can be read, as when this script is run through a
#     link from another directory, which it then takes for the clone that holds it;
#   - a skill whose name another plugin, of the same clone or of another, also holds: one link
#     cannot lead to both;
#   - something at the place of a link that does not lead to its target: a directory, a file, a
#     link elsewhere or a link to nothing, such as a link that an earlier run made to a skill
#     since moved, or instructions of the user's own;
#   - a skill whose name ${CODEX_HOME:-~/.codex}/skills holds, unless that directory and
#     ~/.agents/skills are one: Codex would list both.
#
# Then it prints `== <client>` before the part of each client, and `  <place>: linked` or
# `  <place>: already linked` for each link that it makes or finds. A link is found when what
# is at its place leads to its target, by any path. A place, in these lines and in the others
# below, is written from `~/` when it lies under the home directory.
#
# == Codex: each skill of each clone, a directory plugins/<plugin>/skills/<name>/ that holds a
# SKILL.md, is linked as ~/.agents/skills/<name>, where Codex reads the skills of the user; and
# ${CODEX_HOME:-~/.codex}/AGENTS.md, the instructions of the user for Codex, is linked to the
# shared rules.
#
# == Claude Code: it reads the installed plugins once, with `plugin list --json`. For each clone
# it runs `plugin marketplace add <clone>`, which registers the clone as a marketplace read from
# its directory; then, for each plugin of its marketplace file, `plugin install
# <plugin>@<marketplace>` unless the list holds that plugin for the user, and `plugin update
# <plugin>@<marketplace>`, which refreshes the copy that sessions of the desktop app read. A
# plugin that the user disabled so stays disabled: an install would enable it again. The CLI is
# $C, else $CLAUDE_CODE_EXECPATH, else `claude` on PATH; without one, these steps are skipped
# and it prints `  skipped: no Claude Code CLI; set C to its path`.
# With a CLI or without, it then reads ${CLAUDE_CONFIG_DIR:-~/.claude}/CLAUDE.md, the
# instructions of the user for Claude Code, for a line of its own that imports the shared rules:
# `@` and a path that leads to them, absolute, from `~/` or from the directory of that file,
# with `\ ` for a space. It prints `  <file>: imports the shared rules`; or, when no line does,
# `  <file>: add this line to import the shared rules:` and the line, `    @<path>`, on the next
# one. It writes no such file.
#
# == VS Code: ~/.config/Code/User/prompts/shift-left.instructions.md, in the folder of the
# user's instruction files of VS Code on Linux, is linked to the shared rules. Then it prints
# `  add these entries to "chat.pluginLocations" in the user settings:` and one entry per plugin
# of each clone, `    "<clone>/plugins/<plugin>": true,`. It writes no setting.
#
# Status 0: every part ran or said that it was skipped. Status 1: a refusal, and nothing was
# changed; or a step failed, such as a command of the CLI or the reading of its list, and the
# steps after it did not run.

set -u
shopt -s nullglob

# CDPATH would make `cd` look for a relative path elsewhere first.
here="$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)" || exit 1
rules="$here/instructions/global.md"
agents="$HOME/.agents/skills"
codex="${CODEX_HOME:-$HOME/.codex}"
config="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
prompts="$HOME/.config/Code/User/prompts/shift-left.instructions.md"
cli="${C:-${CLAUDE_CODE_EXECPATH:-claude}}"

# The name of a marketplace, then the name of each of its plugins, one per line. A file that
# names no plugin, or a name that one line cannot carry, is no marketplace here.
read_marketplace='
import json, sys
marketplace = json.load(open(sys.argv[1], encoding="utf-8"))
names = [marketplace["name"]] + [plugin["name"] for plugin in marketplace["plugins"]]
for name in names:
    if not (isinstance(name, str) and name and name.isprintable()):
        sys.exit(1)
if len(names) < 2:
    sys.exit(1)
print("\n".join(names))
'

# The id of each plugin that the list of the CLI holds for the user, one per line. A list in
# another form is an error, so that no plugin is installed again by a misreading.
read_installed='
import json, sys
for plugin in json.load(sys.stdin):
    if plugin["scope"] == "user":
        print(plugin["id"])
'

# A line of its own that imports a file: `@`, then a path in which a space is `\ `.
import='^@(([^[:space:]\]|\\ )+)[[:space:]]*$'

# A path as the output writes it: from `~/` when it lies under the home directory.
shown() {
  case "$1" in
    "$HOME"/*) printf '%s\n' "~/${1#"$HOME"/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

refused=0
refuse() {
  echo "refused $(shown "$1"): $2" >&2
  refused=1
}

# Status 0 when something is at the place, the first argument, that does not lead to the
# target, the second, by any path. A link to nothing counts.
taken() {
  ! [ "$1" -ef "$2" ] && { [ -e "$1" ] || [ -L "$1" ]; }
}

# Makes a link at the place to the target, and the directories above it, unless what is there
# leads to the target already, and says which.
link() {
  if [ "$1" -ef "$2" ]; then
    echo "  $(shown "$1"): already linked"
  else
    mkdir -p "$(dirname "$1")" && ln -s "$2" "$1" || return 1
    echo "  $(shown "$1"): linked"
  fi
}

[ "$#" -gt 0 ] || set -- "$here"
clones=()
marketplaces=()
plugins=()
for argument in "$@"; do
  # CDPATH would make `cd` look for a relative path elsewhere first.
  if ! clone="$(CDPATH='' cd -- "$argument" 2>/dev/null && pwd)" ||
    ! names="$(python3 -c "$read_marketplace" "$clone/.claude-plugin/marketplace.json" \
      2>/dev/null)"; then
    refuse "$argument" "no marketplace file that names one plugin or more can be read in it"
    continue
  fi
  clones+=("$clone")
  marketplaces+=("${names%%$'\n'*}")
  plugins+=("${names#*$'\n'}")
done

skills=()
# The names of the skills seen so far, each on a line of its own.
seen=$'\n'
for clone in "${clones[@]}"; do
  for skill in "$clone"/plugins/*/skills/*/SKILL.md; do
    directory="${skill%/SKILL.md}"
    name="${directory##*/}"
    case "$seen" in *$'\n'"$name"$'\n'*)
      refuse "$agents/$name" "two plugins hold a skill of this name; one link cannot lead to both"
      ;;
    esac
    seen="$seen$name"$'\n'
    if taken "$agents/$name" "$directory"; then
      refuse "$agents/$name" "something is there that does not lead to $(shown "$directory")"
    fi
    # When the two are one directory, what is there is what the test above accepted.
    if ! [ "$codex/skills" -ef "$agents" ] &&
      { [ -e "$codex/skills/$name" ] || [ -L "$codex/skills/$name" ]; }; then
      refuse "$codex/skills/$name" "Codex would list it beside $(shown "$agents/$name")"
    fi
    skills+=("$directory")
  done
done
if ! [ -f "$rules" ] || ! [ -r "$rules" ]; then
  refuse "$rules" "the shared rules are not a file that can be read"
fi
for place in "$codex/AGENTS.md" "$prompts"; do
  if taken "$place" "$rules"; then
    refuse "$place" "something is there that does not lead to $(shown "$rules")"
  fi
done
[ "$refused" -eq 0 ] || exit 1

echo "== Codex"
for directory in "${skills[@]}"; do
  link "$agents/${directory##*/}" "$directory" || exit 1
done
link "$codex/AGENTS.md" "$rules" || exit 1

echo "== Claude Code"
if command -v "$cli" >/dev/null; then
  listed="$("$cli" plugin list --json </dev/null)" || exit 1
  installed="$(python3 -c "$read_installed" <<<"$listed")" || exit 1
  for index in "${!clones[@]}"; do
    "$cli" plugin marketplace add "${clones[index]}" </dev/null || exit 1
    while IFS= read -r plugin; do
      id="$plugin@${marketplaces[index]}"
      case $'\n'"$installed"$'\n' in
        *$'\n'"$id"$'\n'*) ;;
        *) "$cli" plugin install "$id" </dev/null || exit 1 ;;
      esac
      "$cli" plugin update "$id" </dev/null || exit 1
    done <<<"${plugins[index]}"
  done
else
  echo "  skipped: no Claude Code CLI; set C to its path"
fi
imports=""
if [ -f "$config/CLAUDE.md" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ $import ]] || continue
    path="${BASH_REMATCH[1]//\\ / }"
    case "$path" in
      "~/"*) path="$HOME/${path#"~/"}" ;;
      /*) ;;
      *) path="$config/$path" ;;
    esac
    [ "$path" -ef "$rules" ] && imports=yes
  done <"$config/CLAUDE.md"
fi
if [ -n "$imports" ]; then
  echo "  $(shown "$config/CLAUDE.md"): imports the shared rules"
else
  echo "  $(shown "$config/CLAUDE.md"): add this line to import the shared rules:"
  line="@$(shown "$rules")"
  echo "    ${line// /\\ }"
fi

echo "== VS Code"
link "$prompts" "$rules" || exit 1
echo '  add these entries to "chat.pluginLocations" in the user settings:'
for index in "${!clones[@]}"; do
  while IFS= read -r plugin; do
    echo "    \"$(shown "${clones[index]}/plugins/$plugin")\": true,"
  done <<<"${plugins[index]}"
done
