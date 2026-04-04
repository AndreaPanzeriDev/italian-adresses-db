#!/bin/bash
set -e

echo "=== Italian Addresses DB - Full Pipeline ==="
echo ""

echo "Step 1: Installing dependencies..."
pip install -r requirements.txt
echo ""

echo "Step 2: Downloading OSM data..."
python download_osm.py
echo ""

echo "Step 3: Extracting addresses..."
python extract_addresses.py
echo ""

echo "Step 4: Importing into PostgreSQL..."
python import_db.py
echo ""

echo "=== Pipeline Complete ==="
