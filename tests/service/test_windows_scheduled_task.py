from unittest.mock import MagicMock, patch

import pytest

from claude_hub.service.base import ServiceSpec
from claude_hub.service.windows_scheduled_task import (
    ScheduledTaskManager, _task_name,
)


def _spec(name="claude-hub"):
    return ServiceSpec(
        name=name,
        command=[r"C:\Users\u\.local\bin\claude.exe", "remote-control", "--name", "x"],
        cwd=r"C:\Users\u",
        env={},
        auto_start=True,
    )


def test_task_name_uses_root_path():
    """Regression: creating tasks under a custom folder (\\claude-hub\\...)
    fails with 'Acceso denegado' / 'Access denied' on many Windows installs
    unless elevated. The flat \\<name> layout works without admin."""
    assert _task_name("claude-hub") == r"\claude-hub"
    assert _task_name("claude-hub-wsl-debian") == r"\claude-hub-wsl-debian"


def test_install_uses_xml_template():
    """Regression: flag-only `schtasks /Create /SC ONLOGON` returns 'Acceso
    denegado' on Windows 11 22H2+ when not elevated. Using an XML template
    with LogonType=InteractiveToken bypasses the restriction."""
    fake_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with patch("claude_hub.service.windows_scheduled_task.subprocess.run", fake_run):
        ScheduledTaskManager().install(_spec("claude-hub"))
    commands = [call.args[0] for call in fake_run.call_args_list]
    create_call = next(c for c in commands if c[0] == "schtasks" and "/Create" in c)
    assert "/XML" in create_call
    assert "/TN" in create_call
    # /SC ONLOGON is NOT passed when /XML is used.
    assert "/SC" not in create_call


def test_install_xml_has_interactive_token_logon():
    """The generated XML must specify LogonType=InteractiveToken."""
    from claude_hub.service.windows_scheduled_task import _xml_template
    xml = _xml_template(_spec("claude-hub"))
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    assert "<LogonTrigger>" in xml


def test_install_raises_on_failure():
    """Regression: earlier versions silently ignored schtasks failures, so the
    installer printed [OK] even when the task wasn't created."""
    fake_run = MagicMock(return_value=MagicMock(
        returncode=1,
        stdout="ERROR: Access is denied.\n",
        stderr="",
    ))
    with patch("claude_hub.service.windows_scheduled_task.subprocess.run", fake_run):
        with pytest.raises(RuntimeError, match="schtasks /Create /XML failed"):
            ScheduledTaskManager().install(_spec())


def test_uninstall_calls_schtasks_delete():
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.windows_scheduled_task.subprocess.run", fake_run):
        ScheduledTaskManager().uninstall("claude-hub")
    commands = [call.args[0] for call in fake_run.call_args_list]
    delete_call = next(c for c in commands if c[0] == "schtasks" and "/Delete" in c)
    assert "/TN" in delete_call
    assert "/F" in delete_call
