"""Config file load/save (TOML)."""
from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

from .platform import paths

CURRENT_VERSION = 1


@dataclass
class HubConfig:
    session_name: str
    working_dir: str
    claude_bin: str


@dataclass
class WslEntry:
    distro: str
    session_name: str
    working_dir: str


@dataclass
class ServiceConfig:
    backend: Literal["auto", "systemd", "launchd", "scheduled-task", "nssm"] = "auto"


@dataclass
class Config:
    version: int
    hub: HubConfig
    wsl: list[WslEntry] = field(default_factory=list)
    service: ServiceConfig = field(default_factory=ServiceConfig)


def load() -> Optional[Config]:
    path = paths.config_path()
    if not path.exists():
        return None
    with open(path, "rb") as f:
        data = tomllib.load(f)
    return Config(
        version=int(data.get("version", CURRENT_VERSION)),
        hub=HubConfig(**data["hub"]),
        wsl=[WslEntry(**w) for w in data.get("wsl", [])],
        service=ServiceConfig(**data.get("service", {})),
    )


def _toml_str(v: str) -> str:
    """Serialize a value as a TOML literal string (single quotes, no escapes).

    Literal strings are preferred over basic strings because Windows paths like
    `C:\\Users\\foo` contain backslashes that TOML basic strings interpret as
    escape sequences (e.g. `\\U...` is a Unicode escape requiring 8 hex chars).
    Literal strings disallow single quotes in the value; we fall back to a
    basic string with escaped backslashes when that happens.
    """
    s = str(v)
    if "'" not in s:
        return f"'{s}'"
    # Rare fallback: escape backslashes + double quotes for basic string.
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save(cfg: Config) -> None:
    path = paths.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"version = {cfg.version}", ""]
    lines.append("[hub]")
    for k, v in asdict(cfg.hub).items():
        lines.append(f"{k} = {_toml_str(v)}")
    lines.append("")
    for w in cfg.wsl:
        lines.append("[[wsl]]")
        for k, v in asdict(w).items():
            lines.append(f"{k} = {_toml_str(v)}")
        lines.append("")
    lines.append("[service]")
    lines.append(f"backend = {_toml_str(cfg.service.backend)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
