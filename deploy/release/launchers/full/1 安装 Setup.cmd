@echo off
rem Set it up, once (D70, D184): the same as typing the line START-HERE.md gives.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
pause
