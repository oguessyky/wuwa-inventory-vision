@echo off
rem Uninstall (D232): the shortcuts, the installed environment, the model and the program's
rem files; it asks before your scans and settings. Runs from a copy, outside this folder: a
rem window still in a folder, or a batch file still being read, keeps it from being removed.
if not "%~1"=="--copy" (
  copy /y "%~f0" "%TEMP%\wuwa-uninstall.cmd" >nul
  "%TEMP%\wuwa-uninstall.cmd" --copy "%~dp0."
  exit /b
)
cd /d "%TEMP%"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed: nothing was set up here, so deleting this folder removes it all.
  pause
  exit /b 1
)
uv run --project "%~2" python -m wuwa_vision uninstall --folder "%~2"
exit /b
