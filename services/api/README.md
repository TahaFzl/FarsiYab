# FarsiYab API

Backend for FarsiYab: indexes cities from open data sources, detects Iranian and
Persian-speaking businesses, and serves search results with sources and evidence.
Design documents are in [`docs/`](../../docs/); this file is only about running it.

## Requirements

- **PostgreSQL 16 + PostGIS**: the only service to install (no Docker, no Redis)
  - Ubuntu/Debian: `sudo apt install postgresql-16 postgresql-16-postgis-3`
  - macOS: `brew install postgresql@16 postgis`
  - Windows: the official PostgreSQL installer, then PostGIS from StackBuilder
- **Python 3.11+** and [uv](https://docs.astral.sh/uv/)

No API keys or accounts are needed (ADR-005).

## Setup

```bash
# 1. Database, role and extensions (as a PostgreSQL superuser)
sudo -u postgres scripts/setup_db.sh          # run from the repository root

# 2. Python dependencies
cd services/api
uv sync

# 3. Tables + countries, cities, categories and sources from data/*.yaml
uv run farsiyab db init
```

Settings come from `FARSIYAB_*` environment variables or `services/api/.env`
(see [`.env.example`](.env.example)).

## Use

```bash
uv run farsiyab index toronto                  # Overture + OSM + website checks
uv run farsiyab index toronto --source overture --no-websites   # quick run
uv run farsiyab cities                         # what is indexed and when
uv run farsiyab serve                          # API on http://127.0.0.1:8000 (docs at /docs)
uv run farsiyab worker                         # processes jobs queued by searches
```

Example:

```bash
curl 'http://127.0.0.1:8000/api/v1/search?country=CA&city=toronto&categories=restaurant'
```

When a search hits a city that was never indexed (or is older than 7 days) the
response contains `live_search.job_id`; the worker picks it up, and
`GET /api/v1/search/jobs/{job_id}` reports progress.

## Tests

```bash
sudo -u postgres env DB_NAME=farsiyab_test scripts/setup_db.sh   # once
uv run pytest
uv run ruff check .
```

Database tests use `FARSIYAB_TEST_DATABASE_URL`
(default `postgresql+psycopg://farsiyab:farsiyab@localhost:5432/farsiyab_test`)
and are skipped if it is unreachable.

## Layout

| Path | What |
|---|---|
| `farsiyab/adapters/` | One module per source: `overture.py`, `osm.py`, `website.py` |
| `farsiyab/detection/` | Iranian-ness signals, weights, Persian-script rules |
| `farsiyab/links.py` | Normalizes websites, social profiles and phone numbers |
| `farsiyab/resolution.py` | Merges the same business seen in several sources |
| `farsiyab/indexer.py` | Runs a full city index |
| `farsiyab/jobs.py`, `quota.py` | Job queue and request caps, both in PostgreSQL |
| `farsiyab/api.py` | HTTP API (`docs/05-api.md`) |
| `migrations/` | Alembic migrations |
| `../../data/` | Cities, categories, sources and detector word lists (edit without code changes) |
