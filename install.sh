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

echo "Installing claude-hub..."
pipx install --force claude-code-hub

echo ""
echo "claude-hub installed. Run 'claude-hub install' to configure."
