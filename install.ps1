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

# PowerShell 에서는 .ps1 래퍼가 먼저 잡혀 따옴표·파이프가 든 인자도 그대로 전달된다. 실행 정책이 막으면 만들지 않는다.
$ps1 = Join-Path $dest "tssh.ps1"
$policy = Get-ExecutionPolicy
if ($policy -in @("Restricted", "AllSigned")) {
    if (Test-Path $ps1) { Remove-Item $ps1 -Force }
    Write-Host "실행 정책이 $policy 이라 tssh.ps1 래퍼는 건너뜁니다 (tssh.cmd 만 사용)."
} else {
    $ps1Body = "# tssh PowerShell 래퍼. 인자를 그대로 tssh.py 에 넘긴다.`r`n& `"$python`" `"`$PSScriptRoot\tssh.py`" @args`r`nexit `$LASTEXITCODE`r`n"
    [System.IO.File]::WriteAllText($ps1, $ps1Body, (New-Object System.Text.UTF8Encoding $true))
}

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
