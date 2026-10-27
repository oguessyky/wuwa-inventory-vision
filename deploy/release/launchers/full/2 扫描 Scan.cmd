@echo off
rem Scan the bag (D184): then alt-tab into the game; F9 stops.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed yet: double-click "1 ... Setup" first.
  pause
  exit /b 1
)
uv run python -m wuwa_vision live --identify
rem the window stays only when something went wrong, to be read (D184)
if errorlevel 1 pause
