# Manual smoke tests

Run these per OS before cutting a release. Not part of automated CI.

## Linux (Ubuntu 24.04 or similar with systemd)

1. `curl -fsSL .../install.sh | bash`
2. `claude-hub install --no-interactive`
3. `systemctl --user status claude-hub` -> active
4. `claude mcp list | grep claude-hub-projects` -> Connected
5. `claude-hub doctor` -> all green
6. Open claude.ai/code from phone -> hostname visible
7. `claude-hub uninstall --purge`
8. Verify no systemd unit, no ~/.claude-hub, no MCP registration.

## macOS

Same steps; service mgr is launchd instead of systemd.

## Windows (no WSL)

1. `irm .../install.ps1 | iex`
2. `claude-hub install --no-interactive`
3. `Get-ScheduledTask -TaskPath \claude-hub\` -> claude-hub present
4. `claude mcp list | findstr claude-hub-projects` -> Connected
5. Open claude.ai/code -> machine visible
6. `claude-hub uninstall --purge`

## Windows + WSL

1. From PS, `claude-hub install --no-interactive --wsl Debian`
2. Both scheduled tasks present (claude-hub, claude-hub-wsl-debian)
3. MCPs connected on Windows-side (plus WSL-side if user ran install separately)
4. Phone sees both environments (hostname + WSL-Debian)
5. `claude-hub uninstall --purge`
