#!/usr/bin/env bash
# The gate: the checks that a change passes before it is handed over or released.
#
#     ci/gate.sh [--no-cli] [check ...]
#
# It checks the repository that holds the working directory, from its root. With no name
# it runs every check, in the order below; with names, those only, in the order given.
# It prints `== <check>` before each check and stops at the first that fails.
#
#     tests      the test suite passes
#     lint       Ruff finds nothing, as a linter and as a formatter
#     contained  no file of a plugin reaches outside its plugin
#     dashes     no tracked file other than LICENSE holds a Unicode dash
#     private    no tracked file holds a home directory path, an email address that is
#                not allowed or a string of the denylist
#     version    .version holds a version in the one form that is accepted
#     messages   no commit that HEAD reaches and no tag reaches has a co-author trailer,
#                and none has in its message what `dashes` and `private` search for
#     manifests  the Claude Code CLI validates the marketplace and each plugin
#
# A check that searches prints one line per rule: what it searched for, then `none`, or
# then what it found, one line each. A search that ends in error fails its rule. The check
# `messages` prints `commits read: <n>`, applies each of its rules to every commit, also
# after one has failed, and names a commit by its hash. Its rules, as they are printed:
#
#     a commit with a co-author trailer
#     a commit with a Unicode dash in its message
#     a commit with a home directory path in its message
#     an email address that is not allowed in the message of a commit
#     a commit with a string of the denylist in its message
#
# The trailer is read as git reads trailers, in any letter case; it is not searched as text.
#
# The denylist is docs/work/denylist.txt of the main worktree, one string per line. It is
# not tracked, and a fresh clone has none. `private` and `messages` print
# `denylist: <n> strings searched`, or `denylist: no file found`; they print no string of it
# and not its path.
#
# The CLI is $C, else $CLAUDE_CODE_EXECPATH, else `claude` on PATH. Without one the check
# `manifests` fails. With --no-cli it is skipped, and prints `skipped, as --no-cli asks`.
# The CLI runs with HOME and CLAUDE_CONFIG_DIR in a temporary directory, which the script
# removes.
#
# Status 0: every check that ran passed. Status 1: a check failed, and the last line of
# standard output is `gate: the check <name> failed`. Status 2: an argument is no check,
# or the working directory is in no repository.

set -u

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
checks=(tests lint contained dashes private version messages manifests)

# The number of files of the plugins that link back to their skill. AGENTS.md repeats it.
back_links=16

# What the searches look for, as arguments of `grep` and of `git grep`.
# U+2013 and U+2014 as bytes: written so, this file holds neither and no locale is needed.
dashes=(-F -e $'\xe2\x80\x93' -e $'\xe2\x80\x94')
# A home directory path. The brackets keep each pattern from matching its own line.
home=(-E -e '/ho[m]e/' -e '/Use[r]s/')
# An email address. A line that holds an allowed address does not count.
email=(-E -e '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
allowed='git@github\.com|noreply@anthropic\.com|@users\.noreply\.github\.com|@example\.invalid'
# The strings of the denylist, once read_denylist has run.
denylist=()

# Runs a search and keeps what it printed in $found. Status 0: it found something. Status
# 1: it found nothing. Any other status is an error of the search, and is said.
found=""
search() {
  found="$("$@")"
  local status=$?
  [ "$status" -le 1 ] || echo "  a search ended in error, with status $status"
  return "$status"
}

# One rule: passes when the search finds nothing. Prints what was searched for, then
# `none` or what was found.
finds_nothing() {
  local what="$1"
  shift
  search "$@"
  case "$?" in
    0)
      echo "  $what:"
      printf '%s\n' "$found"
      return 1
      ;;
    1)
      echo "  $what: none"
      return 0
      ;;
    *) return 1 ;;
  esac
}

# A search of which some lines do not count: those that `grep` matches with the option and
# the pattern given first. The search itself is what follows them.
unless() {
  local option="$1" pattern="$2" lines status
  shift 2
  lines="$("$@")"
  status=$?
  [ "$status" -eq 0 ] || return "$status"
  grep -v "$option" -e "$pattern" <<<"$lines"
}

# Reads the denylist of the main worktree into $denylist, and says how many strings it
# holds or that there is no file. A file that is there and cannot be read is an error.
read_denylist() {
  local file string
  file="$(git worktree list --porcelain)" || return 1
  file="${file%%$'\n'*}"
  file="${file#worktree }/docs/work/denylist.txt"
  denylist=()
  if [ ! -e "$file" ]; then
    echo "  denylist: no file found"
    return 0
  fi
  search grep -s . "$file"
  [ "$?" -le 1 ] || return 1
  while IFS= read -r string; do
    [ -z "$string" ] || denylist+=(-e "$string")
  done <<<"$found"
  echo "  denylist: $((${#denylist[@]} / 2)) strings searched"
}

check_tests() {
  python3 -m unittest discover -s tests -t .
}

check_lint() {
  ruff --version && ruff check . && ruff format --check .
}

check_contained() {
  local files
  finds_nothing "a file of a plugin that reaches outside it" \
    unless -F '](../SKILL.md)' git grep -n -F '../' -- plugins || return 1
  search git grep -c -F '](../SKILL.md)' -- plugins
  [ "$?" -le 1 ] || return 1
  files="$(grep -c . <<<"$found")"
  echo "  files of the plugins that link back to their skill: $files, of $back_links"
  [ "$files" -eq "$back_links" ]
}

check_dashes() {
  finds_nothing "a Unicode dash in a tracked file" git grep -n "${dashes[@]}" -- . ':!LICENSE'
}

check_private() {
  local failed=0
  read_denylist || return 1
  finds_nothing "a home directory path in a tracked file" git grep -n "${home[@]}" || failed=1
  finds_nothing "an email address that is not allowed in a tracked file" \
    unless -E "$allowed" git grep -n "${email[@]}" || failed=1
  [ "${#denylist[@]}" -eq 0 ] ||
    finds_nothing "a tracked file with a string of the denylist" \
      git grep -l -F "${denylist[@]}" || failed=1
  return "$failed"
}

check_version() {
  python3 "$here/next_version.py" .version
}

check_messages() {
  local commits commit failed=0
  commits="$(git rev-list HEAD --not --tags)" || return 1
  mkdir -p "$scratch/trailers" "$scratch/messages" || return 1
  for commit in $commits; do
    git log -n 1 --format='%(trailers:key=Co-Authored-By)' "$commit" \
      >"$scratch/trailers/$commit" || return 1
    git log -n 1 --format=%B "$commit" >"$scratch/messages/$commit" || return 1
  done
  echo "  commits read: $(wc -w <<<"$commits")"
  read_denylist || return 1
  # From here on a file is named after its commit, so that a search names commits.
  cd "$scratch/trailers" || return 1
  finds_nothing "a commit with a co-author trailer" grep -r -l . || failed=1
  cd "$scratch/messages" || return 1
  finds_nothing "a commit with a Unicode dash in its message" \
    grep -r -l "${dashes[@]}" || failed=1
  finds_nothing "a commit with a home directory path in its message" \
    grep -r -l "${home[@]}" || failed=1
  finds_nothing "an email address that is not allowed in the message of a commit" \
    unless -E "$allowed" grep -r "${email[@]}" || failed=1
  [ "${#denylist[@]}" -eq 0 ] ||
    finds_nothing "a commit with a string of the denylist in its message" \
      grep -r -l -F "${denylist[@]}" || failed=1
  return "$failed"
}

check_manifests() {
  local cli directory
  if [ -n "$no_cli" ]; then
    echo "  skipped, as --no-cli asks"
    return 0
  fi
  cli="${C:-${CLAUDE_CODE_EXECPATH:-claude}}"
  if ! command -v "$cli" >/dev/null; then
    echo "  no Claude Code CLI: set C to its path, or pass --no-cli"
    return 1
  fi
  mkdir -p "$scratch/home" "$scratch/config" || return 1
  for directory in . plugins/*/; do
    [ "$directory" = . ] || [ -f "$directory.claude-plugin/plugin.json" ] || continue
    env -i HOME="$scratch/home" PATH="$PATH" CLAUDE_CONFIG_DIR="$scratch/config" \
      "$cli" plugin validate "$directory" || return 1
  done
}

no_cli=""
selected=()
for argument in "$@"; do
  if [ "$argument" = --no-cli ]; then
    no_cli=yes
  elif declare -F "check_$argument" >/dev/null; then
    selected+=("$argument")
  else
    echo "gate: $argument is no check; the checks are: ${checks[*]}" >&2
    exit 2
  fi
done
[ "${#selected[@]}" -gt 0 ] || selected=("${checks[@]}")

root="$(git rev-parse --show-toplevel)" || exit 2
cd "$root" || exit 2
scratch="$(mktemp -d)" || exit 2
trap 'rm -rf "$scratch"' EXIT

for name in "${selected[@]}"; do
  echo "== $name"
  # In a subshell, so that a check may change the working directory.
  if ! ("check_$name"); then
    echo "gate: the check $name failed"
    exit 1
  fi
done
