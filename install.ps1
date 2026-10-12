# tssh Windows installer (part of DeskTools): copies tssh.py to %LOCALAPPDATA%\tssh, writes shims, adds the folder to the user PATH.
# This file is intentionally ASCII-only (no BOM, English messages) so that
#   irm https://raw.githubusercontent.com/jekim14/tssh/HEAD/tools/tssh/install.ps1 | iex
# works in Windows PowerShell 5.1, which decodes GitHub's response as Latin-1.
# jekim14/tssh is the public mirror of tools/tssh in the private DeskTools repository.
# Local usage:  powershell -ExecutionPolicy Bypass -File install.ps1 [-NoPath] [-NoSetup]
param(
    [switch]$NoPath,
    [switch]$NoSetup,
    [string]$Repo = "jekim14/tssh",
    [string]$Ref = "HEAD"
)

$ErrorActionPreference = "Stop"
$src = if ($PSScriptRoot) { Join-Path $PSScriptRoot "tssh.py" } else { "" }
$downloaded = $null
if (-not $src -or -not (Test-Path $src)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = "https://raw.githubusercontent.com/$Repo/$Ref/tools/tssh/tssh.py"
    $downloaded = Join-Path ([System.IO.Path]::GetTempPath()) ("tssh-" + [guid]::NewGuid().ToString("N") + ".py")
    Write-Host "Downloading tssh.py from $url"
    Invoke-WebRequest -Uri $url -OutFile $downloaded -UseBasicParsing
    $src = $downloaded
}

$python = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $python = $cmd.Source; break }
}
if (-not $python) { throw "Python 3 was not found. Install it from https://www.python.org and run this again." }
$ver = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.10") { throw "Python 3.10 or newer is required (found $ver at $python)." }

$dest = Join-Path $env:LOCALAPPDATA "tssh"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item $src (Join-Path $dest "tssh.py") -Force

# cmd.exe shim.
$shim = Join-Path $dest "tssh.cmd"
$shimBody = "@echo off`r`n`"$python`" `"%~dp0tssh.py`" %*`r`n"
[System.IO.File]::WriteAllText($shim, $shimBody, [System.Text.Encoding]::ASCII)

# PowerShell wrapper: PowerShell resolves tssh.ps1 before tssh.cmd, so quoted arguments survive intact.
# Skipped when the execution policy would refuse to run it.
$ps1 = Join-Path $dest "tssh.ps1"
$policy = Get-ExecutionPolicy
if ($policy -in @("Restricted", "AllSigned")) {
    if (Test-Path $ps1) { Remove-Item $ps1 -Force }
    Write-Host "Execution policy is $policy; skipping the tssh.ps1 wrapper (tssh.cmd will be used)."
} else {
    $ps1Body = "# tssh PowerShell wrapper: forwards all arguments to tssh.py.`r`n& `"$python`" `"`$PSScriptRoot\tssh.py`" @args`r`nexit `$LASTEXITCODE`r`n"
    [System.IO.File]::WriteAllText($ps1, $ps1Body, [System.Text.Encoding]::ASCII)
}

if (-not $NoPath) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) { $parts = $userPath.Split(";") | Where-Object { $_ -ne "" } }
    if ($parts -notcontains $dest) {
        [Environment]::SetEnvironmentVariable("Path", (($parts + $dest) -join ";"), "User")
        Write-Host "Added $dest to the user PATH. Open a new terminal for it to take effect."
    }
}

if ($downloaded -and (Test-Path $downloaded)) { Remove-Item $downloaded -Force }
$installed = & $python (Join-Path $dest "tssh.py") version
Write-Host "Installed: $installed  ->  $dest"
Write-Host "Run: tssh   (in a new terminal)"

# Make this PC reachable over SSH inside the tailnet and exchange public keys (asks for UAC once).
if (-not $NoSetup) {
    & $python (Join-Path $dest "tssh.py") setup
}
