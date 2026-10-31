@echo off
rem Give this PC its server, once (D145, D184): the address and key the server's setup gave.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed yet: double-click "1 ... Setup" first.
  pause
  exit /b 1
)
echo The server's address: just its name on Tailscale (Enter tries wuwa-server), or the name
echo Tailscale shows (wuwa-server.your-tailnet.ts.net), or its 100.x address. http:// and port
echo 4000 are put in when left out.
set WUWA_SERVER=
set /p WUWA_SERVER="Server address [Enter = wuwa-server]: "
echo The key: press Enter to take server.key from your Downloads folder (download it from
echo the server's data folder on the NAS first), or paste the key, or drag the file in.
set WUWA_KEY=
set /p WUWA_KEY="Server key [Enter = server.key in Downloads]: "
uv run python -m wuwa_vision server set "%WUWA_SERVER%" "%WUWA_KEY%"
pause
