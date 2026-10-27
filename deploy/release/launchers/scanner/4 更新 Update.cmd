@echo off
rem Update to the home's version, only when the home says this one is behind (D203).
rem Runs from a copy: a batch file rewritten while it runs would go wrong.
if not "%~1"=="--copy" (
  copy /y "%~f0" "%TEMP%\wuwa-update.cmd" >nul
  "%TEMP%\wuwa-update.cmd" --copy "%~dp0"
  exit /b
)
cd /d "%~2"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed yet: double-click "1 ... Setup" first.
  pause
  exit /b 1
)
uv run python -m wuwa_vision update
rem 3: nothing to update; 1: it said why
if errorlevel 3 (
  pause
  exit /b 0
)
if errorlevel 1 (
  pause
  exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File "setup.ps1" -Scanner -Yes
pause
