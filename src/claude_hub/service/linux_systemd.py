"""systemd --user ServiceManager backend (Linux)."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from .base import ServiceManager, ServiceSpec, ServiceStatus


def _unit_dir() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    d = base / "systemd" / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _unit_file_text(spec: ServiceSpec) -> str:
    exec_start = " ".join([spec.command[0]] + [f'"{arg}"' for arg in spec.command[1:]])
    env_lines = "\n".join(f'Environment="{k}={v}"' for k, v in spec.env.items())
    return f"""[Unit]
Description={spec.description or spec.name}
After=network.target

[Service]
Type=simple
ExecStart={exec_start}
WorkingDirectory={spec.cwd}
{env_lines}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


class SystemdUserManager(ServiceManager):
    def install(self, spec: ServiceSpec) -> None:
        unit_path = _unit_dir() / f"{spec.name}.service"
        unit_path.write_text(_unit_file_text(spec), encoding="utf-8")
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
        if spec.auto_start:
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", spec.name], check=False
            )

    def uninstall(self, name: str) -> None:
        subprocess.run(["systemctl", "--user", "disable", "--now", name], check=False)
        unit_path = _unit_dir() / f"{name}.service"
        if unit_path.exists():
            unit_path.unlink()
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)

    def start(self, name: str) -> None:
        subprocess.run(["systemctl", "--user", "start", name], check=False)

    def stop(self, name: str) -> None:
        subprocess.run(["systemctl", "--user", "stop", name], check=False)

    def restart(self, name: str) -> None:
        subprocess.run(["systemctl", "--user", "restart", name], check=False)

    def status(self, name: str) -> ServiceStatus:
        unit_path = _unit_dir() / f"{name}.service"
        if not unit_path.exists():
            return ServiceStatus(name=name, installed=False, running=False,
                                 auto_start=False, pid=None)
        active = subprocess.run(
            ["systemctl", "--user", "is-active", name],
            capture_output=True, text=True, check=False,
        ).stdout.strip() == "active"
        enabled = subprocess.run(
            ["systemctl", "--user", "is-enabled", name],
            capture_output=True, text=True, check=False,
        ).stdout.strip() == "enabled"
        pid_text = subprocess.run(
            ["systemctl", "--user", "show", "-p", "MainPID", "--value", name],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        pid: Optional[int] = None
        if pid_text.isdigit() and int(pid_text) > 0:
            pid = int(pid_text)
        return ServiceStatus(name=name, installed=True, running=active,
                             auto_start=enabled, pid=pid)

    def list_logs(self, name: str) -> list[Path]:
        return []
