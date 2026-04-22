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


def test_windows_paths_with_backslashes_roundtrip(tmp_path, monkeypatch):
    """Regression: Windows paths contain backslashes that TOML basic strings
    interpret as escape sequences (e.g. \\U starts a Unicode escape). Literal
    strings (single quotes) must be used when serializing values."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    cfg = Config(
        version=1,
        hub=HubConfig(
            session_name="MY-PC",
            working_dir=r"C:\Users\Usuario\Documents",
            claude_bin=r"C:\Users\Usuario\.local\bin\claude.exe",
        ),
        wsl=[WslEntry(distro="Debian", session_name="WSL-Debian",
                      working_dir="/home/u")],
        service=ServiceConfig(backend="auto"),
    )
    save(cfg)
    loaded = load()
    assert loaded == cfg
    assert loaded.hub.working_dir == r"C:\Users\Usuario\Documents"
    assert loaded.hub.claude_bin == r"C:\Users\Usuario\.local\bin\claude.exe"
