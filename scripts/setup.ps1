$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (Test-Path -LiteralPath '.env') {
    Write-Host 'Existing configuration preserved. Run .\scripts\start.ps1 to start DocuMind.'
    exit 0
}
$dbPassword = [Guid]::NewGuid().ToString('N') + [Guid]::NewGuid().ToString('N')
$adminPassword = 'Dm!' + [Guid]::NewGuid().ToString('N')
@"
DOCUMIND_DB_PASSWORD=$dbPassword
DOCUMIND_ADMIN_PASSWORD=$adminPassword
DOCUMIND_OLLAMA_URL=http://host.docker.internal:11434
DOCUMIND_ALLOW_SELF_APPROVAL=true
"@ | Set-Content -LiteralPath '.env' -Encoding utf8
Write-Host 'Created local configuration with unique passwords in .env. Username: admin.'
Write-Host 'Keep .env private. Run .\scripts\start.ps1 next.'
