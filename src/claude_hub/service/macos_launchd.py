"""launchd user agent ServiceManager backend (macOS)."""
from __future__ import annotations

import plistlib
import subprocess
from pathlib import Path
from typing import Optional

from .base import ServiceManager, ServiceSpec, ServiceStatus

_LABEL_PREFIX = "com.github.jleal52"


def _label(name: str) -> str:
    return f"{_LABEL_PREFIX}.{name}"


def _agents_dir() -> Path:
    d = Path.home() / "Library" / "LaunchAgents"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _plist_path(name: str) -> Path:
    return _agents_dir() / f"{_label(name)}.plist"


def _plist_content(spec: ServiceSpec) -> dict:
    content: dict = {
        "Label": _label(spec.name),
        "ProgramArguments": list(spec.command),
        "WorkingDirectory": spec.cwd,
        "RunAtLoad": spec.auto_start,
        "KeepAlive": True,
        "EnvironmentVariables": dict(spec.env),
    }
    if spec.stdout_log:
        content["StandardOutPath"] = str(spec.stdout_log)
    if spec.stderr_log:
        content["StandardErrorPath"] = str(spec.stderr_log)
    return content


class LaunchdManager(ServiceManager):
    def install(self, spec: ServiceSpec) -> None:
        path = _plist_path(spec.name)
        with open(path, "wb") as f:
            plistlib.dump(_plist_content(spec), f)
        subprocess.run(["launchctl", "load", "-w", str(path)], check=False)

    def uninstall(self, name: str) -> None:
        path = _plist_path(name)
        subprocess.run(["launchctl", "unload", "-w", str(path)], check=False)
        if path.exists():
            path.unlink()

    def start(self, name: str) -> None:
        subprocess.run(["launchctl", "start", _label(name)], check=False)

    def stop(self, name: str) -> None:
        subprocess.run(["launchctl", "stop", _label(name)], check=False)

    def restart(self, name: str) -> None:
        self.stop(name)
        self.start(name)

    def status(self, name: str) -> ServiceStatus:
        path = _plist_path(name)
        if not path.exists():
            return ServiceStatus(name=name, installed=False, running=False,
                                 auto_start=False, pid=None)
        result = subprocess.run(
            ["launchctl", "list", _label(name)],
            capture_output=True, text=True, check=False,
        )
        running = result.returncode == 0
        pid: Optional[int] = None
        if running:
            for line in result.stdout.splitlines():
                if '"PID"' in line:
                    try:
                        pid = int(line.split("=")[1].strip().rstrip(";"))
                    except (ValueError, IndexError):
                        pass
                    break
        return ServiceStatus(name=name, installed=True, running=running,
                             auto_start=True, pid=pid)

    def list_logs(self, name: str) -> list[Path]:
        return []
