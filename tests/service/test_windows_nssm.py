from unittest.mock import MagicMock, patch

import pytest

from claude_hub.service.base import ServiceSpec
from claude_hub.service.windows_nssm import NssmManager


def _spec(name="claude-hub"):
    return ServiceSpec(
        name=name,
        command=[r"C:\Users\u\.local\bin\claude.exe", "remote-control", "--name", "x"],
        cwd=r"C:\Users\u",
        env={},
        auto_start=True,
    )


def test_install_issues_nssm_install_and_set_sequence():
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.windows_nssm.subprocess.run", fake_run):
        NssmManager().install(_spec("claude-hub"))
    commands = [call.args[0] for call in fake_run.call_args_list]
    install_call = next(c for c in commands if c[0] == "nssm" and c[1] == "install")
    assert install_call[2] == "claude-hub"
    set_keys = [c[3] for c in commands if c[:3] == ["nssm", "set", "claude-hub"]]
    assert "AppParameters" in set_keys
    assert "AppDirectory" in set_keys
    assert "Start" in set_keys


def test_uninstall_stops_and_removes():
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.windows_nssm.subprocess.run", fake_run):
        NssmManager().uninstall("claude-hub")
    commands = [call.args[0] for call in fake_run.call_args_list]
    assert any(c[:3] == ["nssm", "stop", "claude-hub"] for c in commands)
    assert any(c[:3] == ["nssm", "remove", "claude-hub"] for c in commands)
