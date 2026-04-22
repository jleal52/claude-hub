"""Compose a WSL ServiceSpec as a Windows-side one wrapping wsl.exe."""
from __future__ import annotations

from .base import ServiceSpec

_WSL_EXE_DEFAULT = r"C:\Windows\System32\wsl.exe"


def wrap_for_wsl(inner: ServiceSpec, *, distro: str, wsl_cwd: str,
                 wsl_exe: str = _WSL_EXE_DEFAULT) -> ServiceSpec:
    """Return a new ServiceSpec wrapping wsl.exe -d <distro> --cd <wsl_cwd> -- <inner>."""
    composed = [
        wsl_exe,
        "-d", distro,
        "--cd", wsl_cwd,
        "--",
        *inner.command,
    ]
    return ServiceSpec(
        name=inner.name,
        command=composed,
        cwd=inner.cwd,
        env=inner.env,
        auto_start=inner.auto_start,
        description=inner.description,
        stdout_log=inner.stdout_log,
        stderr_log=inner.stderr_log,
    )
