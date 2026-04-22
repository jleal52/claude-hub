#!/usr/bin/env bash
# claude-hub bootstrap installer (Linux/macOS).
# Verifies Python 3.11+, installs pipx, installs claude-hub, runs `claude-hub install`.
set -euo pipefail

PYTHON="${PYTHON:-python3}"
REQUIRED="3.11"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERROR: $PYTHON not found. Install Python $REQUIRED+ first." >&2
    exit 1
fi

version=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$(printf '%s\n' "$REQUIRED" "$version" | sort -V | head -n1)" != "$REQUIRED" ]; then
    echo "ERROR: Python $REQUIRED+ required, found $version." >&2
    exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
    echo "Installing pipx..."
    # Debian 12+/Ubuntu 23.04+ enforce PEP 668 and refuse `pip install --user`
    # into the system interpreter. Try the distro package first (pipx is in
    # apt/dnf/pacman), then fall back to `pip install --user` for systems
    # without a packaged pipx. Last resort: --break-system-packages (safe
    # because we're only adding pipx to the user site-packages).
    if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
        apt-get update -qq && apt-get install -y pipx
    elif command -v apt-get >/dev/null 2>&1 && command -v sudo >/dev/null 2>&1; then
        sudo apt-get update -qq && sudo apt-get install -y pipx
    elif command -v brew >/dev/null 2>&1; then
        brew install pipx
    elif "$PYTHON" -m pip install --user pipx >/dev/null 2>&1; then
        :
    else
        echo "  pip refused (PEP 668); retrying with --break-system-packages..."
        "$PYTHON" -m pip install --user --break-system-packages pipx
    fi
    "$PYTHON" -m pipx ensurepath >/dev/null 2>&1 || true
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "Installing claude-hub from PyPI..."
if ! pipx install --force claude-code-hub 2>&1 | tee /tmp/claude-hub-pipx.log; then
    :
fi
if grep -q "No matching distribution" /tmp/claude-hub-pipx.log 2>/dev/null; then
    echo ""
    echo "PyPI install failed; falling back to latest main from GitHub..."
    pipx install --force "git+https://github.com/jleal52/claude-hub.git"
fi
rm -f /tmp/claude-hub-pipx.log

echo ""
echo "claude-hub installed. Open a new shell (or run 'source ~/.bashrc'), then:"
echo "    claude-hub install"
