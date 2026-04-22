# tests/platform/test_detect.py
import sys
from unittest.mock import patch

from claude_hub.platform import detect


def test_current_os_linux():
    with patch("sys.platform", "linux"):
        assert detect.current_os() == "linux"


def test_current_os_macos():
    with patch("sys.platform", "darwin"):
        assert detect.current_os() == "macos"


def test_current_os_windows():
    with patch("sys.platform", "win32"):
        assert detect.current_os() == "windows"


def test_find_claude_binary_via_which():
    with patch("shutil.which", return_value="/usr/local/bin/claude"):
        assert detect.find_claude_binary() == "/usr/local/bin/claude"


def test_find_claude_binary_returns_none_when_missing():
    with patch("shutil.which", return_value=None):
        assert detect.find_claude_binary() is None


def test_list_wsl_distros_non_windows():
    with patch("sys.platform", "linux"):
        assert detect.list_wsl_distros() == []


def test_default_session_name_uses_hostname():
    with patch("socket.gethostname", return_value="my-laptop"):
        assert detect.default_session_name() == "my-laptop"
