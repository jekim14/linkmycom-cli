# tssh 를 %LOCALAPPDATA%\tssh 에 설치하고 PATH 에 등록하는 Windows 설치 스크립트.
# 사용법:  powershell -ExecutionPolicy Bypass -File install.ps1 [-NoPath]
param(
    [switch]$NoPath
)

$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "tssh.py"
if (-not (Test-Path $src)) { throw "tssh.py 를 찾지 못했습니다: $src" }

$python = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $python = $cmd.Source; break }
}
if (-not $python) { throw "Python 3 를 찾지 못했습니다. https://www.python.org 에서 설치한 뒤 다시 실행하세요." }
$ver = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.10") { throw "Python 3.10 이상이 필요합니다 (현재 $ver, $python)." }

$dest = Join-Path $env:LOCALAPPDATA "tssh"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item $src (Join-Path $dest "tssh.py") -Force

$shim = Join-Path $dest "tssh.cmd"
$shimBody = "@echo off`r`n`"$python`" `"%~dp0tssh.py`" %*`r`n"
[System.IO.File]::WriteAllText($shim, $shimBody, [System.Text.Encoding]::ASCII)

if (-not $NoPath) {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) { $parts = $userPath.Split(";") | Where-Object { $_ -ne "" } }
    if ($parts -notcontains $dest) {
        [Environment]::SetEnvironmentVariable("Path", (($parts + $dest) -join ";"), "User")
        Write-Host "사용자 PATH 에 $dest 를 추가했습니다. 새 터미널을 열어야 적용됩니다."
    }
}

$installed = & $python (Join-Path $dest "tssh.py") version
Write-Host "설치 완료: $installed  →  $dest"
Write-Host "실행: tssh        (새 터미널에서)"
