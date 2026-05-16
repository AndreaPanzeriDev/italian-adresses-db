#!/bin/bash
set -e

echo "=== Italian Addresses DB - Full Pipeline ==="
echo ""

echo "Step 1: Installing dependencies..."
pip3 install -r requirements.txt --break-system-packages
echo ""

echo "Step 2: Downloading OSM data..."
python3 download_osm.py
echo ""

echo "Step 3: Extracting addresses..."
python3 extract_addresses.py
echo ""

echo "Step 4: Importing into PostgreSQL..."
python3 import_db.py
echo ""

echo "Step 5: Deduplicating cities..."
python3 dedup_cities.py
echo ""

echo "=== Pipeline Complete ==="
