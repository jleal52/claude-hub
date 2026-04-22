"""Windows Scheduled Task ServiceManager backend.

Uses the `schtasks` CLI to register a user task that runs at logon. Does NOT
require Administrator privileges on any Windows version:

- Simple flag-based `schtasks /Create /SC ONLOGON` is rejected with
  "Access denied" on Windows 11 22H2+ with Credential Guard / stricter
  Task Scheduler ACLs, because without an explicit XML template the default
  LogonType is Password, which requires the service account credentials.
- Using an XML template that specifies `LogonType=InteractiveToken` makes
  the task run under the current interactive session token and bypasses
  that requirement.

Other operations (query / run / end / delete) accept the simple `/TN \\name`
form without trouble.
"""
from __future__ import annotations

import getpass
import os
import platform
import subprocess
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

from .base import ServiceManager, ServiceSpec, ServiceStatus


def _task_name(name: str) -> str:
    """Return the absolute Task Scheduler path for a task at the root."""
    return f"\\{name}"


def _full_user_id() -> str:
    """Return `DOMAIN\\user` for the current interactive user."""
    domain = os.environ.get("USERDOMAIN") or platform.node()
    user = os.environ.get("USERNAME") or getpass.getuser()
    return f"{domain}\\{user}"


def _xml_template(spec: ServiceSpec) -> str:
    """Build the Task Scheduler XML that schtasks will import."""
    user = _full_user_id()
    command = escape(spec.command[0])
    # <Arguments> takes a single string; quote arguments containing spaces.
    args = " ".join(
        f'"{a}"' if (" " in a or not a) else a for a in spec.command[1:]
    )
    arguments_xml = f"<Arguments>{escape(args)}</Arguments>" if args else ""
    working_dir_xml = (
        f"<WorkingDirectory>{escape(spec.cwd)}</WorkingDirectory>" if spec.cwd else ""
    )
    description = escape(spec.description or spec.name)
    user_xml = escape(user)

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{description}</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>{user_xml}</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>{user_xml}</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>true</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{command}</Command>
      {arguments_xml}
      {working_dir_xml}
    </Exec>
  </Actions>
</Task>
"""


class ScheduledTaskManager(ServiceManager):
    def install(self, spec: ServiceSpec) -> None:
        xml = _xml_template(spec)
        # Task Scheduler requires UTF-16 LE with BOM.
        tmp = tempfile.NamedTemporaryFile(
            mode="wb", suffix=".xml", delete=False,
        )
        try:
            tmp.write(xml.encode("utf-16"))  # includes BOM
            tmp.flush()
            tmp.close()
            result = subprocess.run(
                ["schtasks", "/Create", "/F", "/TN", _task_name(spec.name), "/XML", tmp.name],
                check=False, capture_output=True, text=True,
            )
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            msg = stderr or stdout or "no output"
            raise RuntimeError(
                f"schtasks /Create /XML failed for {spec.name} "
                f"(exit {result.returncode}): {msg}"
            )

    def uninstall(self, name: str) -> None:
        subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", _task_name(name)],
            check=False, capture_output=True,
        )

    def start(self, name: str) -> None:
        subprocess.run(
            ["schtasks", "/Run", "/TN", _task_name(name)],
            check=False, capture_output=True,
        )

    def stop(self, name: str) -> None:
        subprocess.run(
            ["schtasks", "/End", "/TN", _task_name(name)],
            check=False, capture_output=True,
        )

    def restart(self, name: str) -> None:
        self.stop(name)
        self.start(name)

    def status(self, name: str) -> ServiceStatus:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", _task_name(name), "/FO", "LIST"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0:
            return ServiceStatus(name=name, installed=False, running=False,
                                 auto_start=False, pid=None)
        running = "Running" in result.stdout
        return ServiceStatus(name=name, installed=True, running=running,
                             auto_start=True, pid=None)

    def list_logs(self, name: str) -> list[Path]:
        return []
