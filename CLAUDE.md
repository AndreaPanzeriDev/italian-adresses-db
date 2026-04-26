# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An ETL pipeline that builds a complete Italian address database from OpenStreetMap data, ingests it into PostgreSQL, and optionally enriches each address with ISP fiber coverage data (OpenFiber, FiberCop, FastWeb).

## Commands

```bash
# Full pipeline
bash run.sh

# Individual steps (in order)
pip install -r requirements.txt
python download_osm.py          # Downloads ~1.5GB Italy OSM extract to data/
python extract_addresses.py     # Parses PBF -> data/addresses.csv (~2-4M rows)
python import_db.py             # Loads CSV into PostgreSQL
python enrich_coverage.py       # Optional: ISP coverage enrichment via API

# Database operations (PostgreSQL must be running)
psql -h $PGHOST -d $PGDATABASE -c "SELECT * FROM v_addresses_coverage LIMIT 10;"
psql -h $PGHOST -d $PGDATABASE -f schema.sql  # Reinitialize schema
```

## Environment

Copy `.env copy.example` to `.env` and configure PostgreSQL connection + optional ISP coverage API settings.

| Variable | Purpose |
|---|---|
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | PostgreSQL connection |
| `ISP_COVERAGE_BASE_URL` | ISP coverage API endpoint |
| `ISP_COVERAGE_API_KEY` | Optional API key for coverage endpoint |
| `ISP_COVERAGE_MAX_RPS` | Rate limit (default 200) |
| `ISP_COVERAGE_CONCURRENCY` | Async concurrency (default 200) |
| `ISP_COVERAGE_BATCH_SIZE` | Commit batch size (default 2000) |

## Architecture

Flat ETL pipeline of standalone Python scripts:

1. **`download_osm.py`** — Downloads `italy-latest.osm.pbf` from Geofabrik
2. **`extract_addresses.py`** — Parses OSM PBF using `osmium`, extracting `addr:*` tags into `data/addresses.csv`. Fields: street, house_number, city (falls back through town/village/hamlet), postcode, lat/lon, OSM ID/type, suburb, state_district
3. **`import_db.py`** — Loads CSV into PostgreSQL in phases: provinces → cities → streets → addresses (batches of 10K, `ON CONFLICT DO NOTHING`). Province is inferred from the first 2 digits of the CAP (postcode) via `cap_province.csv`. Postcodes are sanitized to 5-digit format.
4. **`enrich_coverage.py`** — Async HTTP client with sliding-window rate limiter queries ISP coverage API per address. Writes provider columns (covered, technology, max_download_mbps, max_upload_mbps) for OpenFiber, FiberCop, FastWeb into `address_provider_coverage`.

### Database Schema

Tables: `provinces`, `cities`, `streets`, `addresses`, `address_provider_coverage`

Views:
- `v_addresses` — Flattened address view joining all base tables
- `v_addresses_coverage` — Same + LEFT JOIN with coverage data

All tables use integer PKs with sequences. Foreign keys cascade from coverage. Indexes on postcode, city, province, lat/lon, street name.

### Key data files

- `provinces.csv` — All 107 Italian provinces (code, name, region)
- `cap_province.csv` — 2-digit CAP prefix → province code mapping (96 entries)

## Style

- No test framework is used — scripts are run directly
- Type hints are not used consistently
- `osmium.SimpleHandler` pattern for OSM parsing; `psycopg2` for DB; `httpx.AsyncClient` for async HTTP
- Configuration via `python-dotenv` + `os.environ.get()`
- Error handling via print/progress reporting rather than structured logging
- Data licensed under ODbL (OpenStreetMap)