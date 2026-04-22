# Installation

## Linux

Requires systemd user services (most modern distros).

    curl -fsSL https://raw.githubusercontent.com/jleal52/claude-hub/main/install.sh | bash
    claude-hub install

Enable linger so services survive logout:

    loginctl enable-linger $(whoami)

## macOS

    curl -fsSL https://raw.githubusercontent.com/jleal52/claude-hub/main/install.sh | bash
    claude-hub install

## Windows (native)

Defaults to a user-level Scheduled Task (no admin required).

    irm https://raw.githubusercontent.com/jleal52/claude-hub/main/install.ps1 | iex
    claude-hub install

Use `--use-nssm` for NSSM-based service (requires admin + `winget install NSSM.NSSM`).

## Windows + WSL

    claude-hub install --wsl Debian
    claude-hub install --wsl Debian --wsl Ubuntu
