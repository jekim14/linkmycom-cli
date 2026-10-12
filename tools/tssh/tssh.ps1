# tssh PowerShell wrapper shipped in the DeskTools package: finds Python and forwards all arguments to tssh.py.
$tsshPython = $null
foreach ($name in @("python", "python3", "py")) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") { $tsshPython = $cmd.Source; break }
}
if (-not $tsshPython) {
    Write-Host "Python 3 was not found. Install it from https://www.python.org and run this again."
    exit 1
}
& $tsshPython (Join-Path $PSScriptRoot "tssh.py") @args
exit $LASTEXITCODE
