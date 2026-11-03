# Production operations runbook

Article Studio exposes health, status, metrics, backup, and recovery controls for deployment verification. Run smoke checks after every deploy and run a restore drill on the backup schedule.

## Deployment smoke checks

```powershell
python scripts/production_smoke.py --base-url https://studio.example.com --metrics-token $env:METRICS_TOKEN
```

The probe checks `/health/?verbose=1` and `/status/`. Metrics are checked only when `--metrics-token` is supplied. A non-2xx response returns a non-zero exit code for CI or release gates.

## Backup and restore verification

```powershell
python manage.py create_backup
python manage.py run_recovery_drill
```

`create_backup` writes a checksummed database archive or media snapshot under `BACKUP_ROOT`. `run_recovery_drill` verifies the checksum and opens the archive read-only (`pg_restore --list` for PostgreSQL, read-only SQLite for local development). Treat `failed` as an incident; `unsupported` means the production restore dependency is missing and must be fixed before go-live.

## Bounded load probe

Run against staging first, then use a small request count during a production maintenance window:

```powershell
python scripts/load_test.py --url https://studio.example.com/health/ --requests 200 --concurrency 10
```

The result includes status counts, requests per second, and p50/p95 latency. The command exits non-zero when any request fails or returns a non-2xx status. It intentionally has no third-party dependency and does not create application data.

## Monitoring configuration

- Set `METRICS_TOKEN` before exposing `/metrics/`.
- Set `SENTRY_DSN` for error capture and `OTEL_ENABLED=true` with an OTLP endpoint for traces.
- Keep structured request logs enabled; every request includes an `X-Request-ID` and JSON log context.
- Alert on `/health/` failures, `/status/` degradation, queue delays, failed recovery drills, and elevated 5xx rate from the metrics endpoint.
- Keep `BACKUP_ENABLED=true`, verify `BACKUP_ROOT` is durable, and schedule both backup creation and recovery drills through Celery beat or the deployment scheduler.
