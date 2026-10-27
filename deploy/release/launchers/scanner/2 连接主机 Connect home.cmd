@echo off
rem Give this PC its home, once (D145, D184): the address and key the home's setup gave.
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv is not installed yet: double-click "1 ... Setup" first.
  pause
  exit /b 1
)
echo The home's address: just its name on Tailscale (Enter for wuwa-home), or the name
echo Tailscale shows (wuwa-home.your-tailnet.ts.net), or its 100.x address. http:// and port
echo 4000 are put in when left out.
set WUWA_HOME=wuwa-home
set /p WUWA_HOME="Home address [wuwa-home]: "
echo The key: press Enter to take home.key from your Downloads folder (download it from
echo the home's data folder on the NAS first), or paste the key, or drag the file in.
set WUWA_KEY=
set /p WUWA_KEY="Home key [Enter = home.key in Downloads]: "
uv run python -m wuwa_vision home set "%WUWA_HOME%" "%WUWA_KEY%"
pause
