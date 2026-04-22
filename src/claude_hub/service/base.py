"""Abstract ServiceManager protocol + dataclasses."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class ServiceSpec:
    """Inputs to install a service. All backends receive the same shape."""
    name: str
    command: list[str]
    cwd: str
    env: dict[str, str] = field(default_factory=dict)
    auto_start: bool = True
    description: str = ""
    stdout_log: Optional[Path] = None
    stderr_log: Optional[Path] = None


@dataclass(frozen=True)
class ServiceStatus:
    name: str
    installed: bool
    running: bool
    auto_start: bool
    pid: Optional[int]
    extra: dict[str, str] = field(default_factory=dict)


class ServiceManager(ABC):
    """Platform-agnostic service management."""

    @abstractmethod
    def install(self, spec: ServiceSpec) -> None: ...

    @abstractmethod
    def uninstall(self, name: str) -> None: ...

    @abstractmethod
    def start(self, name: str) -> None: ...

    @abstractmethod
    def stop(self, name: str) -> None: ...

    @abstractmethod
    def restart(self, name: str) -> None: ...

    @abstractmethod
    def status(self, name: str) -> ServiceStatus: ...

    @abstractmethod
    def list_logs(self, name: str) -> list[Path]: ...
