from datetime import datetime
from pathlib import Path
from claude_hub.mcp.projects import ProjectInfo, list_projects


def test_empty_projects_dir(tmp_claude_home: Path):
    assert list_projects(claude_home=tmp_claude_home) == []


def test_missing_projects_dir(tmp_path: Path):
    # claude_home exists but has no `projects/` subdir
    home = tmp_path / ".claude"
    home.mkdir()
    assert list_projects(claude_home=home) == []


def test_single_project_reads_cwd(tmp_claude_home: Path, make_jsonl):
    make_jsonl("-home-u-foo", cwd="/home/u/foo", lines=[{"role": "user", "content": "hi"}])
    result = list_projects(claude_home=tmp_claude_home)
    assert len(result) == 1
    assert result[0].path == "/home/u/foo"
    assert result[0].n_sessions == 1


def test_sorted_by_last_modified_desc(tmp_claude_home: Path, make_jsonl):
    make_jsonl("-a", cwd="/a", lines=[{"x": 1}], mtime=1000)
    make_jsonl("-b", cwd="/b", lines=[{"x": 1}], mtime=3000)
    make_jsonl("-c", cwd="/c", lines=[{"x": 1}], mtime=2000)
    result = list_projects(claude_home=tmp_claude_home)
    assert [p.path for p in result] == ["/b", "/c", "/a"]


def test_respects_limit(tmp_claude_home: Path, make_jsonl):
    for i in range(5):
        make_jsonl(f"-p{i}", cwd=f"/p{i}", lines=[{"x": 1}], mtime=1000 + i)
    result = list_projects(limit=3, claude_home=tmp_claude_home)
    assert len(result) == 3


def test_cwd_falls_through_first_non_cwd_line(tmp_claude_home: Path, make_jsonl):
    # First line is permission-mode (no cwd); second line is a message with cwd.
    make_jsonl(
        "-dir",
        cwd=None,
        lines=[
            {"type": "permission-mode", "permissionMode": "auto", "sessionId": "abc"},
            {"role": "user", "content": "hello", "cwd": "/the/real/path"},
        ],
    )
    result = list_projects(claude_home=tmp_claude_home)
    assert result[0].path == "/the/real/path"


def test_n_sessions_counts_all_jsonls(tmp_claude_home: Path, make_jsonl):
    make_jsonl("-multi", cwd="/multi", lines=[{"x": 1}])
    make_jsonl("-multi", cwd="/multi", lines=[{"x": 2}])
    make_jsonl("-multi", cwd="/multi", lines=[{"x": 3}])
    result = list_projects(claude_home=tmp_claude_home)
    assert len(result) == 1
    assert result[0].n_sessions == 3


def test_empty_project_dir_is_skipped(tmp_claude_home: Path):
    # a project dir exists but has no .jsonl inside
    empty = tmp_claude_home / "projects" / "-ghost"
    empty.mkdir()
    assert list_projects(claude_home=tmp_claude_home) == []


def test_cwd_fallback_to_name_parsing_when_no_cwd_anywhere(tmp_claude_home: Path, make_jsonl):
    # All lines lack cwd. Best-effort: parse project dirname.
    make_jsonl(
        "-home-u-noswd",
        cwd=None,
        lines=[{"type": "permission-mode"}],
    )
    result = list_projects(claude_home=tmp_claude_home)
    assert len(result) == 1
    # Fallback is /home/u/noswd (leading dash becomes /, remaining dashes become /)
    assert result[0].path == "/home/u/noswd"


def test_project_info_dataclass_fields(tmp_claude_home: Path, make_jsonl):
    make_jsonl("-x", cwd="/x", lines=[{"x": 1}], mtime=1000)
    result = list_projects(claude_home=tmp_claude_home)
    p = result[0]
    assert isinstance(p, ProjectInfo)
    assert isinstance(p.last_modified, datetime)
    assert p.path == "/x"
    assert p.n_sessions == 1
