# Troubleshooting

## `claude` not found

Ensure Claude Code is installed and on PATH:

    which claude           # Linux/macOS
    where claude           # Windows

## Services not starting at boot (Linux)

    loginctl enable-linger $(whoami)

## macOS: service restarts but doesn't connect

- Check `~/.claude-hub/logs/hub.out.log` for errors.
- Run `claude` manually in your home directory once to accept the workspace trust dialog.

## Windows: `claude.ai/code` doesn't show the environment

- Confirm service is running: `Get-ScheduledTask claude-hub\claude-hub` or `Get-Service claude-hub` (NSSM).
- Verify logs in `%USERPROFILE%\.claude-hub\logs\`.

## WSL: `spawn_session` fails with `Workspace not trusted`

Inside the distro, run `cd <path>` then `claude`, and accept the trust dialog. Retry.

## NSSM stuck in SERVICE_MARKED_FOR_DELETE

From elevated PS:

    sc.exe stop <name>
    sc.exe delete <name>
