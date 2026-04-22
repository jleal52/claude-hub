"""Unit tests for cli/install.py deterministic helpers."""
from unittest.mock import MagicMock, patch

from claude_hub.cli.install import (
    MCP_SERVER_NAME,
    _install_mcp_inside_wsl,
    _register_mcp,
)


def _fake_run_success():
    return MagicMock(returncode=0, stdout="", stderr="")


def _fake_run_failure(exit_code=1, stderr="error: unknown option '-m'"):
    return MagicMock(returncode=exit_code, stdout="", stderr=stderr)


def test_register_mcp_passes_double_dash_before_python_args():
    """Regression: `claude mcp add` misinterprets `-m` as its own option
    unless `--` separates the command-path from its arguments."""
    fake_run = MagicMock(side_effect=[_fake_run_success(), _fake_run_success()])
    with patch("claude_hub.cli.install.subprocess.run", fake_run):
        ok = _register_mcp("/usr/bin/claude")
    assert ok is True
    # Second call is `claude mcp add ...`; inspect the argv.
    add_call = fake_run.call_args_list[1].args[0]
    assert add_call[0] == "/usr/bin/claude"
    assert add_call[1:6] == ["mcp", "add", "-s", "user", MCP_SERVER_NAME]
    # Then: -- <python-path> -m claude_hub.mcp
    sep_idx = add_call.index("--")
    assert "python" in add_call[sep_idx + 1].lower()
    assert add_call[sep_idx + 2:] == ["-m", "claude_hub.mcp"]


def test_register_mcp_returns_false_on_failure():
    """When `claude mcp add` fails, the helper reports False so the caller
    can print [FAIL] instead of misleading [OK]."""
    fake_run = MagicMock(side_effect=[_fake_run_success(), _fake_run_failure()])
    with patch("claude_hub.cli.install.subprocess.run", fake_run):
        ok = _register_mcp("/usr/bin/claude")
    assert ok is False


def test_register_mcp_first_removes_prior_registration():
    """The helper is idempotent: any prior registration is removed first."""
    fake_run = MagicMock(side_effect=[_fake_run_success(), _fake_run_success()])
    with patch("claude_hub.cli.install.subprocess.run", fake_run):
        _register_mcp("/usr/bin/claude")
    first_call = fake_run.call_args_list[0].args[0]
    assert first_call[1:6] == ["mcp", "remove", MCP_SERVER_NAME, "-s", "user"]


def _wsl_fake(stdout: str = "OK", returncode: int = 0):
    return MagicMock(returncode=returncode, stdout=stdout, stderr="")


def test_install_mcp_inside_wsl_happy_path():
    """When pipx is already present, only 2 invocations: install + register."""
    fake_run = MagicMock(side_effect=[
        _wsl_fake("OK\n"),           # probe: pipx exists
        _wsl_fake(),                 # pipx install
        _wsl_fake(),                 # claude-hub install --mcp-only
    ])
    with patch("claude_hub.cli.install.subprocess.run", fake_run):
        ok = _install_mcp_inside_wsl("Debian")
    assert ok is True
    # Each call should be `wsl.exe -d Debian -- bash -lc <script>`
    for call in fake_run.call_args_list:
        argv = call.args[0]
        assert argv[0] == "wsl.exe"
        assert argv[1:4] == ["-d", "Debian", "--"]
        assert argv[4:6] == ["bash", "-lc"]


def test_install_mcp_inside_wsl_installs_pipx_if_missing():
    """Missing pipx triggers a 4-step sequence: probe, install pipx, install pkg, register."""
    fake_run = MagicMock(side_effect=[
        _wsl_fake("MISSING\n"),      # probe: pipx absent
        _wsl_fake(),                 # pip install --user pipx
        _wsl_fake(),                 # pipx install
        _wsl_fake(),                 # claude-hub install --mcp-only
    ])
    with patch("claude_hub.cli.install.subprocess.run", fake_run):
        ok = _install_mcp_inside_wsl("Ubuntu")
    assert ok is True
    # The pip install step should be present in the script
    second_script = fake_run.call_args_list[1].args[0][-1]
    assert "pipx" in second_script
    assert "pip install" in second_script


def test_install_mcp_inside_wsl_returns_false_on_any_failure():
    """If the final register step fails, the helper returns False so the
    caller prints a [WARN] with manual instructions."""
    fake_run = MagicMock(side_effect=[
        _wsl_fake("OK\n"),           # probe
        _wsl_fake(),                 # pipx install OK
        _wsl_fake(returncode=1),     # register FAILED
    ])
    with patch("claude_hub.cli.install.subprocess.run", fake_run):
        ok = _install_mcp_inside_wsl("Debian")
    assert ok is False
