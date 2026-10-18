@echo off
rem linkmycom cmd.exe shim shipped in the LinkMyCom package: runs linkmycom.py with the Python on PATH.
where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0linkmycom.py" %*
) else (
  py -3 "%~dp0linkmycom.py" %*
)
