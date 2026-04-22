"""Atomic load/save for spawn state."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_STATE_FILENAME = "spawns.json"
_REQUIRED_FIELDS = {"name", "path", "pid", "started_at"}


@dataclass(frozen=True)
class SpawnEntry:
    name: str
    path: str
    pid: int
    env_url: Optional[str]
    started_at: str


def load(state_dir: Path) -> list[SpawnEntry]:
    """Read spawns.json from state_dir. Returns [] if missing or invalid."""
    state_dir = Path(state_dir)
    path = state_dir / _STATE_FILENAME
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("state file root must be a list")
        out: list[SpawnEntry] = []
        for raw in data:
            if not isinstance(raw, dict):
                raise ValueError("entry must be an object")
            missing = _REQUIRED_FIELDS - raw.keys()
            if missing:
                raise ValueError(f"entry missing fields: {sorted(missing)}")
            out.append(SpawnEntry(
                name=str(raw["name"]),
                path=str(raw["path"]),
                pid=int(raw["pid"]),
                env_url=raw.get("env_url"),
                started_at=str(raw["started_at"]),
            ))
        return out
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        log.warning("state file at %s unreadable (%s); treating as empty", path, e)
        return []


def save(state_dir: Path, entries: list[SpawnEntry]) -> None:
    """Write spawns.json atomically under state_dir."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / _STATE_FILENAME
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = json.dumps([asdict(e) for e in entries], indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
