@echo off
rem tssh cmd.exe shim shipped in the DeskTools package: runs tssh.py with the Python on PATH.
where python >nul 2>nul
if %errorlevel%==0 (
  python "%~dp0tssh.py" %*
) else (
  py -3 "%~dp0tssh.py" %*
)
