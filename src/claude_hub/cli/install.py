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
        try:
            manager.install(spec)
            print(f"[OK] installed service {SERVICE_NAME_HUB}")
        except RuntimeError as e:
            print(f"[FAIL] {SERVICE_NAME_HUB}: {e}", file=sys.stderr)

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
                try:
                    manager.install(wrapped)
                    wsl_entries.append(
                        WslEntry(distro=distro, session_name=wsl_session_name, working_dir=wsl_cwd)
                    )
                    print(f"[OK] installed WSL service for {distro}")
                except RuntimeError as e:
                    print(f"[FAIL] WSL service for {distro}: {e}", file=sys.stderr)

                # Also install the claude-hub package + register the MCP INSIDE the
                # distro. Without this, the WSL-Debian environment in claude.ai/code
                # wouldn't have claude-hub-projects tools (the MCP is per-side).
                if do_mcp and _install_mcp_inside_wsl(distro):
                    print(f"[OK] registered MCP inside {distro}")
                elif do_mcp:
                    print(
                        f"[WARN] could not register MCP inside {distro}. "
                        f"Run manually inside the distro: "
                        f"pipx install claude-code-hub && claude-hub install --no-interactive --mcp-only",
                        file=sys.stderr,
                    )

    if do_mcp:
        if _register_mcp(claude_bin):
            print(f"[OK] registered MCP {MCP_SERVER_NAME}")
        else:
            print(f"[FAIL] could not register MCP {MCP_SERVER_NAME}")

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


def _install_mcp_inside_wsl(distro: str) -> bool:
    """Install claude-code-hub + register the MCP inside a WSL distro.

    Steps (each run inside `wsl -d <distro> -- bash -lc ...`):
      1. Ensure pipx is available (install via pip --user if missing).
      2. `pipx install --force claude-code-hub` to get the package.
      3. `claude-hub install --no-interactive --mcp-only` to register the MCP
         via `claude mcp add` against the OAuth creds inside the distro.

    Returns True on full success, False if any step fails. Errors are
    captured into the caller's warning message, not printed here, so we don't
    spam during normal operation.
    """
    wsl = "wsl.exe"

    def _run_in_wsl(script: str, timeout: int = 180) -> subprocess.CompletedProcess:
        return subprocess.run(
            [wsl, "-d", distro, "--", "bash", "-lc", script],
            capture_output=True, text=True, check=False, timeout=timeout,
        )

    # 1. pipx
    probe = _run_in_wsl("command -v pipx >/dev/null 2>&1 && echo OK || echo MISSING")
    if "MISSING" in probe.stdout:
        # Try pip install --user (break-system-packages needed on Debian/Ubuntu
        # with PEP 668 externally-managed markers).
        install_pipx = _run_in_wsl(
            "python3 -m pip install --user --break-system-packages --quiet pipx "
            "&& python3 -m pipx ensurepath >/dev/null 2>&1"
        )
        if install_pipx.returncode != 0:
            return False

    # 2. Install the package. Ensure $HOME/.local/bin is on PATH for this and
    #    later steps; pipx ensurepath only affects future shells.
    install_pkg = _run_in_wsl(
        'export PATH="$HOME/.local/bin:$PATH"; '
        "pipx install --force claude-code-hub"
    )
    if install_pkg.returncode != 0:
        return False

    # 3. Register the MCP via the installed CLI (so the same '--' separator
    #    and `claude mcp add` logic is used as on the host).
    register = _run_in_wsl(
        'export PATH="$HOME/.local/bin:$PATH"; '
        "claude-hub install --no-interactive --mcp-only"
    )
    return register.returncode == 0


def _register_mcp(claude_bin: str) -> bool:
    """Register the MCP via `claude mcp add`. Returns True on success."""
    py = sys.executable
    subprocess.run([claude_bin, "mcp", "remove", MCP_SERVER_NAME, "-s", "user"],
                   check=False, capture_output=True)
    # The `--` separator is REQUIRED: without it `claude mcp add` interprets
    # `-m` as one of its own options and fails with "unknown option '-m'".
    result = subprocess.run(
        [claude_bin, "mcp", "add", "-s", "user", MCP_SERVER_NAME,
         "--", py, "-m", "claude_hub.mcp"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: `claude mcp add` failed (exit {result.returncode}):", file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return False
    return True


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
