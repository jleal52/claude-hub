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


def test_install_raises_on_nssm_install_failure():
    """Regression: earlier versions silently ignored nssm errors. If the `install`
    step fails (e.g. not elevated, name conflict) the caller must know."""
    # stop + remove succeed (no-op on a clean system), then install fails.
    fake_run = MagicMock(side_effect=[
        MagicMock(returncode=0, stdout="", stderr=""),  # stop
        MagicMock(returncode=0, stdout="", stderr=""),  # remove
        MagicMock(returncode=5, stdout="", stderr="Access is denied."),  # install
    ])
    with patch("claude_hub.service.windows_nssm.subprocess.run", fake_run):
        with pytest.raises(RuntimeError, match="nssm install failed"):
            NssmManager().install(_spec())


def test_uninstall_stops_and_removes():
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.service.windows_nssm.subprocess.run", fake_run):
        NssmManager().uninstall("claude-hub")
    commands = [call.args[0] for call in fake_run.call_args_list]
    assert any(c[:3] == ["nssm", "stop", "claude-hub"] for c in commands)
    assert any(c[:3] == ["nssm", "remove", "claude-hub"] for c in commands)


def test_install_rejects_wsl_command():
    """Regression: NSSM runs services under LocalSystem, and wsl.exe refuses
    to launch under LocalSystem (WSL_E_LOCAL_SYSTEM_NOT_SUPPORTED). Previous
    versions registered a broken service that would always fail at start.
    The installer must refuse up-front with a clear message pointing to the
    Scheduled Task backend."""
    wsl_spec = ServiceSpec(
        name="claude-hub-wsl-debian",
        command=[r"C:\Windows\System32\wsl.exe", "-d", "Debian", "--", "bash", "-lc", "claude"],
        cwd=r"C:\Users\u",
        env={},
        auto_start=True,
    )
    with pytest.raises(RuntimeError, match="wsl.exe cannot run as LocalSystem"):
        NssmManager().install(wsl_spec)


def test_install_raises_when_nssm_set_fails():
    """Regression (0.1.11 bug): `nssm install` succeeded via a one-time UAC
    prompt but the subsequent `nssm set AppParameters` calls failed silently
    (Access denied), leaving a registered service with empty AppParameters
    that would never actually start `claude remote-control`. Validate every
    `nssm set` and roll back the install on failure."""
    # stop + remove no-op, install ok, first `nssm set AppParameters` fails.
    fake_run = MagicMock(side_effect=[
        MagicMock(returncode=0, stdout="", stderr=""),  # stop
        MagicMock(returncode=0, stdout="", stderr=""),  # remove
        MagicMock(returncode=0, stdout="", stderr=""),  # install
        MagicMock(returncode=5, stdout="", stderr="Access is denied."),  # set AppParameters
        MagicMock(returncode=0, stdout="", stderr=""),  # rollback `nssm remove`
    ])
    with patch("claude_hub.service.windows_nssm.subprocess.run", fake_run):
        with pytest.raises(RuntimeError, match="nssm set AppParameters failed"):
            NssmManager().install(_spec())
    commands = [call.args[0] for call in fake_run.call_args_list]
    # Rollback happened: `nssm remove ... confirm` after the failed set.
    removes = [c for c in commands if c[:2] == ["nssm", "remove"]]
    assert len(removes) == 2  # one before install, one as rollback
