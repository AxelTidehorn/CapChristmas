# MEDELTOMTEN - engångsinstallation (kräver internet). Kör från repo-roten:
#   powershell -ExecutionPolicy Bypass -File scripts\install.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt

Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "Klart. Starta med: powershell -ExecutionPolicy Bypass -File scripts\start.ps1"
