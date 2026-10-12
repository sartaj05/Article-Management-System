param(
    [string]$OutputDirectory = "backups"
)

$ErrorActionPreference = 'Stop'
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$outputPath = Join-Path $OutputDirectory "article-studio-$timestamp.sql"

docker compose exec -T db pg_dump -U article_management -d article_management | Set-Content -Encoding utf8 $outputPath
Write-Host "PostgreSQL backup created at $outputPath"
