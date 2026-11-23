# MEDELTOMTEN - start (fungerar offline efter install.ps1).
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv\Scripts\python.exe)) { throw "Ingen .venv - kör scripts\install.ps1 först (med internet)." }
if (-not (Test-Path frontend\dist\index.html)) { throw "Frontend är inte byggd - kör scripts\install.ps1 först." }

$port = if ($env:MEDELTOMTEN_PORT) { $env:MEDELTOMTEN_PORT } else { 8000 }
Start-Job -ScriptBlock { param($p) Start-Sleep 2; Start-Process "http://127.0.0.1:$p/control" } -ArgumentList $port | Out-Null
Write-Host "MEDELTOMTEN kör på http://127.0.0.1:$port/control  (Ctrl+C stoppar)"
Set-Location backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $port
