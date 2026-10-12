#!/usr/bin/env sh
set -eu

output_directory="${1:-backups}"
timestamp="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$output_directory"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-article_management}" -d "${POSTGRES_DB:-article_management}" > "$output_directory/article-studio-$timestamp.sql"
echo "PostgreSQL backup created in $output_directory"
