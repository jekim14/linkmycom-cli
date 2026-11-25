# linkmycom Windows installer (part of LinkMyCom): copies linkmycom.py to %LOCALAPPDATA%\linkmycom, writes linkmycom/lmc shims, adds the folder to the user PATH.
# This file is intentionally ASCII-only (no BOM, English messages) so that
#   irm https://raw.githubusercontent.com/jekim14/linkmycom-cli/HEAD/tools/linkmycom/install.ps1 | iex
# works in Windows PowerShell 5.1, which decodes GitHub's response as Latin-1.
# jekim14/linkmycom-cli (formerly jekim14/tssh) is the public mirror of tools/linkmycom in the private LinkMyCom repository.
# An old tssh install in %LOCALAPPDATA%\tssh keeps its tssh command, which now forwards to linkmycom.
# Local usage:  powershell -ExecutionPolicy Bypass -File install.ps1 [-NoPath] [-NoSetup]
# The download comes from the latest mirror release (linkmycom.py + linkmycom.py.sig + linkmycom.py.sha256) and is installed
# only after 'ssh-keygen -Y verify' accepts the signature (data given as a redirected file, not a pipe). Without ssh-keygen
# or a .sig asset it falls back to the SHA256 check with a warning. -Unverified uses the old raw-file download at -Ref.
param(
    [switch]$NoPath,
    [switch]$NoSetup,
    [switch]$Unverified,
    [string]$Repo = "jekim14/linkmycom-cli",
    [string]$Ref = "HEAD"
)

$ErrorActionPreference = "Stop"
# Same key and namespace as the CLI constants SIGNING_PUBKEY / SIGNER_IDENTITY / CLI_SIG_NAMESPACE.
$SigningPubKey = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGWKhtP9dXCC5mljTV/5DOf42NzaQ7EUHRAo9B+bX0+s"
$SignerIdentity = "linkmycom"
$SigNamespace = "linkmycom-keys"

function Find-SshKeygen {
    $c = Get-Command ssh-keygen -ErrorAction SilentlyContinue
    if ($c) { return $c.Source }
    $p = Join-Path $env:SystemRoot "System32\OpenSSH\ssh-keygen.exe"
    if (Test-Path -LiteralPath $p) { return $p }
    return $null
}

function Test-LinkMyComSignature([string]$File, [string]$SigFile, [string]$Keygen) {
    $dir = Split-Path -Parent $SigFile
    $allowed = Join-Path $dir "allowed_signers"
    [System.IO.File]::WriteAllText($allowed, "$SignerIdentity $SigningPubKey`n", (New-Object System.Text.ASCIIEncoding))
    $out = Join-Path $dir "verify.out"
    $err = Join-Path $dir "verify.err"
    # The data goes in as a redirected file. A pipe stalls ssh-keygen inside Windows OpenSSH sessions (CLI 0.4.7).
    # Inside an SSH session sshd leaves a *_POSIX_FD_STATE variable that makes the Windows ssh-keygen read the SSH channel
    # instead of its real standard input, so it never ends (measured 2026-11-21). Hide it for this call only.
    $fdState = @(Get-ChildItem env: | Where-Object { $_.Name -like '*_POSIX_FD_STATE' })
    foreach ($fdVar in $fdState) { Remove-Item -LiteralPath "env:$($fdVar.Name)" }
    try {
        $p = Start-Process -FilePath $Keygen -ArgumentList @("-Y", "verify", "-f", "`"$allowed`"", "-I", $SignerIdentity, "-n", $SigNamespace, "-s", "`"$SigFile`"") `
            -RedirectStandardInput $File -RedirectStandardOutput $out -RedirectStandardError $err -NoNewWindow -Wait -PassThru
    } finally {
        foreach ($fdVar in $fdState) { Set-Item -LiteralPath "env:$($fdVar.Name)" -Value $fdVar.Value }
    }
    return ($p.ExitCode -eq 0)
}

$src = if ($PSScriptRoot) { Join-Path $PSScriptRoot "linkmycom.py" } else { "" }
$downloaded = $null
$work = $null
if (-not $src -or -not (Test-Path $src)) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $work = Join-Path ([System.IO.Path]::GetTempPath()) ("linkmycom-install-" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    $downloaded = Join-Path $work "linkmycom.py"
    if ($Unverified) {
        $url = "https://raw.githubusercontent.com/$Repo/$Ref/tools/linkmycom/linkmycom.py"
        Write-Warning "-Unverified: downloading $url without a signature check."
        Invoke-WebRequest -Uri $url -OutFile $downloaded -UseBasicParsing
    } else {
        try {
            # The mirror also carries tower-v*/native-v* releases, so pick the newest CLI tag (v<version>) ourselves.
            $rels = Invoke-RestMethod -UseBasicParsing -Uri "https://api.github.com/repos/$Repo/releases?per_page=30" -Headers @{ "User-Agent" = "linkmycom-installer"; "Accept" = "application/vnd.github+json" }
            $rel = @($rels | Where-Object { $_.tag_name -match '^v\d+(\.\d+)+$' -and -not $_.draft -and -not $_.prerelease } | Sort-Object { [version]($_.tag_name.Substring(1)) } -Descending | Select-Object -First 1)[0]
            if (-not $rel) { throw "No CLI release (v<version>) found in $Repo." }
        } catch {
            throw "Could not read the latest release of $Repo ($($_.Exception.Message)). Try again later, or use -Unverified to install the raw file without a signature check."
        }
        $assets = @{}
        foreach ($a in $rel.assets) { $assets[$a.name] = $a.browser_download_url }
        if (-not $assets["linkmycom.py"]) { throw "Release $($rel.tag_name) of $Repo has no linkmycom.py asset." }
        Write-Host "Downloading linkmycom.py from release $($rel.tag_name) of $Repo"
        Invoke-WebRequest -Uri $assets["linkmycom.py"] -OutFile $downloaded -UseBasicParsing
        $verified = $false
        $keygen = Find-SshKeygen
        if ($assets["linkmycom.py.sig"] -and $keygen) {
            $sig = Join-Path $work "linkmycom.py.sig"
            Invoke-WebRequest -Uri $assets["linkmycom.py.sig"] -OutFile $sig -UseBasicParsing
            if (-not (Test-LinkMyComSignature $downloaded $sig $keygen)) {
                throw "Signature check failed for linkmycom.py ($($rel.tag_name)). Nothing was installed."
            }
            $verified = $true
            Write-Host "Signature OK ($SignerIdentity, $SigNamespace)."
        }
        if ($assets["linkmycom.py.sha256"]) {
            $shaFile = Join-Path $work "linkmycom.py.sha256"
            Invoke-WebRequest -Uri $assets["linkmycom.py.sha256"] -OutFile $shaFile -UseBasicParsing
            $expected = ((Get-Content -LiteralPath $shaFile -Raw).Trim() -split "\s+")[0].ToLower()
            $actual = (Get-FileHash -LiteralPath $downloaded -Algorithm SHA256).Hash.ToLower()
            if ($expected -ne $actual) { throw "SHA256 of linkmycom.py does not match linkmycom.py.sha256. Nothing was installed." }
            if (-not $verified) { Write-Warning "Signature not checked ($(if (-not $keygen) { 'ssh-keygen not found' } else { 'no .sig asset' })); only the SHA256 matched." }
        } elseif (-not $verified) {
            throw "Neither a signature check nor a SHA256 file was possible for release $($rel.tag_name). Nothing was installed (use -Unverified to override)."
        }
    }
    $src = $downloaded
}

$python = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $python = $cmd.Source; break }
}
if (-not $python) { throw "Python 3 was not found. Install it from https://www.python.org and run this again." }
$ver = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$ver -lt [version]"3.9") { throw "Python 3.9 or newer is required (found $ver at $python)." }

$dest = Join-Path $env:LOCALAPPDATA "linkmycom"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item $src (Join-Path $dest "linkmycom.py") -Force

# Paths under the user profile are written as %LOCALAPPDATA% etc. A literal non-ASCII user name (e.g. Korean) would be
# garbled, because cmd.exe reads batch files in the console code page. Anything left non-ASCII is written in that code page.
function Get-ShimPath([string]$Path, [switch]$PowerShell) {
    foreach ($var in @("LOCALAPPDATA", "APPDATA", "USERPROFILE")) {
        $base = [Environment]::GetEnvironmentVariable($var)
        if ($base) {
            $base = $base.TrimEnd("\")
            if ($Path.StartsWith($base + "\", [StringComparison]::OrdinalIgnoreCase)) {
                $prefix = if ($PowerShell) { "`$env:$var" } else { "%$var%" }
                return $prefix + $Path.Substring($base.Length)
            }
        }
    }
    return $Path
}
# cmd.exe reads batch files in the system OEM code page (cp949 on Korean Windows), not the user format culture.
$oemCodePage = [int](Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name OEMCP).OEMCP
$shimEncoding = [System.Text.Encoding]::GetEncoding($oemCodePage)
function Write-Shim([string]$Path, [string]$Body) {
    # .ps1 files get UTF-8 with BOM, which both Windows PowerShell 5.1 and PowerShell 7 read correctly.
    $enc = if ($Path -like "*.ps1") { New-Object System.Text.UTF8Encoding $true } else { $shimEncoding }
    [System.IO.File]::WriteAllText($Path, $Body, $enc)
}

# cmd.exe shims: linkmycom and its short name lmc. Both start Python directly (no nested cmd call, which cost ~0.3 s).
$cmdShim = "@echo off`r`n`"$(Get-ShimPath $python)`" `"%~dp0linkmycom.py`" %*`r`n"
Write-Shim (Join-Path $dest "linkmycom.cmd") $cmdShim
Write-Shim (Join-Path $dest "lmc.cmd") $cmdShim

# PowerShell wrapper: PowerShell resolves linkmycom.ps1 before linkmycom.cmd, so quoted arguments survive intact.
# Skipped when the execution policy would refuse to run it.
$ps1 = Join-Path $dest "linkmycom.ps1"
$policy = Get-ExecutionPolicy
if ($policy -in @("Restricted", "AllSigned")) {
    if (Test-Path $ps1) { Remove-Item $ps1 -Force }
    Write-Host "Execution policy is $policy; skipping the linkmycom.ps1 wrapper (linkmycom.cmd will be used)."
} else {
    $ps1Body = "# linkmycom PowerShell wrapper: forwards all arguments to linkmycom.py.`r`n& `"$(Get-ShimPath $python -PowerShell)`" `"`$PSScriptRoot\linkmycom.py`" @args`r`nexit `$LASTEXITCODE`r`n"
    Write-Shim $ps1 $ps1Body
}

# Old tssh install: its folder stays on PATH and its tssh command now forwards here. The settings in ~/.tssh are shared.
$old = Join-Path $env:LOCALAPPDATA "tssh"
if ((Test-Path (Join-Path $old "tssh.py")) -or (Test-Path (Join-Path $old "linkmycom.py"))) {
    # A tssh that already self-migrated also has linkmycom/lmc here. This folder is earlier on PATH, so every command
    # here must forward to the new install, otherwise the old copy keeps shadowing it.
    Write-Shim (Join-Path $old "tssh.cmd") "@echo off`r`nsetlocal`r`nset LINKMYCOM_INVOKED_AS=tssh`r`ncall `"%~dp0..\linkmycom\linkmycom.cmd`" %*`r`n"
    foreach ($name in @("linkmycom.cmd", "lmc.cmd")) { Write-Shim (Join-Path $old $name) "@echo off`r`ncall `"%~dp0..\linkmycom\linkmycom.cmd`" %*`r`n" }
    foreach ($stale in @("tssh.py", "tssh.ps1", "linkmycom.py", "linkmycom.ps1")) { Remove-Item (Join-Path $old $stale) -Force -ErrorAction SilentlyContinue }
    Write-Host "The old commands in $old (tssh, linkmycom, lmc) now forward to $dest."
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

if ($work -and (Test-Path $work)) { Remove-Item $work -Recurse -Force }
$installed = & $python (Join-Path $dest "linkmycom.py") version
Write-Host "Installed: $installed  ->  $dest"
Write-Host "Run: linkmycom  (or the short name lmc) in a new terminal"

# Make this PC reachable over SSH inside the tailnet and exchange public keys (asks for UAC once).
if (-not $NoSetup) {
    & $python (Join-Path $dest "linkmycom.py") setup
}
