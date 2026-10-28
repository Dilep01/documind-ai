$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
docker compose stop
Write-Host 'Stopped. Your documents and database volumes are preserved.'
