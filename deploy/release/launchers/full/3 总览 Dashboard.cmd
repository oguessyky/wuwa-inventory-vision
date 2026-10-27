@echo off
rem The pages (D184): open http://127.0.0.1:4000 -- close this window to stop them.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed yet: double-click "1 ... Setup" first.
  pause
  exit /b 1
)
uv run python -m wuwa_vision serve
rem the window stays only when something went wrong, to be read (D184)
if errorlevel 1 pause
