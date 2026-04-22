"""Windows Scheduled Task ServiceManager backend.

Uses `schtasks` CLI to register a user task that runs at logon. Does NOT
require Administrator privileges (user-scope task).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .base import ServiceManager, ServiceSpec, ServiceStatus

def _task_name(name: str) -> str:
    """Return the absolute Task Scheduler path for a task.

    We register tasks at the root (`\\<name>`) instead of under a custom
    folder (`\\claude-hub\\<name>`). Creating a folder under Task Scheduler's
    root requires elevated privileges on many Windows installs, which would
    defeat the "no admin required" guarantee of this backend.

    The `name` is already unique (e.g. "claude-hub", "claude-hub-wsl-debian"),
    so the flat layout is not a namespacing concern.
    """
    return f"\\{name}"


def _build_tr_argument(spec: ServiceSpec) -> str:
    exe = spec.command[0]
    rest = " ".join(spec.command[1:])
    return f'"{exe}" {rest}' if rest else f'"{exe}"'


class ScheduledTaskManager(ServiceManager):
    def install(self, spec: ServiceSpec) -> None:
        cmd = [
            "schtasks", "/Create", "/F",
            "/SC", "ONLOGON",
            "/TN", _task_name(spec.name),
            "/TR", _build_tr_argument(spec),
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            # schtasks prints errors to stdout (not stderr) in many cases.
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            msg = stderr or stdout or "no output"
            raise RuntimeError(
                f"schtasks /Create failed for {spec.name} (exit {result.returncode}): {msg}"
            )

    def uninstall(self, name: str) -> None:
        subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", _task_name(name)],
            check=False, capture_output=True,
        )

    def start(self, name: str) -> None:
        subprocess.run(
            ["schtasks", "/Run", "/TN", _task_name(name)],
            check=False, capture_output=True,
        )

    def stop(self, name: str) -> None:
        subprocess.run(
            ["schtasks", "/End", "/TN", _task_name(name)],
            check=False, capture_output=True,
        )

    def restart(self, name: str) -> None:
        self.stop(name)
        self.start(name)

    def status(self, name: str) -> ServiceStatus:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", _task_name(name), "/FO", "LIST"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return ServiceStatus(name=name, installed=False, running=False,
                                 auto_start=False, pid=None)
        running = "Running" in result.stdout
        return ServiceStatus(name=name, installed=True, running=running,
                             auto_start=True, pid=None)

    def list_logs(self, name: str) -> list[Path]:
        return []
