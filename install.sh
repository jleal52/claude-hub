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
    "$PYTHON" -m pip install --user pipx
    "$PYTHON" -m pipx ensurepath
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
