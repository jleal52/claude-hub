"""Shared pytest fixtures."""
import json
import os
from pathlib import Path
import pytest


@pytest.fixture
def tmp_state_dir(tmp_path: Path) -> Path:
    """Empty directory simulating ~/.claude-hub/."""
    d = tmp_path / "claude-hub"
    d.mkdir()
    return d


@pytest.fixture
def tmp_claude_home(tmp_path: Path) -> Path:
    """Empty directory simulating ~/.claude/ (no projects yet)."""
    d = tmp_path / ".claude"
    (d / "projects").mkdir(parents=True)
    return d


@pytest.fixture
def make_jsonl(tmp_claude_home: Path):
    """Factory: creates a project directory with a jsonl session file.

    Returns a callable(project_dirname, cwd, lines=[...], mtime=None) -> Path
    where `lines` is a list of dicts (each becomes a jsonl line), `cwd` is
    what the tool should report (usually embedded in one of the lines), and
    `mtime` optionally stamps the .jsonl's mtime.
    """
    counter = {"n": 0}

    def _make(project_dirname: str, cwd: str | None, lines: list[dict], mtime: float | None = None) -> Path:
        proj = tmp_claude_home / "projects" / project_dirname
        proj.mkdir(parents=True, exist_ok=True)
        counter["n"] += 1
        session_file = proj / f"session-{counter['n']}.jsonl"
        payload_lines = []
        for ln in lines:
            copy = dict(ln)
            if cwd is not None and "cwd" not in copy:
                copy["cwd"] = cwd
            payload_lines.append(json.dumps(copy))
        session_file.write_text("\n".join(payload_lines) + "\n", encoding="utf-8")
        if mtime is not None:
            os.utime(session_file, (mtime, mtime))
        return session_file

    return _make
