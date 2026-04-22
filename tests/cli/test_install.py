"""Unit tests for cli/install.py deterministic helpers."""
from unittest.mock import MagicMock, patch

from claude_hub.cli.install import MCP_SERVER_NAME, _register_mcp


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
