param(
  [int]$BackendPort = 8000
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$venv = Join-Path $backend '.venv'
$venvPython = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path $venvPython)) {
  python -m venv $venv
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $backend 'requirements.txt')
Push-Location $backend
try {
  & $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort
}
finally {
  Pop-Location
}
