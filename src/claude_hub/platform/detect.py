"""OS / distro / claude binary detection."""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys
from typing import Literal, Optional

OSName = Literal["linux", "macos", "windows", "unknown"]


def current_os() -> OSName:
    if sys.platform == "linux":
        return "linux"
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    return "unknown"


def find_claude_binary() -> Optional[str]:
    """Return the absolute path to `claude` / `claude.exe`, or None."""
    return shutil.which("claude")


def default_session_name() -> str:
    """The session name shown in claude.ai/code when the user doesn't pick one."""
    host = socket.gethostname()
    return host or "my-machine"


def list_wsl_distros() -> list[str]:
    """On Windows, return installed WSL distros. Elsewhere, []."""
    if current_os() != "windows":
        return []
    try:
        out = subprocess.run(
            ["wsl.exe", "-l", "-q"],
            capture_output=True,
            check=False,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    try:
        text = out.stdout.decode("utf-16-le")
    except UnicodeDecodeError:
        text = out.stdout.decode("utf-8", errors="replace")
    distros = [line.strip().strip("\x00") for line in text.splitlines()]
    return [d for d in distros if d]
