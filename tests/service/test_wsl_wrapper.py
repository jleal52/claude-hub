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
    dash_idx = wrapped.command.index("--")
    assert wrapped.command[dash_idx + 1:] == ["claude", "remote-control", "--name", "WSL-Debian"]


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
