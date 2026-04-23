"""NSSM ServiceManager backend for Windows (opt-in, requires admin)."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .base import ServiceManager, ServiceSpec, ServiceStatus


def _looks_like_wsl_command(cmd: list[str]) -> bool:
    """Return True when the command shells out to wsl.exe."""
    return any("wsl.exe" in part.lower() or part.lower() == "wsl" for part in cmd[:1])


class NssmManager(ServiceManager):
    def install(self, spec: ServiceSpec) -> None:
        # Guardrail: NSSM by default runs services under LocalSystem, and
        # `wsl.exe` categorically refuses to launch under LocalSystem
        # (WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED). Even for the Windows-side
        # `claude remote-control`, LocalSystem has no access to the user's
        # OAuth credentials at %USERPROFILE%\.claude\, so remote sessions
        # never show up in claude.ai/code. Refuse the install up front
        # rather than produce a broken service.
        if _looks_like_wsl_command(spec.command):
            raise RuntimeError(
                f"refusing to install {spec.name} under NSSM: wsl.exe cannot run "
                "as LocalSystem (WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED). "
                "Use the Scheduled Task backend (default) instead — it runs "
                "under your interactive token, which WSL accepts."
            )

        subprocess.run(["nssm", "stop", spec.name, "confirm"], check=False, capture_output=True)
        subprocess.run(["nssm", "remove", spec.name, "confirm"], check=False, capture_output=True)

        exe = spec.command[0]
        app_params = " ".join(f'"{arg}"' if " " in arg else arg for arg in spec.command[1:])

        result = subprocess.run(["nssm", "install", spec.name, exe],
                                check=False, capture_output=True, text=True)
        if result.returncode != 0:
            msg = (result.stderr or result.stdout or "").strip() or "no output"
            raise RuntimeError(
                f"nssm install failed for {spec.name} (exit {result.returncode}): {msg}\n"
                "Hint: NSSM requires an elevated shell. Re-run from Administrator PowerShell."
            )

        # Each `nssm set` requires admin just like `nssm install`. If the
        # shell lost elevation (or was never elevated and `nssm install`
        # silently upgraded itself via UAC just the once), these fail with
        # "Access denied" and earlier versions ignored that — leaving a
        # registered service with empty AppParameters that would never
        # actually launch `claude remote-control`. Validate every call and
        # roll back on failure so we never leave a half-configured service.
        settings: list[tuple[str, str]] = [
            ("AppParameters", app_params),
            ("AppDirectory", spec.cwd),
        ]
        if spec.auto_start:
            settings.append(("Start", "SERVICE_AUTO_START"))
        if spec.stdout_log:
            settings.append(("AppStdout", str(spec.stdout_log)))
        if spec.stderr_log:
            settings.append(("AppStderr", str(spec.stderr_log)))
        if spec.description:
            settings.append(("Description", spec.description))

        for key, value in settings:
            r = subprocess.run(
                ["nssm", "set", spec.name, key, value],
                check=False, capture_output=True, text=True,
            )
            if r.returncode != 0:
                subprocess.run(["nssm", "remove", spec.name, "confirm"],
                               check=False, capture_output=True)
                msg = (r.stderr or r.stdout or "").strip() or "no output"
                raise RuntimeError(
                    f"nssm set {key} failed for {spec.name} "
                    f"(exit {r.returncode}): {msg}\n"
                    "Hint: every `nssm set` needs admin, not just `nssm install`. "
                    "Re-run the installer from an Administrator PowerShell."
                )

        subprocess.run(["nssm", "start", spec.name], check=False, capture_output=True)

    def uninstall(self, name: str) -> None:
        subprocess.run(["nssm", "stop", name, "confirm"], check=False, capture_output=True)
        subprocess.run(["nssm", "remove", name, "confirm"], check=False, capture_output=True)

    def start(self, name: str) -> None:
        subprocess.run(["nssm", "start", name], check=False, capture_output=True)

    def stop(self, name: str) -> None:
        subprocess.run(["nssm", "stop", name, "confirm"], check=False, capture_output=True)

    def restart(self, name: str) -> None:
        subprocess.run(["nssm", "restart", name], check=False, capture_output=True)

    def status(self, name: str) -> ServiceStatus:
        result = subprocess.run(
            ["nssm", "status", name],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return ServiceStatus(name=name, installed=False, running=False,
                                 auto_start=False, pid=None)
        running = "SERVICE_RUNNING" in result.stdout
        return ServiceStatus(name=name, installed=True, running=running,
                             auto_start=True, pid=None)

    def list_logs(self, name: str) -> list[Path]:
        return []
