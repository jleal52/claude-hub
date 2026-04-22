from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from claude_hub.service.base import ServiceSpec
from claude_hub.service.windows_scheduled_task import (
    ScheduledTaskManager,
    _shim_path,
    _task_name,
    _vbs_launcher_path,
    _write_shim,
    _write_vbs_launcher,
    _xml_template,
)


def _spec(name="claude-hub"):
    return ServiceSpec(
        name=name,
        command=[r"C:\Users\u\.local\bin\claude.exe", "remote-control", "--name", "x", "--spawn", "same-dir"],
        cwd=r"C:\Users\u",
        env={},
        auto_start=True,
        stdout_log=Path(r"C:\Users\u\.claude-hub\logs\claude-hub.out.log"),
        stderr_log=Path(r"C:\Users\u\.claude-hub\logs\claude-hub.err.log"),
    )


def test_task_name_uses_root_path():
    """Regression: tasks under a custom \\claude-hub\\ folder require
    elevated privileges on Windows 11. Registering at the root avoids that."""
    assert _task_name("claude-hub") == r"\claude-hub"
    assert _task_name("claude-hub-wsl-debian") == r"\claude-hub-wsl-debian"


def test_install_uses_xml_template(monkeypatch, tmp_path):
    """Flag-only `schtasks /Create /SC ONLOGON` returns 'Acceso denegado' on
    Windows 11 22H2+ without admin. XML with LogonType=InteractiveToken works."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    fake_run = MagicMock(return_value=MagicMock(returncode=0, stdout="", stderr=""))
    with patch("claude_hub.service.windows_scheduled_task.subprocess.run", fake_run):
        ScheduledTaskManager().install(_spec("claude-hub"))
    commands = [call.args[0] for call in fake_run.call_args_list]
    create_call = next(c for c in commands if c[0] == "schtasks" and "/Create" in c)
    assert "/XML" in create_call
    assert "/TN" in create_call
    assert "/SC" not in create_call


def test_shim_has_stdin_nul_and_log_redirects(monkeypatch, tmp_path):
    """The .cmd shim must redirect stdin from NUL (so claude remote-control
    doesn't detect --print mode) and route stdout/stderr to the log files."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    spec = _spec("claude-hub")
    shim = _write_shim(spec)
    assert shim.exists()
    content = shim.read_text(encoding="ascii")
    assert "< NUL" in content
    assert str(spec.command[0]) in content
    assert "remote-control" in content
    assert str(spec.stdout_log) in content
    assert str(spec.stderr_log) in content


def test_vbs_launcher_uses_swhide(monkeypatch, tmp_path):
    """The .vbs launcher must run the shim with SW_HIDE so no console window
    flashes. That means WshShell.Run's second argument is 0."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    shim = tmp_path / "task-claude-hub.cmd"
    shim.write_text("dummy", encoding="ascii")
    vbs = _write_vbs_launcher("claude-hub", shim)
    assert vbs.exists()
    content = vbs.read_text(encoding="ascii")
    assert "WshShell.Run" in content
    # The critical bit: second argument to Run must be 0 (SW_HIDE).
    # Third arg should be False so VBS returns immediately without waiting.
    assert ", 0, False" in content
    assert str(shim) in content


def test_xml_invokes_wscript_with_vbs_not_cmd_directly(monkeypatch, tmp_path):
    """Regression: before the .vbs indirection the XML action pointed at the
    .cmd directly, which made Task Scheduler flash a console window at logon.
    Now the action is `wscript.exe <vbs-launcher>` and the .vbs hides the window."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    spec = _spec("claude-hub")
    vbs = _vbs_launcher_path("claude-hub")
    xml = _xml_template(spec, vbs)
    assert "<Command>wscript.exe</Command>" in xml
    assert str(vbs) in xml
    # The .cmd shim path and claude.exe must NOT appear in the XML; they live
    # inside the chain .vbs → .cmd which is resolved at runtime.
    assert ".cmd" not in xml
    assert spec.command[0] not in xml


def test_xml_has_interactive_token_logon(monkeypatch, tmp_path):
    """The generated XML must specify LogonType=InteractiveToken."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    spec = _spec("claude-hub")
    vbs = _vbs_launcher_path("claude-hub")
    xml = _xml_template(spec, vbs)
    assert "<LogonType>InteractiveToken</LogonType>" in xml
    assert "<RunLevel>LeastPrivilege</RunLevel>" in xml
    assert "<LogonTrigger>" in xml


def test_install_raises_on_failure(monkeypatch, tmp_path):
    """Regression: earlier versions silently ignored schtasks failures, so the
    installer printed [OK] even when the task wasn't created."""
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    fake_run = MagicMock(return_value=MagicMock(
        returncode=1,
        stdout="ERROR: Access is denied.\n",
        stderr="",
    ))
    with patch("claude_hub.service.windows_scheduled_task.subprocess.run", fake_run):
        with pytest.raises(RuntimeError, match="schtasks /Create /XML failed"):
            ScheduledTaskManager().install(_spec())


def test_uninstall_removes_task_and_shim(monkeypatch, tmp_path):
    monkeypatch.setenv("CLAUDE_HUB_DIR", str(tmp_path))
    # Pre-create a shim to simulate a prior install
    shim = _shim_path("claude-hub")
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text("dummy", encoding="ascii")
    assert shim.exists()

    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.windows_scheduled_task.subprocess.run", fake_run):
        ScheduledTaskManager().uninstall("claude-hub")

    commands = [call.args[0] for call in fake_run.call_args_list]
    delete_call = next(c for c in commands if c[0] == "schtasks" and "/Delete" in c)
    assert "/TN" in delete_call
    assert "/F" in delete_call
    assert not shim.exists()
