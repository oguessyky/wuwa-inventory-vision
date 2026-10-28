@echo off
rem Set the scanner up, once (D174, D184): the server sends the catalogue.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" -Scanner
pause
