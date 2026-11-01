# agent-plugins

A marketplace of agent plugins and skills. Each entry lives in `plugins/<name>/` with its own `.claude-plugin/plugin.json`, version and checks; a standalone skill is packaged as a small plugin with one `skills/<name>/SKILL.md`, so everything installs and versions the same way.

## Install

```sh
/plugin marketplace add <path-or-git-url-of-this-repo>
/plugin install backend-architecture@agent-plugins
```

For local development load a working copy directly, for example `claude --plugin-dir ./plugins/backend-architecture`.

## Plugins

| Plugin | Version | What it does |
| --- | --- | --- |
| [backend-architecture](plugins/backend-architecture/README.md) | 0.5.0 | Backend audit, design and single-area rule lookup: 13 technical areas with opt-in domain review (`--domain on`), a mandatory coverage inventory, calibrated severities and a validated JSON report. |

## Conventions

- Plugins stay project-agnostic. Project-specific hints (where a project's specs or code index live) belong in that project's own `CLAUDE.md` or `.claude/`, not here.
- A change to a report or data contract is a breaking change: bump the plugin's minor version and note it in its README.
- Every plugin keeps deterministic checks runnable with its own instructions; behavioural eval results (traces, reports, token logs) are kept outside the repository (`eval-runs/` is ignored).

## Checks

```sh
cd plugins/backend-architecture
python3 -B scripts/validate_repository.py
python3 -B -m unittest discover -s scripts -p 'test_*.py'
```
