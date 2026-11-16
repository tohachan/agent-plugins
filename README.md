# agent-plugins

A marketplace of agent plugins and skills for Claude Code and Codex. Each entry lives in `plugins/<name>/` with its own `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`, version and checks; a standalone skill is packaged as a small plugin with one `skills/<name>/SKILL.md`, so everything installs and versions the same way. The marketplace is declared once per runtime: `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json`.

## Install

Globally (user scope) for both Claude Code and Codex, from GitHub:

```sh
git clone https://github.com/tohachan/agent-plugins && agent-plugins/scripts/install.sh
```

`scripts/install.sh` registers the `agent-plugins` marketplace and installs every plugin in it with each runtime's own CLI (`claude plugin …`, `codex plugin …`). Flags: `--claude` or `--codex` for one runtime only (with neither, a runtime whose CLI is missing is skipped), `--local [PATH]` to install from a checkout instead of GitHub (this one when `PATH` is omitted), `--ref REF` to pin the GitHub source, `--plugin NAME` for one plugin, `--dry-run` to print the commands. Running it again changes nothing; run it again after `git pull` to update. A marketplace of the same name registered from another source is switched to the requested one.

By hand, the same thing is:

```sh
claude plugin marketplace add tohachan/agent-plugins
claude plugin install backend-architecture@agent-plugins --scope user
codex plugin marketplace add tohachan/agent-plugins
codex plugin add backend-architecture@agent-plugins
```

A `--local` install loads in place in Claude Code (edits take effect at the next session or `/reload-plugins`), while Codex copies the plugin into its cache, so re-run the script after changing a local checkout. For local development without installing, `claude --plugin-dir ./plugins/backend-architecture`.

`npx skills add` is not supported: it copies only `skills/*/`, while the skills read the plugin's `shared/`, `knowledge/` and `scripts/` and dispatch its `agents/`, so a skills-only copy breaks their references.

## Plugins

| Plugin | Version | What it does |
| --- | --- | --- |
| [backend-architecture](plugins/backend-architecture/README.md) | 0.6.0 | Backend audit (triage by default, `--full` for the scored protocol), design with an assumptions registry and single-area rule lookup: 13 technical areas with opt-in domain review (`--domain on`), calibrated severities and a validated JSON report. |

## Conventions

- Plugins stay project-agnostic. Project-specific hints (where a project's specs or code index live) belong in that project's own `CLAUDE.md` or `.claude/`, not here.
- A change to a report or data contract is a breaking change: bump the plugin's minor version and note it in the plugin's CHANGELOG.
- Every plugin keeps deterministic checks runnable with its own instructions; behavioural eval results (traces, reports, token logs) are kept outside the repository (`eval-runs/` is ignored).

## Checks

```sh
cd plugins/backend-architecture
python3 -B scripts/validate_repository.py
python3 -B -m unittest discover -s scripts -p 'test_*.py'
cd ../..
scripts/test_install.sh   # install.sh against throwaway CLAUDE_CONFIG_DIR / CODEX_HOME
```
