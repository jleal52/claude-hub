from pathlib import Path
import pytest
from claude_hub.mcp.spawner import (
    derive_name_from_path,
    resolve_name_collision,
    extract_env_url,
    SpawnEntry,
)


def test_derive_name_uses_basename():
    assert derive_name_from_path("/home/u/foo") == "foo"


def test_derive_name_strips_trailing_slash():
    assert derive_name_from_path("/home/u/foo/") == "foo"


def test_derive_name_on_root_returns_root():
    # Unusual but the function should be total. Empty string fallback.
    assert derive_name_from_path("/") == "root"


def test_resolve_name_collision_returns_input_when_free():
    existing = {"other"}
    assert resolve_name_collision("foo", existing) == "foo"


def test_resolve_name_collision_adds_suffix_when_taken():
    existing = {"foo"}
    assert resolve_name_collision("foo", existing) == "foo-2"


def test_resolve_name_collision_increments_until_free():
    existing = {"foo", "foo-2", "foo-3"}
    assert resolve_name_collision("foo", existing) == "foo-4"


def test_extract_env_url_finds_in_log_line():
    line = "Continue coding in the Claude app or https://claude.ai/code?environment=env_01ABCdef"
    assert extract_env_url(line) == "https://claude.ai/code?environment=env_01ABCdef"


def test_extract_env_url_returns_none_if_absent():
    assert extract_env_url("no url here") is None


def test_extract_env_url_finds_in_multiline_block():
    block = "line1\nsome noise\n... https://claude.ai/code?environment=env_ZZZ9 ...\nmore"
    assert extract_env_url(block) == "https://claude.ai/code?environment=env_ZZZ9"


import sys
from unittest.mock import patch, MagicMock


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only branch")
def test_kill_pid_on_windows_uses_taskkill(tmp_state_dir):
    from claude_hub.mcp.spawner import _kill_pid

    # First taskkill call returns 0 (graceful); process dies; no /F call needed.
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.mcp.spawner.subprocess.run", fake_run), \
         patch("claude_hub.mcp.spawner._pid_alive", side_effect=[True, False]):
        ok = _kill_pid(pid=99999, grace_seconds=0.1)
    assert ok is True
    # First call was a graceful taskkill (without /F)
    first_call_args = fake_run.call_args_list[0].args[0]
    assert first_call_args[0] == "taskkill"
    assert "/F" not in first_call_args


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only branch")
def test_kill_pid_windows_trusts_taskkill_exit_code_over_pid_alive(tmp_state_dir):
    """
    Regression: after `taskkill /F` succeeds, Windows may keep the process
    handle open briefly, making `os.kill(pid, 0)` lie. The exit code of
    taskkill should be the source of truth, not `_pid_alive`.
    """
    from claude_hub.mcp.spawner import _kill_pid

    # Graceful taskkill returns 0 but process stays "alive" (no window).
    # /T /F taskkill returns 0 (killed). `_pid_alive` lies and says True.
    fake_run = MagicMock(return_value=MagicMock(returncode=0))
    with patch("claude_hub.mcp.spawner.subprocess.run", fake_run), \
         patch("claude_hub.mcp.spawner._pid_alive", return_value=True):
        ok = _kill_pid(pid=99999, grace_seconds=0.1)
    # Even though _pid_alive kept returning True, returncode=0 on /T /F wins.
    assert ok is True
    # Second call was the force-kill with /T /F.
    second_call_args = fake_run.call_args_list[1].args[0]
    assert second_call_args[0] == "taskkill"
    assert "/T" in second_call_args
    assert "/F" in second_call_args


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-only branch")
def test_kill_pid_on_posix_uses_sigterm_then_sigkill(tmp_state_dir):
    import signal
    from claude_hub.mcp.spawner import _kill_pid

    calls = []

    def fake_kill(pid, sig):
        calls.append((pid, sig))
        if sig == 0:
            # Simulate alive for first N checks, then dead
            if len(calls) < 5:
                return None
            raise ProcessLookupError
        # SIGTERM / SIGKILL accepted silently
        return None

    with patch("claude_hub.mcp.spawner.os.kill", side_effect=fake_kill):
        _kill_pid(pid=99999, grace_seconds=0.3)

    sigs_sent = [sig for _, sig in calls if sig != 0]
    assert signal.SIGTERM in sigs_sent
    # SIGKILL may or may not be sent depending on how quickly we observed death;
    # the test just verifies SIGTERM was attempted.
