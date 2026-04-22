"""argparse root dispatcher for `claude-hub`."""
from __future__ import annotations

import argparse
import sys
from typing import Optional


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="claude-hub",
        description="Expose your machine(s) to claude.ai/code.",
    )
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p_install = sub.add_parser("install", help="Install hub services + MCP")
    p_install.add_argument("--hub-only", action="store_true")
    p_install.add_argument("--mcp-only", action="store_true")
    p_install.add_argument("--wsl", action="append", metavar="DISTRO", default=[])
    p_install.add_argument("--session-name", default=None)
    p_install.add_argument("--working-dir", default=None)
    p_install.add_argument("--use-nssm", action="store_true",
                           help="On Windows, use NSSM instead of Scheduled Task (requires admin)")
    p_install.add_argument("--no-interactive", action="store_true")

    p_uninstall = sub.add_parser("uninstall", help="Uninstall services + MCP")
    p_uninstall.add_argument("--purge", action="store_true",
                             help="Also delete ~/.claude-hub state + logs")

    p_status = sub.add_parser("status", help="Show services and MCP status")
    p_status.add_argument("--json", action="store_true")

    p_logs = sub.add_parser("logs", help="Show service logs")
    p_logs.add_argument("service", nargs="?", default=None)
    p_logs.add_argument("--follow", "-f", action="store_true")
    p_logs.add_argument("--lines", "-n", type=int, default=50)

    sub.add_parser("doctor", help="Diagnose install health")

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        from claude_hub import __version__
        print(__version__)
        return 0

    if args.command == "install":
        from .install import run as run_install
        return run_install(args)
    if args.command == "uninstall":
        from .uninstall import run as run_uninstall
        return run_uninstall(args)
    if args.command == "status":
        from .status import run as run_status
        return run_status(args)
    if args.command == "logs":
        from .logs import run as run_logs
        return run_logs(args)
    if args.command == "doctor":
        from .doctor import run as run_doctor
        return run_doctor(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
