# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.2] -- 2026-04-22

### Fixed
- MCP registration failed with `error: unknown option '-m'`. The `claude mcp add` command interprets the first `-`-prefixed token after the server name as one of its own options; we now pass `--` to separate the command path from its arguments. `_register_mcp` also returns a boolean so the installer prints `[FAIL]` instead of a misleading `[OK]` when the registration fails. Added regression tests.

## [0.1.1] -- 2026-04-22

### Fixed
- Windows: `claude-hub status` (and any command loading config) crashed with `tomllib.TOMLDecodeError: Invalid hex value` when the saved `config.toml` contained Windows paths like `C:\Users\...`. Config serializer now uses TOML literal strings (single quotes) so backslashes are preserved verbatim. Added a regression test covering Windows paths round-trip.

## [0.1.0] -- 2026-04-22

Initial release.

### Added
- `claude-hub` CLI with `install`, `uninstall`, `status`, `logs`, `doctor` subcommands.
- Service manager backends: Linux (systemd user), macOS (launchd), Windows (Scheduled Task, NSSM).
- WSL distro wrapping via `wsl.exe` composition.
- MCP server `claude-hub-projects` with 5 tools: `list_projects`, `spawn_session`, `list_running_sessions`, `stop_session`, `search_conversations`.
- Bootstrap scripts `install.sh` / `install.ps1`.
- GitHub Actions CI matrix (ubuntu/macos/windows x python 3.11/3.12/3.13).
- AGPL-3.0 license.

### Note on naming

The PyPI distribution is `claude-code-hub` (since `claude-hub` was taken). The Python import path (`claude_hub`) and CLI command (`claude-hub`) are unchanged. So:

    pipx install claude-code-hub
    claude-hub install
