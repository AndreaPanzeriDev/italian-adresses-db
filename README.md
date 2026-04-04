# Italian Addresses Database

Complete Italian address database from OpenStreetMap, ready for PostgreSQL.

## Prerequisites

- Python 3.8+
- PostgreSQL (local or external)
- ~5GB free disk space

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure database connection

Copy `.env.example` to `.env` and fill in your external PostgreSQL credentials:

```bash
cp .env.example .env
```

Edit `.env`:
```
PGHOST=your-db-host.com
PGPORT=5432
PGDATABASE=your_database_name
PGUSER=your_username
PGPASSWORD=your_password
```

### 3. Download OSM data

```bash
python download_osm.py
```

Downloads ~1.5GB Italy extract from Geofabrik.

### 4. Extract addresses

```bash
python extract_addresses.py
```

Parses the OSM file and exports ~2-4M addresses to CSV. Takes 5-15 minutes depending on hardware.

### 5. Import into PostgreSQL

```bash
python import_db.py
```

## Environment Variables

All configured via `.env` file (see `.env.example`):

| Variable | Required | Description |
|----------|----------|-------------|
| PGHOST | Yes | Database host |
| PGPORT | No | Database port (default: 5432) |
| PGDATABASE | Yes | Database name |
| PGUSER | Yes | PostgreSQL user |
| PGPASSWORD | Yes | PostgreSQL password |

## Usage

Query the convenient view:

```sql
SELECT * FROM v_addresses 
WHERE postcode = '20100' 
ORDER BY street, house_number;
```

## Data Coverage

- ~2-4 million addresses (varies by OSM update)
- Northern Italy: ~70-85% coverage
- Central Italy: ~60-75% coverage
- Southern Italy: ~50-65% coverage

## Schema

- **provinces** - Italian provinces with ISTAT codes
- **cities** - Municipalities (comuni)
- **streets** - Normalized street names
- **addresses** - Full addresses with coordinates

## License

OpenStreetMap data is ODbL licensed. See https://www.openstreetmap.org/copyright
