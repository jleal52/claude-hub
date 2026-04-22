from claude_hub.service.base import ServiceSpec
from claude_hub.service.wsl_wrapper import wrap_for_wsl


def test_wrap_composes_wsl_exe_with_distro():
    inner = ServiceSpec(
        name="wsl-Debian",
        command=["claude", "remote-control", "--name", "WSL-Debian"],
        cwd="~",
        env={},
    )
    wrapped = wrap_for_wsl(inner, distro="Debian", wsl_cwd="/home/u")
    assert wrapped.command[0].endswith("wsl.exe")
    assert "-d" in wrapped.command and "Debian" in wrapped.command


def test_wrap_uses_bash_lc_for_login_shell():
    """Regression: wsl.exe -d <distro> -- <cmd> does NOT source ~/.profile,
    so `claude` from ~/.local/bin is not on PATH → task exits 127. We wrap
    the command with bash -lc so login shell PATH is sourced."""
    inner = ServiceSpec(
        name="wsl-Debian",
        command=["claude", "remote-control", "--name", "WSL-Debian"],
        cwd="~",
        env={},
    )
    wrapped = wrap_for_wsl(inner, distro="Debian", wsl_cwd="/home/u")
    dash_idx = wrapped.command.index("--")
    tail = wrapped.command[dash_idx + 1:]
    assert tail[0] == "bash"
    assert tail[1] == "-lc"
    # The final string must quote the inner command and redirect stdin to /dev/null
    assert "claude" in tail[2]
    assert "remote-control" in tail[2]
    assert "< /dev/null" in tail[2]


def test_wrap_preserves_name_and_adds_cd_flag():
    inner = ServiceSpec(
        name="wsl-Ubuntu",
        command=["echo", "hi"],
        cwd="/home/u",
        env={},
    )
    wrapped = wrap_for_wsl(inner, distro="Ubuntu", wsl_cwd="/home/u/proj")
    assert wrapped.name == "wsl-Ubuntu"
    assert "--cd" in wrapped.command
    cd_idx = wrapped.command.index("--cd")
    assert wrapped.command[cd_idx + 1] == "/home/u/proj"
