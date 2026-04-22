"""logs subcommand - tails the service stdout/stderr logs."""
from __future__ import annotations

import argparse
import subprocess

from ..platform import detect, paths


def run(args: argparse.Namespace) -> int:
    os_name = detect.current_os()
    name = args.service or "claude-hub"

    if os_name == "linux":
        cmd = ["journalctl", "--user", "-u", name, "-n", str(args.lines)]
        if args.follow:
            cmd.append("-f")
        subprocess.run(cmd, check=False)
        return 0

    log = paths.logs_dir() / f"{name.replace('claude-hub', 'hub')}.out.log"
    if not log.exists():
        print(f"No log at {log}")
        return 1
    if args.follow:
        subprocess.run(["tail", "-n", str(args.lines), "-f", str(log)], check=False)
    else:
        text = log.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()[-args.lines:]
        print("\n".join(lines))
    return 0
