from pathlib import Path
from unittest.mock import MagicMock, patch
import plistlib

from claude_hub.service.base import ServiceSpec
from claude_hub.service.macos_launchd import LaunchdManager, _label


def _spec(name="claude-hub"):
    return ServiceSpec(
        name=name,
        command=["/Users/u/.local/bin/claude", "remote-control", "--name", "x"],
        cwd="/Users/u",
        env={},
        auto_start=True,
        stdout_log=Path("/tmp/out.log"),
        stderr_log=Path("/tmp/err.log"),
    )


def test_label_namespace():
    assert _label("claude-hub") == "com.github.jleal52.claude-hub"


def test_install_writes_plist_and_loads(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "claude_hub.service.macos_launchd._agents_dir",
        lambda: tmp_path,
    )
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.macos_launchd.subprocess.run", fake_run):
        LaunchdManager().install(_spec("claude-hub"))
    plist_path = tmp_path / "com.github.jleal52.claude-hub.plist"
    assert plist_path.exists()
    with open(plist_path, "rb") as f:
        data = plistlib.load(f)
    assert data["Label"] == "com.github.jleal52.claude-hub"
    assert data["ProgramArguments"][0].endswith("claude")
    assert data["RunAtLoad"] is True
    assert data["KeepAlive"] is True
    commands = [call.args[0] for call in fake_run.call_args_list]
    assert ["launchctl", "load", "-w", str(plist_path)] in commands


def test_uninstall_removes_plist_and_unloads(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "claude_hub.service.macos_launchd._agents_dir",
        lambda: tmp_path,
    )
    plist_path = tmp_path / "com.github.jleal52.claude-hub.plist"
    plist_path.write_text("dummy")
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.macos_launchd.subprocess.run", fake_run):
        LaunchdManager().uninstall("claude-hub")
    assert not plist_path.exists()
