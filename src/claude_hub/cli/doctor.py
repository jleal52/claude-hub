"""doctor subcommand - diagnostic checks."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from ..config import load as load_config
from ..platform import detect


def _check(name: str, ok: bool, detail: str = "") -> None:
    from ._colors import green, red
    mark = green("[OK]") if ok else red("[FAIL]")
    print(f"  {mark} {name}{': ' + detail if detail else ''}")


def run(args: argparse.Namespace) -> int:
    print(f"claude-hub doctor - OS: {detect.current_os()}")

    _check("Python 3.11+", sys.version_info >= (3, 11),
           detail=f"{sys.version_info.major}.{sys.version_info.minor}")

    claude = detect.find_claude_binary()
    _check("claude binary on PATH", claude is not None, detail=claude or "NOT FOUND")

    cfg = load_config()
    _check("config.toml present", cfg is not None)

    if claude:
        out = subprocess.run([claude, "mcp", "list"], capture_output=True, text=True, check=False)
        _check("MCP claude-hub-projects registered", "claude-hub-projects" in out.stdout)

    if detect.current_os() == "windows":
        distros = detect.list_wsl_distros()
        _check("WSL distros detected", len(distros) > 0, detail=", ".join(distros))

    # Service status
    if cfg:
        from ..service import factory
        mgr = factory.get_service_manager(prefer=cfg.service.backend)
        status = mgr.status("claude-hub")
        _check("hub service running", status.running)
        for w in cfg.wsl:
            st = mgr.status(f"claude-hub-wsl-{w.distro.lower()}")
            _check(f"WSL {w.distro} service running", st.running)

    # Auth token (shallow check)
    from pathlib import Path
    cred_path = Path.home() / ".claude" / "credentials.json"
    _check("claude OAuth credentials file exists", cred_path.exists())

    return 0
