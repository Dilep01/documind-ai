$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if (-not (Test-Path -LiteralPath '.env')) { & "$PSScriptRoot\setup.ps1" }
docker compose up --build -d
if ($LASTEXITCODE -ne 0) { throw 'DocuMind did not start. Check Docker Desktop and docker compose logs.' }
Write-Host 'DocuMind is starting at http://localhost:8765. Local administrator credentials are in .env.'
