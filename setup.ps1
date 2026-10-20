# Set the project up on Windows (D70): checks the two prerequisites, then hands
# over to tools/setup.py, which works out what this machine is.
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Yes
#   powershell -ExecutionPolicy Bypass -File setup.ps1 -Scanner   # scans for a home (D174)

param([switch]$Yes, [switch]$Check, [switch]$Scanner)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# Python 3.12 from python.org, and no other: the Store's cannot be bundled, and without a
# 3.12 uv would fetch a build of its own, which Windows Smart App Control refuses to start
# (D151). A release carries python.org's own portable build in python\ (D175): that one
# first, then an installed one -- `py` finds a 3.12 even when another is first on the PATH.
$found = $null
$beside = Join-Path $PSScriptRoot 'python\python.exe'
$tries = @(@('py', '-3.12'), @('python'))
if (Test-Path $beside) { $tries = @(, @($beside)) + $tries }
foreach ($try in $tries) {
  $exe = $try[0]
  if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
  $rest = @($try | Select-Object -Skip 1)
  $said = & $exe @rest -c "import sys; print('%d.%d|%s' % (sys.version_info[0], sys.version_info[1], sys.executable))" 2>$null
  if ($LASTEXITCODE -eq 0 -and $said -like '3.12|*' -and $said -notlike '*WindowsApps*') {
    $found = ($said -split '\|', 2)[1]
    break
  }
}
if (-not $found) {
  Write-Host 'Python 3.12 is missing: install it from https://www.python.org/downloads/ (NOT the Microsoft Store,'
  Write-Host 'and 3.12 exactly: 3.13 will not do). Then run this again.'
  exit 1
}
Write-Host "Python  : $found"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host 'uv is missing, and so is winget to install it: see https://docs.astral.sh/uv/ , then run this again.'
    exit 1
  }
  Write-Host 'uv is missing. Installing it with winget...'
  winget install --id astral-sh.uv -e --accept-source-agreements --accept-package-agreements
  # what winget added to the PATH reaches new windows only: read it again for this one
  $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
              [Environment]::GetEnvironmentVariable('Path', 'User')
  if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'uv was installed but cannot be found yet: open a new PowerShell window and run this again.'
    exit 1
  }
}

$args = @()
if ($Yes) { $args += '--yes' }
if ($Check) { $args += '--check' }
if ($Scanner) { $args += '--scanner' }
# uv builds the environment on this one and no other (it is not on the PATH when it is ours)
$args += @('--python', $found)
& $found tools/setup.py @args
exit $LASTEXITCODE
