# Architecture

claude-hub has two independent capabilities:

## 1. Hub service

Long-running service on the host OS that invokes `claude remote-control`. That subcommand registers the machine with `claude.ai/code`.

Service managers per OS:

| OS | Default | Alternative |
|----|---------|-------------|
| Linux | systemd user service | -- |
| macOS | launchd user agent | -- |
| Windows | Scheduled Task (at logon) | NSSM (`--use-nssm`, requires admin) |

For Windows + WSL, the service wraps `wsl.exe -d <distro> -- claude remote-control ...`. This lets the distro register as a parallel environment.

## 2. MCP claude-hub-projects

stdio MCP server spawned per-Claude-session. Exposes 5 tools backed by:
- Python 3.11+ venv (managed by pipx)
- `~/.claude/projects/` for project discovery and conversation search
- `subprocess.Popen` (detached) for spawning new `claude remote-control` sessions

Platform-aware in `spawner.py`: Linux uses setsid + SIGTERM/SIGKILL, Windows uses CREATE_NEW_PROCESS_GROUP + `taskkill /T /F`.
