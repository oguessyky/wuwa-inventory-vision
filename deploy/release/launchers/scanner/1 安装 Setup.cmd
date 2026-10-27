@echo off
rem Set the scanner up, once (D174, D184): the home sends the catalogue.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -Scanner
pause
