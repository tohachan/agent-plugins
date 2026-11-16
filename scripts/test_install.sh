#!/usr/bin/env bash
# Exercise scripts/install.sh against throwaway Claude Code and Codex homes (CLAUDE_CONFIG_DIR,
# CODEX_HOME); the real ~/.claude and ~/.codex are never touched. Needs the claude and codex CLIs;
# a missing one is reported and its cases are skipped. Local sources only, so no network.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
INSTALL=$ROOT/scripts/install.sh
WORK=$(cd "$(mktemp -d "${TMPDIR:-/tmp}/agent-plugins-install-test.XXXXXX")" && pwd -P)
trap 'rm -rf "$WORK"' EXIT
export CLAUDE_CONFIG_DIR=$WORK/claude CODEX_HOME=$WORK/codex
mkdir -p "$CLAUDE_CONFIG_DIR" "$CODEX_HOME"

fails=0
ok() { echo "ok   - $1"; }
bad() { echo "FAIL - $1"; fails=$((fails + 1)); }
check() { if eval "$2"; then ok "$1"; else bad "$1"; fi; }

runtimes=()
for rt in claude codex; do
  if command -v "$rt" >/dev/null 2>&1; then runtimes+=("$rt"); else echo "skip - $rt CLI not found"; fi
done
[ ${#runtimes[@]} -gt 0 ] || { echo "no runtime CLI found; nothing tested"; exit 0; }
flags=(); for rt in "${runtimes[@]}"; do flags+=("--$rt"); done

snapshot() { # the user-level files an install writes
  { cat "$CLAUDE_CONFIG_DIR/settings.json" 2>/dev/null; echo '--'; cat "$CODEX_HOME/config.toml" 2>/dev/null; } | shasum
}

# 1. Dry run prints the intended commands and writes nothing. The '+ <command>' lines are the
#    dry run's product (what a real run would execute), so asserting on them runs the artifact.
out=$("$INSTALL" "${flags[@]}" --local "$ROOT" --dry-run)
for rt in "${runtimes[@]}"; do
  check "dry run prints $rt marketplace add" "grep -q '^+ $rt plugin marketplace add $ROOT\$' <<<\"\$out\"" # test-value: ok dry run names the marketplace add a real run executes
done
check "dry run prints claude install" "[[ ! \" ${runtimes[*]} \" =~ ' claude ' ]] || grep -q '^+ claude plugin install backend-architecture@agent-plugins --scope user' <<<\"\$out\""
check "dry run prints codex add" "[[ ! \" ${runtimes[*]} \" =~ ' codex ' ]] || grep -q '^+ codex plugin add backend-architecture@agent-plugins' <<<\"\$out\""
check "dry run writes no config" "[ ! -e \"$CLAUDE_CONFIG_DIR/settings.json\" ] && [ ! -e \"$CODEX_HOME/config.toml\" ]"

# 2. A real run installs and enables the plugin in each runtime.
"$INSTALL" "${flags[@]}" --local "$ROOT" >"$WORK/run1.log" 2>&1 || { cat "$WORK/run1.log"; bad "first install exits 0"; }
for rt in "${runtimes[@]}"; do
  if [ "$rt" = claude ]; then
    check "claude lists the plugin enabled" "claude plugin list 2>/dev/null | grep -A4 'backend-architecture@agent-plugins' | grep -q enabled"
  else
    check "codex lists the plugin enabled" "codex plugin list --json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); sys.exit(0 if any(p[\"pluginId\"]==\"backend-architecture@agent-plugins\" and p[\"enabled\"] for p in d[\"installed\"]) else 1)'"
    check "codex cache carries the whole plugin" "for d in skills shared knowledge scripts agents; do [ -d \"\$(ls -d $CODEX_HOME/plugins/cache/agent-plugins/backend-architecture/*/ | head -1)\$d\" ] || exit 1; done"
  fi
done

# 3. A second run changes nothing.
before=$(snapshot)
"$INSTALL" "${flags[@]}" --local "$ROOT" >"$WORK/run2.log" 2>&1 || { cat "$WORK/run2.log"; bad "second install exits 0"; }
check "second run leaves the configs byte-identical" "[ \"$before\" = \"\$(snapshot)\" ]"
check "second run adds no marketplace" "! grep -q '^+ .* plugin marketplace add' \"$WORK/run2.log\"" # test-value: ok the command trace shows a re-run registers nothing twice

# 4. A marketplace registered from another source is switched to the requested one.
OTHER=$WORK/other-checkout
mkdir -p "$OTHER"
cp -R "$ROOT/.claude-plugin" "$ROOT/.agents" "$ROOT/plugins" "$OTHER/"
"$INSTALL" "${flags[@]}" --local "$OTHER" >"$WORK/run3.log" 2>&1 || { cat "$WORK/run3.log"; bad "switching install exits 0"; }
for rt in "${runtimes[@]}"; do
  check "$rt marketplace now points at the other checkout" "$rt plugin marketplace list --json 2>/dev/null | grep -q '$OTHER'"
done

# 4b. Without --local the source is the GitHub repository, and --ref reaches each CLI in its own
#     syntax (dry run only: no network).
out=$("$INSTALL" "${flags[@]}" --ref main --dry-run)
for rt in "${runtimes[@]}"; do
  if [ "$rt" = claude ]; then want='^+ claude plugin marketplace add tohachan/agent-plugins\#main$'
  else want='^+ codex plugin marketplace add tohachan/agent-plugins --ref main$'; fi
  check "$rt gets the GitHub source pinned to the ref" "grep -q '$want' <<<\"\$out\"" # test-value: ok the command a real run executes, per CLI syntax
done

# 5. A runtime named explicitly whose CLI is missing fails; an implicit one is skipped.
NOBIN=$WORK/nobin; mkdir -p "$NOBIN"; ln -s "$(command -v python3)" "$NOBIN/python3"
for t in bash dirname sed tr cat pwd; do ln -s "$(command -v $t)" "$NOBIN/$t"; done
check "explicit --codex without the CLI fails" "! PATH=$NOBIN \"$NOBIN/bash\" \"$INSTALL\" --codex --local \"$ROOT\" --dry-run >/dev/null 2>&1"
check "implicit runtimes without CLIs are skipped, exit 0, nothing run" "out=\$(PATH=$NOBIN \"$NOBIN/bash\" \"$INSTALL\" --local \"$ROOT\" --dry-run 2>&1) && ! grep -q '^+ ' <<<\"\$out\""

# 6. Bad arguments are refused.
check "unknown flag exits 2" "\"$INSTALL\" --bogus >/dev/null 2>&1; [ \$? -eq 2 ]"
check "--ref with --local exits 2" "\"$INSTALL\" --local \"$ROOT\" --ref main >/dev/null 2>&1; [ \$? -eq 2 ]"

[ "$fails" -eq 0 ] && echo "install tests passed" || { echo "$fails install test(s) failed"; exit 1; }
