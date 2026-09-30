$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$projectDirectory = Join-Path $repositoryRoot 'Article'
$managePy = Join-Path $projectDirectory 'manage.py'

if (-not (Test-Path -LiteralPath $managePy)) {
    throw "Django manage.py was not found at $managePy"
}

Push-Location $projectDirectory
try {
    python manage.py makemigrations articles users
    python manage.py migrate
    python manage.py check
}
finally {
    Pop-Location
}
