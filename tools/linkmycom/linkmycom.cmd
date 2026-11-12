@echo off
rem linkmycom cmd.exe shim shipped in the LinkMyCom package: runs linkmycom.py with the Python on PATH,
rem skipping the Microsoft Store stub in WindowsApps (same rule as linkmycom.ps1).
setlocal
set "LMC_PY="
for %%N in (python.exe python3.exe py.exe) do (
  if not defined LMC_PY (
    for /f "delims=" %%P in ('where %%N 2^>nul') do (
      if not defined LMC_PY call :lmc_pick "%%P"
    )
  )
)
if not defined LMC_PY (
  echo Python 3 was not found. Install it from https://www.python.org and run this again.
  exit /b 1
)
"%LMC_PY%" "%~dp0linkmycom.py" %*
exit /b %errorlevel%

:lmc_pick
echo %~1| findstr /i /c:"WindowsApps" >nul && exit /b 0
set "LMC_PY=%~1"
exit /b 0
