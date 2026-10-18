# linkmycom PowerShell wrapper shipped in the LinkMyCom package: finds Python and forwards all arguments to linkmycom.py.
$lmcPython = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $lmcPython = $cmd.Source; break }
}
if (-not $lmcPython) {
    Write-Host "Python 3 was not found. Install it from https://www.python.org and run this again."
    exit 1
}
& $lmcPython (Join-Path $PSScriptRoot "linkmycom.py") @args
exit $LASTEXITCODE
