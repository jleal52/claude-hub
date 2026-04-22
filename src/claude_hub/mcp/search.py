"""Search across conversation .jsonl files."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

_SNIPPET_RADIUS = 60  # chars before and after the first match


@dataclass(frozen=True)
class Match:
    project_path: str
    session_id: str
    timestamp: str
    snippet: str
    match_count: int


def search_conversations(
    query: str,
    limit: int = 20,
    case_sensitive: bool = False,
    claude_home: Path = Path.home() / ".claude",
) -> list[Match]:
    if not query:
        raise ValueError("query must be a non-empty string")

    needle = query if case_sensitive else query.lower()
    projects_root = Path(claude_home) / "projects"
    if not projects_root.is_dir():
        return []

    # (project_path, session_id) -> aggregated Match info
    accum: dict[tuple[str, str], _Agg] = {}

    for project_dir in projects_root.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_path in project_dir.glob("*.jsonl"):
            _scan_file(jsonl_path, needle, case_sensitive, accum)

    results = [
        Match(
            project_path=a.project_path,
            session_id=a.session_id,
            timestamp=a.latest_timestamp,
            snippet=a.first_snippet,
            match_count=a.match_count,
        )
        for a in accum.values()
    ]
    results.sort(key=lambda m: m.timestamp, reverse=True)
    return results[:limit]


@dataclass
class _Agg:
    project_path: str
    session_id: str
    latest_timestamp: str
    first_snippet: str
    match_count: int


def _scan_file(
    jsonl_path: Path,
    needle: str,
    case_sensitive: bool,
    accum: dict[tuple[str, str], _Agg],
) -> None:
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                text = _extract_text(obj)
                if not text:
                    continue
                haystack = text if case_sensitive else text.lower()
                hits = haystack.count(needle)
                if hits == 0:
                    continue
                session_id = str(obj.get("sessionId") or "")
                project_path = str(obj.get("cwd") or "")
                timestamp = str(obj.get("timestamp") or "")
                if not session_id or not project_path:
                    continue
                key = (project_path, session_id)
                first_idx = haystack.find(needle)
                snippet = _make_snippet(text, first_idx, len(needle))
                existing = accum.get(key)
                if existing is None:
                    accum[key] = _Agg(
                        project_path=project_path,
                        session_id=session_id,
                        latest_timestamp=timestamp,
                        first_snippet=snippet,
                        match_count=hits,
                    )
                else:
                    existing.match_count += hits
                    if timestamp > existing.latest_timestamp:
                        existing.latest_timestamp = timestamp
    except OSError as e:
        log.warning("cannot read %s: %s", jsonl_path, e)


def _extract_text(obj: dict) -> str:
    """Extract user/assistant visible text from a jsonl message object."""
    message = obj.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                t = block.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "\n".join(parts)
    return ""


def _make_snippet(text: str, match_start: int, match_len: int) -> str:
    start = max(0, match_start - _SNIPPET_RADIUS)
    end = min(len(text), match_start + match_len + _SNIPPET_RADIUS)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix
