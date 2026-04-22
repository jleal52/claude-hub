#Requires -Version 5.1
<#
.SYNOPSIS
  Bootstrap installer for claude-hub on Windows.
  Verifies Python 3.11+, installs pipx, installs claude-hub, prompts `claude-hub install`.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Get-PythonCommand {
    $candidates = @("py -3.11", "py -3.12", "py -3.13", "py -3", "python")
    foreach ($c in $candidates) {
        try {
            $parts = $c -split " "
            $output = & $parts[0] $parts[1..($parts.Length-1)] --version 2>&1
            if ($output -match "Python 3\.(1[1-9]|\d{2,})") {
                return $c
            }
        } catch {}
    }
    return $null
}

$python = Get-PythonCommand
if (-not $python) {
    Write-Error "Python 3.11+ not found. Install from python.org or 'winget install Python.Python.3.12'."
}
Write-Host "Using Python: $python"

$pipxCheck = Get-Command pipx -ErrorAction SilentlyContinue
if (-not $pipxCheck) {
    Write-Host "Installing pipx..."
    $pyParts = $python.Split()
    & $pyParts[0] $pyParts[1..($pyParts.Length-1)] -m pip install --user pipx
    & $pyParts[0] $pyParts[1..($pyParts.Length-1)] -m pipx ensurepath
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
}

Write-Host "Installing claude-hub..."
pipx install --force claude-code-hub

Write-Host ""
Write-Host "claude-hub installed. Run 'claude-hub install' to configure."
