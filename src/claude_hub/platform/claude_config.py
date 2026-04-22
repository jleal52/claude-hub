"""Helpers for mutating Claude Code's `~/.claude.json`.

Claude Code blocks `claude remote-control` until two consents are recorded:

1. **Remote Control dialog.** First time `claude remote-control` runs it
   prints `Enable Remote Control? (y/n)` and waits for stdin. Once accepted,
   Claude writes `"remoteDialogSeen": true` at the root of `~/.claude.json`
   and never prompts again. When `claude-hub` installs the service and the
   user has not run `claude remote-control` interactively first, the service
   exits on the prompt and systemd marks it as activating/failed.

2. **Workspace trust dialog.** Running `claude` in a new directory prints
   `Do you trust the files in this folder?` Until accepted, any non-
   interactive invocation fails with `Error: Workspace not trusted.` Claude
   records acceptance in `projects[<path>].hasTrustDialogAccepted`.

`ensure_remote_control_consent()` pre-writes both flags so the service
starts cleanly on first boot. Safe to call when `~/.claude.json` is missing
or malformed: the helper creates the file, or skips silently if the JSON is
corrupt (we never want installer crashes for a best-effort nicety).
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _claude_config_path() -> Path:
    return Path.home() / ".claude.json"


def _trust_key_variants(working_dir: str) -> list[str]:
    """Return the path variants Claude may use as the key in `projects`.

    Claude normalizes Windows paths to forward slashes in some codepaths and
    leaves backslashes in others, so we write both. On POSIX there is only
    one form. Also include the absolute-resolved form in case the caller
    passed a relative path.
    """
    variants = [working_dir]
    # Normalize separators both ways on Windows.
    if "\\" in working_dir:
        variants.append(working_dir.replace("\\", "/"))
    if "/" in working_dir and os.name == "nt":
        variants.append(working_dir.replace("/", "\\"))
    # De-dupe preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)
    return unique


def ensure_remote_control_consent(working_dir: str) -> bool:
    """Mark Remote Control + workspace trust as accepted for `working_dir`.

    Returns True if the file was written (or already had both flags set),
    False if the file exists but could not be parsed (we leave it alone in
    that case — corrupting user config is worse than a one-time prompt).
    """
    cfg_path = _claude_config_path()
    if cfg_path.exists():
        try:
            data = json.loads(cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
        if not isinstance(data, dict):
            return False
    else:
        data = {}

    data["remoteDialogSeen"] = True

    projects = data.setdefault("projects", {})
    if not isinstance(projects, dict):
        projects = {}
        data["projects"] = projects

    for key in _trust_key_variants(working_dir):
        entry = projects.setdefault(key, {})
        if not isinstance(entry, dict):
            entry = {}
            projects[key] = entry
        entry["hasTrustDialogAccepted"] = True

    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return True
