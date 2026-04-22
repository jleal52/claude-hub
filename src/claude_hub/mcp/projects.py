"""Project discovery from ~/.claude/projects/."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

_MAX_LINES_PROBE_FOR_CWD = 5


@dataclass(frozen=True)
class ProjectInfo:
    path: str
    last_modified: datetime
    n_sessions: int


def list_projects(limit: int = 20, claude_home: Path = Path.home() / ".claude") -> list[ProjectInfo]:
    projects_root = Path(claude_home) / "projects"
    if not projects_root.is_dir():
        return []

    out: list[ProjectInfo] = []
    for project_dir in projects_root.iterdir():
        if not project_dir.is_dir():
            continue
        jsonls = sorted(project_dir.glob("*.jsonl"))
        if not jsonls:
            continue
        last_mtime = max(p.stat().st_mtime for p in jsonls)
        cwd = _extract_cwd(jsonls[0]) or _fallback_parse_dirname(project_dir.name)
        out.append(ProjectInfo(
            path=cwd,
            last_modified=datetime.fromtimestamp(last_mtime, tz=timezone.utc),
            n_sessions=len(jsonls),
        ))

    out.sort(key=lambda p: p.last_modified, reverse=True)
    return out[:limit]


def _extract_cwd(jsonl_path: Path) -> str | None:
    """Read up to _MAX_LINES_PROBE_FOR_CWD lines; return the first 'cwd' value found."""
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= _MAX_LINES_PROBE_FOR_CWD:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and isinstance(obj.get("cwd"), str):
                    return obj["cwd"]
    except OSError as e:
        log.warning("cannot read %s: %s", jsonl_path, e)
    return None


def _fallback_parse_dirname(dirname: str) -> str:
    """Convert '-home-user-foo' to '/home/user/foo'. Ambiguous with dashes in real names."""
    if not dirname.startswith("-"):
        return dirname
    return "/" + dirname[1:].replace("-", "/")
