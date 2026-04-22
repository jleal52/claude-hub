"""claude remote-control subprocess spawner and lifecycle management."""
from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from .state import SpawnEntry, load, save

log = logging.getLogger(__name__)

_ENV_URL_RE = re.compile(r"https://claude\.ai/code\?environment=env_[A-Za-z0-9]+")
_POLL_INTERVAL = 0.2  # seconds
_STOP_SIGTERM_WAIT = 5.0  # seconds to wait for graceful stop before SIGKILL / taskkill /F

_IS_WINDOWS = sys.platform == "win32"


@dataclass(frozen=True)
class SpawnResult:
    name: str
    path: str
    pid: int
    env_url: Optional[str]
    started_at: str


@dataclass(frozen=True)
class StopResult:
    name: str
    stopped: bool
    error: Optional[str] = None


@dataclass(frozen=True)
class RunningSession:
    name: str
    path: str
    pid: int
    env_url: Optional[str]
    started_at: str
    alive: bool


def derive_name_from_path(path: str) -> str:
    base = Path(path).name
    return base if base else "root"


def resolve_name_collision(name: str, existing: Iterable[str]) -> str:
    existing_set = set(existing)
    if name not in existing_set:
        return name
    n = 2
    while f"{name}-{n}" in existing_set:
        n += 1
    return f"{name}-{n}"


def extract_env_url(text: str) -> Optional[str]:
    m = _ENV_URL_RE.search(text)
    return m.group(0) if m else None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def spawn_session(
    path: str,
    name: Optional[str] = None,
    claude_bin: str = "claude",
    state_dir: Path = Path.home() / ".claude-hub",
    startup_timeout: float = 15.0,
) -> SpawnResult:
    if not Path(path).is_dir():
        raise ValueError(f"path does not exist or is not a directory: {path}")

    state_dir = Path(state_dir)
    entries = load(state_dir)
    existing_names = {e.name for e in entries}

    base_name = name or derive_name_from_path(path)
    final_name = resolve_name_collision(base_name, existing_names)

    log_dir = state_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"spawn-{final_name}.log"

    cmd = [claude_bin, "remote-control", "--name", final_name, "--spawn", "same-dir"]
    log_file = open(log_path, "ab", buffering=0)

    popen_kwargs = dict(
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=path,
    )
    if _IS_WINDOWS:
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
    else:
        popen_kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError as e:
        log_file.close()
        raise RuntimeError(f"failed to spawn {claude_bin}: {e}") from e

    started_at = _now_iso()
    env_url = _wait_for_env_url(log_path, proc.pid, startup_timeout)

    if env_url is None:
        _kill_pid(proc.pid)
        tail = _tail_log(log_path, 15)
        log_file.close()
        raise RuntimeError(
            f"spawn did not reach 'Connected' within {startup_timeout}s. Log tail:\n{tail}"
        )

    log_file.close()

    entry = SpawnEntry(
        name=final_name,
        path=path,
        pid=proc.pid,
        env_url=env_url,
        started_at=started_at,
    )
    entries.append(entry)
    save(state_dir, entries)

    return SpawnResult(
        name=final_name,
        path=path,
        pid=proc.pid,
        env_url=env_url,
        started_at=started_at,
    )


def stop_session(name: str, state_dir: Path = Path.home() / ".claude-hub") -> StopResult:
    state_dir = Path(state_dir)
    entries = load(state_dir)
    target = next((e for e in entries if e.name == name), None)
    if target is None:
        return StopResult(name=name, stopped=False, error="unknown name")

    killed = _kill_pid(target.pid, grace_seconds=_STOP_SIGTERM_WAIT)
    entries = [e for e in entries if e.name != name]
    save(state_dir, entries)
    if not killed:
        return StopResult(name=name, stopped=False, error="failed to kill process")
    return StopResult(name=name, stopped=True)


def list_running(state_dir: Path = Path.home() / ".claude-hub") -> list[RunningSession]:
    state_dir = Path(state_dir)
    entries = load(state_dir)
    out: list[RunningSession] = []
    for e in entries:
        alive = _pid_alive(e.pid)
        out.append(RunningSession(
            name=e.name,
            path=e.path,
            pid=e.pid,
            env_url=e.env_url,
            started_at=e.started_at,
            alive=alive,
        ))
    return out


def _wait_for_env_url(log_path: Path, pid: int, timeout: float) -> Optional[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return None
        if log_path.exists():
            content = log_path.read_text(encoding="utf-8", errors="replace")
            url = extract_env_url(content)
            if url:
                return url
        time.sleep(_POLL_INTERVAL)
    return None


def _pid_alive(pid: int) -> bool:
    # os.kill(pid, 0) works on both POSIX and Windows (Python >= 3.3).
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def _kill_pid(pid: int, grace_seconds: float = _STOP_SIGTERM_WAIT) -> bool:
    if _IS_WINDOWS:
        return _kill_pid_windows(pid, grace_seconds)
    return _kill_pid_posix(pid, grace_seconds)


def _kill_pid_windows(pid: int, grace_seconds: float) -> bool:
    # Graceful: taskkill without /F sends WM_CLOSE to the main window. For
    # detached console processes (no window) this is a no-op but it is still
    # worth attempting for the occasional windowed claude.exe case.
    subprocess.run(["taskkill", "/PID", str(pid)], capture_output=True)
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(_POLL_INTERVAL)
    # Force-kill the whole process tree. `claude remote-control` spawns child
    # claude.exe sessions; /T ensures they are all taken down.
    result = subprocess.run(
        ["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True
    )
    # Source of truth is taskkill's exit code, not `_pid_alive`: after /F the
    # process may still have an open handle for a brief window, making
    # `os.kill(pid, 0)` lie (it succeeds on zombies).
    #   0  -> process killed
    #   128 -> process not found (already dead)
    # Anything else (access denied, etc.) is a real failure.
    if result.returncode in (0, 128):
        return True
    time.sleep(_POLL_INTERVAL)
    return not _pid_alive(pid)


def _kill_pid_posix(pid: int, grace_seconds: float) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(_POLL_INTERVAL)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    time.sleep(_POLL_INTERVAL)
    return not _pid_alive(pid)


def _tail_log(log_path: Path, n: int) -> str:
    if not log_path.exists():
        return "(no log file)"
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[-n:])
