# tests/test_config.py
from claude_hub.config import Config, HubConfig, WslEntry, ServiceConfig, load, save


def test_default_config_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    cfg = Config(
        version=1,
        hub=HubConfig(session_name="test", working_dir="/tmp", claude_bin="/usr/bin/claude"),
        wsl=[WslEntry(distro="Debian", session_name="WSL-Debian", working_dir="/home/u")],
        service=ServiceConfig(backend="auto"),
    )
    save(cfg)
    loaded = load()
    assert loaded == cfg


def test_load_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    assert load() is None


def test_wsl_list_may_be_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    cfg = Config(
        version=1,
        hub=HubConfig(session_name="x", working_dir="/", claude_bin="/a"),
        wsl=[],
        service=ServiceConfig(backend="auto"),
    )
    save(cfg)
    assert load().wsl == []
