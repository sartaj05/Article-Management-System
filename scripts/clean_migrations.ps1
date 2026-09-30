$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$projectDirectory = Join-Path $repositoryRoot 'Article'
$customApps = @('articles', 'users')

Write-Host 'This removes migration files except __init__.py for the custom apps and deletes Python caches.' -ForegroundColor Yellow
Write-Host 'Do not run this against a shared or production database.' -ForegroundColor Yellow
$confirmation = Read-Host 'Type DELETE to continue'
if ($confirmation -cne 'DELETE') {
    Write-Host 'Cancelled.'
    exit 0
}

foreach ($app in $customApps) {
    $migrationDirectory = Join-Path $projectDirectory "$app\migrations"
    if (Test-Path -LiteralPath $migrationDirectory) {
        Get-ChildItem -LiteralPath $migrationDirectory -File -Filter '*.py' |
            Where-Object { $_.Name -ne '__init__.py' } |
            Remove-Item -Force
    }
}

Get-ChildItem -LiteralPath $repositoryRoot -Directory -Recurse -Force -Filter '__pycache__' |
    Remove-Item -Recurse -Force

Write-Host 'Migration files and Python caches were removed locally.' -ForegroundColor Green
Write-Host 'Run .\scripts\migrate.ps1 to regenerate migrations from the current models.'
