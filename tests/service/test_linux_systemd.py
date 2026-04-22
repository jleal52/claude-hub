from unittest.mock import MagicMock, patch

from claude_hub.service.base import ServiceSpec
from claude_hub.service.linux_systemd import SystemdUserManager, _unit_file_text


def _spec(name="claude-hub"):
    return ServiceSpec(
        name=name,
        command=["/home/u/.local/bin/claude", "remote-control", "--name", "x"],
        cwd="/home/u",
        env={"FOO": "bar"},
        auto_start=True,
        description="test service",
    )


def test_unit_file_text_contains_exec_start():
    text = _unit_file_text(_spec())
    assert "[Service]" in text
    assert 'ExecStart=/home/u/.local/bin/claude "remote-control" "--name" "x"' in text
    assert 'WorkingDirectory=/home/u' in text
    assert 'Environment="FOO=bar"' in text
    assert "[Install]" in text
    assert "WantedBy=default.target" in text


def test_install_writes_unit_and_enables(tmp_path, monkeypatch):
    unit_dir = tmp_path / "systemd-user"
    unit_dir.mkdir()
    monkeypatch.setattr(
        "claude_hub.service.linux_systemd._unit_dir",
        lambda: unit_dir,
    )
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.linux_systemd.subprocess.run", fake_run):
        SystemdUserManager().install(_spec("claude-hub"))

    unit = unit_dir / "claude-hub.service"
    assert unit.exists()
    assert "ExecStart=" in unit.read_text()
    commands_called = [call.args[0] for call in fake_run.call_args_list]
    assert ["systemctl", "--user", "daemon-reload"] in commands_called
    assert ["systemctl", "--user", "enable", "--now", "claude-hub"] in commands_called


def test_uninstall_stops_and_removes_unit(tmp_path, monkeypatch):
    unit_dir = tmp_path / "systemd-user"
    unit_dir.mkdir()
    (unit_dir / "claude-hub.service").write_text("dummy")
    monkeypatch.setattr(
        "claude_hub.service.linux_systemd._unit_dir",
        lambda: unit_dir,
    )
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.linux_systemd.subprocess.run", fake_run):
        SystemdUserManager().uninstall("claude-hub")

    assert not (unit_dir / "claude-hub.service").exists()
    commands_called = [call.args[0] for call in fake_run.call_args_list]
    assert ["systemctl", "--user", "disable", "--now", "claude-hub"] in commands_called
