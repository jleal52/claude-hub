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
    # Refresh PATH for the remainder of THIS session (pipx ensurepath only affects new shells).
    $scriptsDir = & $pyParts[0] $pyParts[1..($pyParts.Length-1)] -c "import sysconfig; print(sysconfig.get_path('scripts', f'{sysconfig.get_default_scheme()}_user'))"
    if ($scriptsDir -and (Test-Path $scriptsDir)) { $env:Path = "$scriptsDir;$env:Path" }
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path
}

# Install from PyPI. Falls back to GitHub main if PyPI doesn't have the release yet
# (useful when running this script from a branch ahead of the last tag).
Write-Host "Installing claude-hub from PyPI..."
$pypiFailed = $false
try {
    pipx install --force claude-code-hub 2>&1 | Tee-Object -Variable pypiOutput | Out-Host
    if ($LASTEXITCODE -ne 0 -or ($pypiOutput -match "No matching distribution")) {
        $pypiFailed = $true
    }
} catch {
    $pypiFailed = $true
}

if ($pypiFailed) {
    Write-Host ""
    Write-Host "PyPI install failed; falling back to latest main from GitHub..."
    pipx install --force "git+https://github.com/jleal52/claude-hub.git"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "GitHub install also failed. Check errors above."
    }
}

Write-Host ""
Write-Host "claude-hub installed. Open a NEW PowerShell window, then run:"
Write-Host "    claude-hub install"
Write-Host ""
Write-Host "(A new window is needed so the updated PATH from pipx takes effect.)"
