import json
from pathlib import Path
from claude_hub.mcp.state import SpawnEntry, load, save


def _entry(name="alpha", path="/p", pid=111, env_url="https://x", started="2026-01-01T00:00:00"):
    return SpawnEntry(name=name, path=path, pid=pid, env_url=env_url, started_at=started)


def test_load_returns_empty_when_file_missing(tmp_state_dir: Path):
    assert load(tmp_state_dir) == []


def test_save_then_load_roundtrip(tmp_state_dir: Path):
    entries = [_entry("a"), _entry("b", pid=222)]
    save(tmp_state_dir, entries)
    loaded = load(tmp_state_dir)
    assert loaded == entries


def test_load_returns_empty_on_invalid_json(tmp_state_dir: Path):
    (tmp_state_dir / "spawns.json").write_text("not json{", encoding="utf-8")
    assert load(tmp_state_dir) == []


def test_load_returns_empty_on_missing_required_field(tmp_state_dir: Path):
    (tmp_state_dir / "spawns.json").write_text(
        json.dumps([{"name": "x", "path": "/p"}]), encoding="utf-8"
    )
    assert load(tmp_state_dir) == []


def test_save_is_atomic_tmp_file_does_not_corrupt_previous(tmp_state_dir: Path):
    save(tmp_state_dir, [_entry("first")])
    # Simulate crash between writing .tmp and the rename
    (tmp_state_dir / "spawns.json.tmp").write_text("partial garbage", encoding="utf-8")
    # Load must still return the previous valid state
    assert load(tmp_state_dir) == [_entry("first")]


def test_save_creates_parent_directory_if_missing(tmp_path: Path):
    nested = tmp_path / "nested" / "dir"
    save(nested, [_entry("x")])
    assert load(nested) == [_entry("x")]


def test_save_with_empty_list_writes_empty_array(tmp_state_dir: Path):
    save(tmp_state_dir, [])
    assert (tmp_state_dir / "spawns.json").read_text(encoding="utf-8").strip().startswith("[")
    assert load(tmp_state_dir) == []


def test_spawn_entry_env_url_can_be_none(tmp_state_dir: Path):
    save(tmp_state_dir, [_entry("x", env_url=None)])
    loaded = load(tmp_state_dir)
    assert loaded[0].env_url is None
