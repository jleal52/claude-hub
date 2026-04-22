"""NSSM ServiceManager backend for Windows (opt-in, requires admin)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

from .base import ServiceManager, ServiceSpec, ServiceStatus


class NssmManager(ServiceManager):
    def install(self, spec: ServiceSpec) -> None:
        subprocess.run(["nssm", "stop", spec.name, "confirm"], check=False, capture_output=True)
        subprocess.run(["nssm", "remove", spec.name, "confirm"], check=False, capture_output=True)

        exe = spec.command[0]
        app_params = " ".join(f'"{arg}"' if " " in arg else arg for arg in spec.command[1:])

        subprocess.run(["nssm", "install", spec.name, exe], check=False, capture_output=True)
        subprocess.run(["nssm", "set", spec.name, "AppParameters", app_params],
                       check=False, capture_output=True)
        subprocess.run(["nssm", "set", spec.name, "AppDirectory", spec.cwd],
                       check=False, capture_output=True)
        if spec.auto_start:
            subprocess.run(["nssm", "set", spec.name, "Start", "SERVICE_AUTO_START"],
                           check=False, capture_output=True)
        if spec.stdout_log:
            subprocess.run(["nssm", "set", spec.name, "AppStdout", str(spec.stdout_log)],
                           check=False, capture_output=True)
        if spec.stderr_log:
            subprocess.run(["nssm", "set", spec.name, "AppStderr", str(spec.stderr_log)],
                           check=False, capture_output=True)
        if spec.description:
            subprocess.run(["nssm", "set", spec.name, "Description", spec.description],
                           check=False, capture_output=True)
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
