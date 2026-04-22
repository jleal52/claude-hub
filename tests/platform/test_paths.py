from pathlib import Path
from unittest.mock import patch

from claude_hub.platform import paths


def test_hub_dir_uses_home():
    expected = Path.home() / ".claude-hub"
    assert paths.hub_dir() == expected


def test_logs_dir_nested_inside_hub_dir():
    assert paths.logs_dir() == paths.hub_dir() / "logs"


def test_state_dir_nested_inside_hub_dir():
    assert paths.state_dir() == paths.hub_dir() / "state"


def test_config_path():
    assert paths.config_path() == paths.hub_dir() / "config.toml"


def test_hub_dir_override_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path / "override"))
    assert paths.hub_dir() == tmp_path / "override"
