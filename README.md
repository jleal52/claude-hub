# claude-hub

Expose your machine(s) to [claude.ai/code](https://claude.ai/code) as remote-control environments you can chat with from anywhere (phone, another laptop). Bundled with `claude-hub-projects`, an MCP server that gives any Claude Code session the ability to list your projects, search past conversations, and spin up new remote-control sessions on demand.

[![CI](https://github.com/jleal52/claude-hub/actions/workflows/ci.yml/badge.svg)](https://github.com/jleal52/claude-hub/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/claude-code-hub.svg)](https://pypi.org/project/claude-code-hub/)
[![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](LICENSE)

> **Status:** alpha. Core functionality works on Linux, macOS, Windows, and Windows+WSL; APIs and CLI flags may still shift before 1.0.

## Why

Once `claude remote-control` is running on your machine, it shows up in `claude.ai/code` and you can talk to it from any device logged into the same Claude account. `claude-hub` wraps that into a proper service that starts at boot/login, with a single cross-platform installer.

The MCP adds a second layer: when you're already in a Claude session (local or remote), you can ask things like *"what projects do I have?"*, *"search my past conversations for stripe webhook"*, or *"open a new session in /home/me/work/foo"* — and the agent delegates to the MCP tools instead of walking you through the filesystem.

## What you get

- **`claude-hub` service** — runs `claude remote-control` in the background as a user-scope service. Your machine appears in `claude.ai/code` as `<hostname>` (configurable).
- **`claude-hub-projects` MCP** — 5 tools registered at user scope via `claude mcp add`:
  - `list_projects` — projects with conversation history
  - `search_conversations` — grep across past session `.jsonl` files
  - `spawn_session` — start a new remote-control session in any folder; returns the `claude.ai/code?environment=env_…` URL
  - `list_running_sessions` — sessions you spawned dynamically
  - `stop_session`
- **Cross-platform**: Linux (systemd user), macOS (launchd), Windows (Scheduled Task default, NSSM opt-in).
- **WSL support**: on Windows, register distros as parallel environments alongside the host.

## Requirements

- Python 3.11+
- [Claude Code CLI](https://claude.com/claude-code) installed and logged in with a Claude account that has a subscription.

## Install

### Linux / macOS

```sh
curl -fsSL https://raw.githubusercontent.com/jleal52/claude-hub/main/install.sh | bash
claude-hub install
```

### Windows

```powershell
irm https://raw.githubusercontent.com/jleal52/claude-hub/main/install.ps1 | iex
claude-hub install
```

### Direct, if you already have pipx

```sh
pipx install claude-code-hub
claude-hub install
```

Both installers bootstrap pipx if missing, install the package, and leave you at a prompt to run the interactive setup wizard.

### WSL parallel environments

From Windows, register one or more WSL distros in the same install:

```powershell
claude-hub install --wsl Debian --wsl Ubuntu
```

The host and each distro appear as separate environments in `claude.ai/code` (e.g. `my-laptop`, `WSL-Debian`, `WSL-Ubuntu`).

## Usage

```
claude-hub install            # interactive wizard (default)
claude-hub install --no-interactive --session-name my-laptop
claude-hub status             # services + MCP registration
claude-hub logs [service]
claude-hub doctor             # diagnose health
claude-hub uninstall [--purge]
```

## Naming

Three distinct names (all related but each with a reason):

| What | Name | Why |
|------|------|-----|
| PyPI distribution | `claude-code-hub` | `claude-hub` was already taken on PyPI |
| Python import | `claude_hub` | snake_case convention, short |
| CLI command | `claude-hub` | registered via `[project.scripts]` in `pyproject.toml` |

So: `pipx install claude-code-hub` → run `claude-hub install`.

## Documentation

- [Installation by OS](docs/install.md)
- [Architecture](docs/architecture.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Manual smoke tests](docs/smoke-tests.md)

## Contributing

Issues and PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[AGPL-3.0-or-later](LICENSE). If you run a modified version as a network service, you must offer the source to your users.
