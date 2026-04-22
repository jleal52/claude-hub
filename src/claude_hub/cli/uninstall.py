"""uninstall subcommand."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

from ..config import load as load_config
from ..platform import paths
from ..service import factory

SERVICE_NAME_HUB = "claude-hub"
MCP_SERVER_NAME = "claude-hub-projects"


def run(args: argparse.Namespace) -> int:
    cfg = load_config()
    backend_pref = cfg.service.backend if cfg else "auto"
    manager = factory.get_service_manager(prefer=backend_pref)

    claude = shutil.which("claude")
    if claude:
        subprocess.run([claude, "mcp", "remove", MCP_SERVER_NAME, "-s", "user"],
                       check=False, capture_output=True)
        print(f"[OK] unregistered MCP {MCP_SERVER_NAME}")

    if cfg:
        for w in cfg.wsl:
            svc_name = f"{SERVICE_NAME_HUB}-wsl-{w.distro.lower()}"
            manager.uninstall(svc_name)
            print(f"[OK] uninstalled WSL service {svc_name}")

    manager.uninstall(SERVICE_NAME_HUB)
    print(f"[OK] uninstalled service {SERVICE_NAME_HUB}")

    if args.purge:
        if paths.hub_dir().exists():
            import shutil as _sh
            _sh.rmtree(paths.hub_dir())
            print(f"[OK] purged {paths.hub_dir()}")

    return 0
