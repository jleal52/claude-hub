"""Compose a WSL ServiceSpec as a Windows-side one wrapping wsl.exe."""
from __future__ import annotations

import shlex

from .base import ServiceSpec

_WSL_EXE_DEFAULT = r"C:\Windows\System32\wsl.exe"


def wrap_for_wsl(inner: ServiceSpec, *, distro: str, wsl_cwd: str,
                 wsl_exe: str = _WSL_EXE_DEFAULT) -> ServiceSpec:
    """Wrap a command as `wsl.exe -d <distro> --cd <cwd> -- bash -lc '<cmd> < /dev/null'`.

    The `bash -lc` is required so the login shell sources `~/.profile` and
    `claude` from `~/.local/bin` resolves. The `< /dev/null` redirect prevents
    `claude remote-control` from entering `--print` mode when it detects that
    stdin is not a TTY under Task Scheduler or NSSM.
    """
    inner_cmd = shlex.join(inner.command) + " < /dev/null"
    composed = [
        wsl_exe,
        "-d", distro,
        "--cd", wsl_cwd,
        "--",
        "bash", "-lc", inner_cmd,
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
