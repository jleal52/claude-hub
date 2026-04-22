"""Windows Scheduled Task ServiceManager backend.

Uses `schtasks` CLI to register a user task that runs at logon. Does NOT
require Administrator privileges (user-scope task).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .base import ServiceManager, ServiceSpec, ServiceStatus

_TASK_FOLDER = "claude-hub"


def _task_name(name: str) -> str:
    return f"\\{_TASK_FOLDER}\\{name}"


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
        subprocess.run(cmd, check=False, capture_output=True)

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
