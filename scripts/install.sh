#!/usr/bin/env bash
# Install the plugins of this marketplace globally (user scope) for Claude Code and Codex.
#
#   scripts/install.sh [--claude] [--codex] [--local [PATH]] [--ref REF] [--plugin NAME]... [--dry-run]
#
# With neither --claude nor --codex both runtimes are installed, and a runtime whose CLI is
# missing is skipped with a warning; a runtime named explicitly is required. The source is the
# GitHub repository by default; --local installs from a checkout (this one when PATH is omitted).
# Running it again changes nothing. A marketplace already added under the same name from another
# source is removed and added again from the requested one.
set -euo pipefail

MARKETPLACE=agent-plugins
GITHUB_REPO=tohachan/agent-plugins
REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

want_claude=0 want_codex=0 local_path='' ref='' dry_run=0 plugins=()
usage() { sed -n '2,10p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
while [ $# -gt 0 ]; do
  case "$1" in
    --claude) want_claude=1 ;;
    --codex) want_codex=1 ;;
    --local)
      if [ $# -gt 1 ] && [ "${2#--}" = "$2" ]; then local_path=$2; shift; else local_path=$REPO_ROOT; fi ;;
    --ref) ref=${2:?--ref needs a value}; shift ;;
    --plugin) plugins+=("${2:?--plugin needs a value}"); shift ;;
    --dry-run) dry_run=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install.sh: unknown argument $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
explicit=$((want_claude + want_codex))
[ "$explicit" -eq 0 ] && want_claude=1 want_codex=1

if [ -n "$local_path" ]; then
  [ -d "$local_path" ] || { echo "install.sh: $local_path is not a directory" >&2; exit 2; }
  local_path=$(cd "$local_path" && pwd -P)
  [ -z "$ref" ] || { echo "install.sh: --ref applies to the GitHub source, not --local" >&2; exit 2; }
fi
manifest_root=${local_path:-$REPO_ROOT}
if [ ${#plugins[@]} -eq 0 ]; then
  # Every plugin both marketplaces list; read from the checkout the script runs from or installs.
  while IFS= read -r p; do plugins+=("$p"); done < <(python3 - "$manifest_root" <<'PY'
import json, sys, pathlib
root = pathlib.Path(sys.argv[1])
names = [[p['name'] for p in json.loads((root / f).read_text())['plugins']]
         for f in ('.claude-plugin/marketplace.json', '.agents/plugins/marketplace.json')]
print('\n'.join(n for n in names[0] if n in names[1]))
PY
)
fi
[ ${#plugins[@]} -gt 0 ] || { echo "install.sh: no plugins found in $manifest_root" >&2; exit 1; }

run() {
  printf '+'; printf ' %q' "$@"; printf '\n'
  [ "$dry_run" -eq 1 ] || "$@"
}

# Print the source a marketplace of this name is registered from, normalised to a local path or
# owner/repo; empty when it is not registered. $1 is claude|codex, stdin the CLI's JSON listing.
registered_source() {
  python3 -c '
import json, os, re, sys
runtime, name = sys.argv[1], sys.argv[2]
try: data = json.load(sys.stdin)
except ValueError: sys.exit(0)
items = data if runtime == "claude" else data.get("marketplaces", [])
for m in items:
    if m.get("name") != name: continue
    if runtime == "claude":
        kind, value = m.get("source"), m.get("path") or m.get("repo") or m.get("url") or ""
    else:
        src = m.get("marketplaceSource") or {}
        kind, value = src.get("sourceType"), src.get("source", "")
    if kind in ("directory", "local", "file"): print("path:" + os.path.realpath(value))
    else:
        g = re.search(r"github\.com[:/]([^/]+/[^/.]+)", value)
        print("repo:" + (g.group(1) if g else value).lower())
' "$1" "$MARKETPLACE"
}

if [ -n "$local_path" ]; then want_source="path:$local_path"; source_arg=$local_path
else want_source="repo:$(printf %s "$GITHUB_REPO" | tr '[:upper:]' '[:lower:]')"; source_arg=$GITHUB_REPO
fi

install_runtime() { # $1 claude|codex
  local rt=$1 have
  if ! command -v "$rt" >/dev/null 2>&1; then
    if [ "$explicit" -gt 0 ]; then echo "install.sh: $rt CLI not found" >&2; return 1; fi
    echo "== $rt: CLI not found, skipped"; return 0
  fi
  echo "== $rt"
  have=$("$rt" plugin marketplace list --json 2>/dev/null | registered_source "$rt" || true)
  if [ -n "$have" ] && [ "$have" != "$want_source" ]; then
    echo "marketplace $MARKETPLACE is registered from ${have#*:}; switching to ${want_source#*:}"
    run "$rt" plugin marketplace remove "$MARKETPLACE"
    have=''
  fi
  if [ -z "$have" ]; then
    if [ -n "$ref" ]; then
      if [ "$rt" = codex ]; then run codex plugin marketplace add "$source_arg" --ref "$ref"
      else run claude plugin marketplace add "$source_arg#$ref"; fi
    else
      run "$rt" plugin marketplace add "$source_arg"
    fi
  elif [ -z "$local_path" ]; then
    # A Git source is a snapshot; refresh it so an install picks up the current version.
    if [ "$rt" = codex ]; then run codex plugin marketplace upgrade "$MARKETPLACE"
    else run claude plugin marketplace update "$MARKETPLACE"; fi
  else
    echo "marketplace $MARKETPLACE already registered from ${have#*:}"
  fi
  local p
  for p in "${plugins[@]}"; do
    if [ "$rt" = codex ]; then run codex plugin add "$p@$MARKETPLACE"
    else run claude plugin install "$p@$MARKETPLACE" --scope user; fi
  done
}

status=0
[ "$want_claude" -eq 0 ] || install_runtime claude || status=1
[ "$want_codex" -eq 0 ] || install_runtime codex || status=1
if [ "$status" -eq 0 ] && [ "$dry_run" -eq 0 ]; then
  echo "Done. Start a new Claude Code or Codex session (or /reload-plugins in Claude Code) to load the skills."
fi
exit "$status"
