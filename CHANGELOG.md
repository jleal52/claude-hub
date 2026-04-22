# Changelog

All notable changes to this project will be documented in this file.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning: [SemVer](https://semver.org/).

## [Unreleased]

## [0.1.8] -- 2026-04-22

### Added
- `claude-hub install --wsl <distro>` now also installs the `claude-code-hub` package inside the distro (via pipx, bootstrapping it with `pip install --user` if missing) and registers the MCP there. Before this, the Windows-side install only registered the MCP on the host, so the `WSL-<distro>` environment in claude.ai/code didn't expose `claude-hub-projects` tools. Prints `[OK] registered MCP inside <distro>` on success, or `[WARN]` with the manual fallback command if anything fails (keeping the overall install non-blocking).

## [0.1.7] -- 2026-04-22

### Fixed
- Windows Scheduled Task action launched the claude binary directly, without stdin attached. `claude remote-control` interpreted the closed stdin as `--print` mode and exited immediately, so tasks showed `Ready` (not `Running`) right after `/Run`. The backend now generates a small `.cmd` shim per service under `~/.claude-hub/`, with `< NUL` for stdin and stdout/stderr redirected to `logs/<name>.{out,err}.log`. The XML action points at the shim. This makes task logs visible and the service actually stays alive.

### Added
- `list_logs(name)` in the Scheduled Task backend now returns the out/err log paths when present.

## [0.1.6] -- 2026-04-22

### Fixed
- WSL task exited with code 127 (`command not found`) because `wsl.exe -d <distro> -- <cmd>` does NOT source `~/.profile`, so `claude` from `~/.local/bin` wasn't on PATH. The wsl_wrapper now wraps the inner command with `bash -lc "<cmd> < /dev/null"`, which sources the login shell PATH and redirects stdin from /dev/null so `claude remote-control` doesn't switch to `--print` mode under Task Scheduler.

## [0.1.5] -- 2026-04-22

### Fixed
- Windows 11 22H2+ rejects `schtasks /Create /SC ONLOGON` with `Acceso denegado` / `Access denied` unless the shell is elevated, because without explicit LogonType the task defaults to Password authentication (requires the user's credentials). The ScheduledTask backend now submits an XML template with `LogonType=InteractiveToken` and `RunLevel=LeastPrivilege`, which Windows accepts from a non-elevated shell. Keeps the "no admin required" installer promise.

## [0.1.4] -- 2026-04-22

### Fixed
- Windows: `schtasks /Create` failed with `Error: Acceso denegado / Access denied` when registering tasks under a custom `\claude-hub\` folder on Windows 11 installs with stricter Task Scheduler ACLs. Tasks are now registered at the root of the Task Scheduler tree (`\claude-hub`, `\claude-hub-wsl-debian`), which works without elevated privileges. The service names are already unique so the flat layout is not a concern.

## [0.1.3] -- 2026-04-22

### Fixed
- Windows backends (Scheduled Task, NSSM) silently ignored `schtasks` / `nssm` failures, causing the installer to print `[OK] installed service ...` even when nothing was registered. They now raise `RuntimeError` with the stderr output, and the CLI prints `[FAIL]` with the underlying error. Includes regression tests.

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
