# MEDELTOMTEN - engangsinstallation. Fardigbyggt paket kraver bara Python, inte Node.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path .venv)) {
    py -3 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Kunde inte skapa Python-miljon." }
}
.\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Kunde inte uppdatera pip." }
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Kunde inte installera Python-paketen." }

if (Test-Path frontend\dist\index.html) {
    Write-Host "Fardigbyggt granssnitt finns. Node.js behovs inte."
} else {
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
        throw "Detta ar kallkodspaketet. Hamta det fardigbyggda paketet for installation utan Node.js."
    }
    Push-Location frontend
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci misslyckades." }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend-bygget misslyckades." }
    } finally { Pop-Location }
}

Write-Host "Klart. Starta med: powershell -ExecutionPolicy Bypass -File scripts\start.ps1"
