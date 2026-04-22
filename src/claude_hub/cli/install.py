"""install subcommand - composes ServiceSpec + registers services + MCP."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ..platform import detect, paths
from ..service import factory
from ..service.base import ServiceSpec
from ..service.wsl_wrapper import wrap_for_wsl
from ..config import Config, HubConfig, WslEntry, ServiceConfig, save


SERVICE_NAME_HUB = "claude-hub"
MCP_SERVER_NAME = "claude-hub-projects"


def run(args: argparse.Namespace) -> int:
    paths.ensure_dirs()
    if args.no_interactive:
        return _install_non_interactive(args)
    return _install_interactive(args)


def _install_non_interactive(args: argparse.Namespace) -> int:
    claude_bin = detect.find_claude_binary()
    if not claude_bin:
        print("ERROR: `claude` not found on PATH. Install Claude Code first.", file=sys.stderr)
        return 2

    session_name = args.session_name or detect.default_session_name()
    working_dir = args.working_dir or str(Path.home())

    backend_pref = "nssm" if args.use_nssm else "auto"
    manager = factory.get_service_manager(prefer=backend_pref)

    do_hub = not args.mcp_only
    do_mcp = not args.hub_only

    if do_hub:
        spec = ServiceSpec(
            name=SERVICE_NAME_HUB,
            command=[claude_bin, "remote-control", "--name", session_name, "--spawn", "same-dir"],
            cwd=working_dir,
            env={},
            auto_start=True,
            description=f"claude-hub ({session_name})",
            stdout_log=paths.logs_dir() / "hub.out.log",
            stderr_log=paths.logs_dir() / "hub.err.log",
        )
        manager.install(spec)
        print(f"[OK] installed service {SERVICE_NAME_HUB}")

    wsl_entries: list[WslEntry] = []
    if do_hub and args.wsl:
        if detect.current_os() != "windows":
            print("WARNING: --wsl is only meaningful on Windows; skipping", file=sys.stderr)
        else:
            for distro in args.wsl:
                wsl_cwd = "/home/" + _wsl_user(distro)
                wsl_session_name = f"WSL-{distro}"
                inner = ServiceSpec(
                    name=f"{SERVICE_NAME_HUB}-wsl-{distro.lower()}",
                    command=["claude", "remote-control", "--name", wsl_session_name, "--spawn", "same-dir"],
                    cwd="",
                    env={},
                )
                wrapped = wrap_for_wsl(inner, distro=distro, wsl_cwd=wsl_cwd)
                manager.install(wrapped)
                wsl_entries.append(
                    WslEntry(distro=distro, session_name=wsl_session_name, working_dir=wsl_cwd)
                )
                print(f"[OK] installed WSL service for {distro}")

    if do_mcp:
        _register_mcp(claude_bin)
        print(f"[OK] registered MCP {MCP_SERVER_NAME}")

    save(
        Config(
            version=1,
            hub=HubConfig(
                session_name=session_name,
                working_dir=working_dir,
                claude_bin=claude_bin,
            ),
            wsl=wsl_entries,
            service=ServiceConfig(backend=backend_pref),
        )
    )
    print("Done. Check status with: claude-hub status")
    return 0


def _register_mcp(claude_bin: str) -> None:
    py = sys.executable
    subprocess.run([claude_bin, "mcp", "remove", MCP_SERVER_NAME, "-s", "user"],
                   check=False, capture_output=True)
    subprocess.run(
        [claude_bin, "mcp", "add", "-s", "user", MCP_SERVER_NAME, py,
         "-m", "claude_hub.mcp"],
        check=False,
    )


def _install_interactive(args: argparse.Namespace) -> int:
    from types import SimpleNamespace
    print(f"Detecting environment... {detect.current_os()}")
    claude_bin = detect.find_claude_binary()
    if not claude_bin:
        print("ERROR: `claude` not found on PATH.", file=sys.stderr)
        return 2
    print(f"Found claude binary: {claude_bin}")

    default_name = detect.default_session_name()
    session_name = input(f"Session name [{default_name}]: ").strip() or default_name

    default_dir = str(Path.home())
    working_dir = input(f"Working directory [{default_dir}]: ").strip() or default_dir

    wsl_distros: list[str] = []
    if detect.current_os() == "windows":
        distros = detect.list_wsl_distros()
        if distros:
            print(f"Detected WSL distros: {', '.join(distros)}")
            ans = input("Register WSL distros? [y/N]: ").strip().lower()
            if ans == "y":
                for d in distros:
                    sel = input(f"  Include {d}? [y/N]: ").strip().lower()
                    if sel == "y":
                        wsl_distros.append(d)

    backend_pref = "auto"
    if detect.current_os() == "windows":
        ans = input("Use NSSM (requires admin) instead of Scheduled Task? [y/N]: ").strip().lower()
        if ans == "y":
            backend_pref = "nssm"

    non_interactive_args = SimpleNamespace(
        session_name=session_name,
        working_dir=working_dir,
        wsl=wsl_distros,
        use_nssm=(backend_pref == "nssm"),
        hub_only=False,
        mcp_only=False,
        no_interactive=True,
    )
    return _install_non_interactive(non_interactive_args)


def _wsl_user(distro: str) -> str:
    try:
        result = subprocess.run(
            ["wsl.exe", "-d", distro, "--", "whoami"],
            capture_output=True, text=True, check=False, timeout=15,
        )
        user = result.stdout.strip()
        return user or "root"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "root"
