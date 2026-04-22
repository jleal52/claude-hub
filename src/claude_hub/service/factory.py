"""Select the right ServiceManager backend for the current platform."""
from __future__ import annotations

from typing import Literal

from ..platform import detect
from .base import ServiceManager

Backend = Literal["auto", "nssm", "scheduled-task", "systemd", "launchd"]


def get_service_manager(prefer: Backend = "auto") -> ServiceManager:
    os_name = detect.current_os()
    if os_name == "linux":
        from .linux_systemd import SystemdUserManager
        return SystemdUserManager()
    if os_name == "macos":
        from .macos_launchd import LaunchdManager
        return LaunchdManager()
    if os_name == "windows":
        if prefer == "nssm":
            from .windows_nssm import NssmManager
            return NssmManager()
        from .windows_scheduled_task import ScheduledTaskManager
        return ScheduledTaskManager()
    raise RuntimeError(f"unsupported OS: {os_name}")
