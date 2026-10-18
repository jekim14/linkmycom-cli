# linkmycom Windows installer (part of LinkMyCom): copies linkmycom.py to %LOCALAPPDATA%\linkmycom, writes linkmycom/lmc shims, adds the folder to the user PATH.
# This file is intentionally ASCII-only (no BOM, English messages) so that
#   irm https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.ps1 | iex
# works in Windows PowerShell 5.1, which decodes GitHub's response as Latin-1.
# jekim14/linkmycom-cli (formerly jekim14/tssh) is the public mirror of tools/linkmycom in the private LinkMyCom repository.
# An old tssh install in %LOCALAPPDATA%\tssh keeps its tssh command, which now forwards to linkmycom.
# Local usage:  powershell -ExecutionPolicy Bypass -File install.ps1 [-NoPath] [-NoSetup]
param(
    [switch]$NoPath,
    [switch]$NoSetup,
    [string]$Repo = "jekim14/linkmycom-cli",
    [string]$Ref = "HEAD"
)

$ErrorActionPreference = "Stop"
$src = if ($PSScriptRoot) { Join-Path $PSScriptRoot "linkmycom.py" } else { "" }
$downloaded = $null
if (-not $src -or -not (Test-Path $src)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = "https://raw.githubusercontent.com/$Repo/$Ref/tools/linkmycom/linkmycom.py"
    $downloaded = Join-Path ([System.IO.Path]::GetTempPath()) ("linkmycom-" + [guid]::NewGuid().ToString("N") + ".py")
    Write-Host "Downloading linkmycom.py from $url"
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

$dest = Join-Path $env:LOCALAPPDATA "linkmycom"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item $src (Join-Path $dest "linkmycom.py") -Force

# cmd.exe shims: linkmycom and its short name lmc.
$shimBody = "@echo off`r`n`"$python`" `"%~dp0linkmycom.py`" %*`r`n"
[System.IO.File]::WriteAllText((Join-Path $dest "linkmycom.cmd"), $shimBody, [System.Text.Encoding]::ASCII)
[System.IO.File]::WriteAllText((Join-Path $dest "lmc.cmd"), "@echo off`r`ncall `"%~dp0linkmycom.cmd`" %*`r`n", [System.Text.Encoding]::ASCII)

# PowerShell wrapper: PowerShell resolves linkmycom.ps1 before linkmycom.cmd, so quoted arguments survive intact.
# Skipped when the execution policy would refuse to run it.
$ps1 = Join-Path $dest "linkmycom.ps1"
$policy = Get-ExecutionPolicy
if ($policy -in @("Restricted", "AllSigned")) {
    if (Test-Path $ps1) { Remove-Item $ps1 -Force }
    Write-Host "Execution policy is $policy; skipping the linkmycom.ps1 wrapper (linkmycom.cmd will be used)."
} else {
    $ps1Body = "# linkmycom PowerShell wrapper: forwards all arguments to linkmycom.py.`r`n& `"$python`" `"`$PSScriptRoot\linkmycom.py`" @args`r`nexit `$LASTEXITCODE`r`n"
    [System.IO.File]::WriteAllText($ps1, $ps1Body, [System.Text.Encoding]::ASCII)
}

# Old tssh install: its folder stays on PATH and its tssh command now forwards here. The settings in ~/.tssh are shared.
$old = Join-Path $env:LOCALAPPDATA "tssh"
if (Test-Path (Join-Path $old "tssh.py")) {
    $fwd = "@echo off`r`nset LINKMYCOM_INVOKED_AS=tssh`r`ncall `"$(Join-Path $dest 'linkmycom.cmd')`" %*`r`n"
    [System.IO.File]::WriteAllText((Join-Path $old "tssh.cmd"), $fwd, [System.Text.Encoding]::ASCII)
    foreach ($stale in @("tssh.py", "tssh.ps1")) { Remove-Item (Join-Path $old $stale) -Force -ErrorAction SilentlyContinue }
    Write-Host "The old tssh command in $old now forwards to linkmycom."
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
$installed = & $python (Join-Path $dest "linkmycom.py") version
Write-Host "Installed: $installed  ->  $dest"
Write-Host "Run: linkmycom  (or the short name lmc) in a new terminal"

# Make this PC reachable over SSH inside the tailnet and exchange public keys (asks for UAC once).
if (-not $NoSetup) {
    & $python (Join-Path $dest "linkmycom.py") setup
}
