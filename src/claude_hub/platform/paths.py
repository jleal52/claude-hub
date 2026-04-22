"""User-scope paths for claude-hub state and config."""
from __future__ import annotations

import os
from pathlib import Path


def hub_dir() -> Path:
    """Root directory for claude-hub state, logs, config.

    Honors CLAUDE_HUB_DIR env var for tests or user override.
    Defaults to ~/.claude-hub (cross-platform: resolves to
    C:\\Users\\<user>\\.claude-hub on Windows).
    """
    override = os.environ.get("CLAUDE_HUB_DIR")
    if override:
        return Path(override)
    return Path.home() / ".claude-hub"


def logs_dir() -> Path:
    return hub_dir() / "logs"


def state_dir() -> Path:
    return hub_dir() / "state"


def config_path() -> Path:
    return hub_dir() / "config.toml"


def ensure_dirs() -> None:
    """Create hub_dir, logs_dir, state_dir if missing."""
    hub_dir().mkdir(parents=True, exist_ok=True)
    logs_dir().mkdir(parents=True, exist_ok=True)
    state_dir().mkdir(parents=True, exist_ok=True)
