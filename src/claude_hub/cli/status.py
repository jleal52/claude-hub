"""status subcommand."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict

from ..config import load as load_config
from ..service import factory

SERVICE_NAME_HUB = "claude-hub"
MCP_SERVER_NAME = "claude-hub-projects"


def run(args: argparse.Namespace) -> int:
    cfg = load_config()
    backend_pref = cfg.service.backend if cfg else "auto"
    manager = factory.get_service_manager(prefer=backend_pref)

    services = [SERVICE_NAME_HUB]
    if cfg:
        for w in cfg.wsl:
            services.append(f"{SERVICE_NAME_HUB}-wsl-{w.distro.lower()}")

    statuses = [manager.status(s) for s in services]

    mcp_registered = False
    claude = shutil.which("claude")
    if claude:
        out = subprocess.run(
            [claude, "mcp", "list"], capture_output=True, text=True, check=False,
        )
        mcp_registered = MCP_SERVER_NAME in out.stdout

    if args.json:
        print(json.dumps({
            "services": [asdict(s) for s in statuses],
            "mcp_registered": mcp_registered,
        }, indent=2))
        return 0

    print("Services:")
    for s in statuses:
        state = "running" if s.running else ("installed" if s.installed else "not installed")
        print(f"  {s.name:35s} {state}")
    print(f"MCP {MCP_SERVER_NAME}: {'registered' if mcp_registered else 'not registered'}")
    return 0
