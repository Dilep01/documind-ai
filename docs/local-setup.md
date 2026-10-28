# Local setup and operation

## Start

1. Start Docker Desktop with Linux containers.
2. Run `./scripts/setup.ps1` from the project folder. It creates `.env` only if absent.
3. Run `./scripts/start.ps1`. The first build downloads free images/packages.
4. Open http://localhost:8765. Username: `admin`. Read the generated password from `DOCUMIND_ADMIN_PASSWORD` in `.env`.
5. Upload a fictional sample from `data/samples/`.

Keep `.env` private. Startup migrates the schema, creates the first administrator if absent, trains the small classifier, and starts the API. The worker waits for readiness. Existing credentials are preserved: editing `.env` after account creation does not reset its password.

Verify fields and rows, choose the printed tax mode, save a revision, resolve blockers, acknowledge warnings with a reason, and approve. Exports use that approved revision. Saving later changes invalidates approval.

## Optional models

The local configuration uses `nomic-embed-text:latest` and `qwen3:1.7b` through Ollama. No paid endpoint is called. When unavailable, core OCR/review/export and keyword search work. Docker Desktop normally reaches the host through `host.docker.internal:11434`. Do not weaken an existing model-server binding to make this work; use core mode while arranging an explicitly local connection. The verification report records actual observed behavior.

Set `DOCUMIND_ALLOW_SELF_APPROVAL=false` to require another reviewer. Team access creates local uploader/reviewer/admin accounts; there is no public signup. Uploaders can only access their documents.

## Development

Python 3.12/3.13, Node 22+, and the pinned lockfiles are the baseline. Install `requirements.lock`, then `pip install --no-deps --no-build-isolation -e .`. Use the installed Python's full path if Windows' launcher points to an unconfigured manager. Native OCR needs Tesseract on PATH; the container includes it.

For a native backend, configure a PostgreSQL database with pgvector using `DOCUMIND_DATABASE_URL`, `DOCUMIND_STORAGE`, and a unique `DOCUMIND_ADMIN_PASSWORD`. Run `python -m documind_ai.manage migrate`, then `seed`, then `uvicorn documind_ai.api:app --host 127.0.0.1 --port 8765`. Run `python -m documind_ai.worker` separately. Compose avoids changing an existing PostgreSQL installation.

Inside `frontend/`, use `npm ci`, `npm run dev`, and `npm run build`. Direct JavaScript entry points avoid Windows .cmd shim errors caused by the ampersand in this folder name. The development server proxies API requests to port 8765.

## Verify and stop

```powershell
docker compose exec -T app python -m pytest -q
docker compose exec -T app python -m ruff check backend
docker compose exec -T app python -m ruff format --check backend
```

Database tests use uniquely named schemas, not application records. Native tests without PostgreSQL/Tesseract skip those integration paths; use the full container suite. Stop with `./scripts/stop.ps1`; this preserves volumes. Restart with `docker compose start`. Inspect `docker compose ps` and bounded app/worker logs when diagnosing failures. Do not remove needed data volumes.

## Backup and restore verification

```powershell
.\.venv\Scripts\python.exe scripts/recovery.py backup backups/my-snapshot
.\.venv\Scripts\python.exe scripts/recovery.py verify backups/my-snapshot
```

Backup briefly stops app/worker writes, saves a DB snapshot and storage, includes private configuration, checks originals, and restarts services. Each destination must be new. Backups contain credentials and document data: never publish them.

Verification restores into a separately named temporary PostgreSQL container without published ports, compares record counts, and checks original-file hashes. It never overwrites the running workspace. This is recovery verification, not automatic failover. A real restore should use new volumes and a reviewed maintenance procedure.
