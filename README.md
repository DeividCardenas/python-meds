# python-meds

Medication catalog and pricing platform built with FastAPI, PostgreSQL (pgvector), Redis and Celery.

---

## Quick start

```bash
cp .env.example .env          # copy environment template (credentials already filled in)
docker compose up --build -d  # build images and start all services
```

---

## Connecting to PostgreSQL from pgAdmin / DBeaver

The Docker container maps **host port 5433 → container port 5432** so that it does not clash with any native PostgreSQL installation that may already be listening on 5432.

| **Field**    | **Value**             |
|--------------|-----------------------|
| **Host**     | `127.0.0.1`           |
| **Port**     | `5433`                |
| **User**     | `genhospi_admin`      |
| **Password** | `GenhospiSecure2026!` |
| **Database** | `genhospi_catalog` (or `genhospi_pricing`) |

> **Important:** always use port **5433** (the host-mapped port), not 5432.
> If you type 5432 you will hit the native Postgres on your machine (if any) instead of the container.

---

## Wipe the volume and rebuild from scratch

Run this command if credentials became corrupted inside the volume, or any time you need a clean slate:

```bash
docker compose down -v && docker compose up --build -d
```

`-v` removes all named volumes (including `postgres_data`), so PostgreSQL will reinitialise with the credentials defined in `.env` on the next start.

---

## Architecture

| Service    | Internal address | Host port |
|------------|-----------------|-----------|
| PostgreSQL | `db:5432`        | `5433`    |
| Redis      | `redis:6379`     | `6379`    |
| Backend    | `backend:8000`   | `8000`    |
| Frontend   | `frontend:80`    | `3000`    |

Services inside the Docker network communicate using the service name (e.g. `db:5432`).
External tools on the host connect via the mapped host port (e.g. `localhost:5433`).
