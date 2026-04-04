import osmium
import csv
import sys
import os
import json
from collections import defaultdict

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
OUTPUT_FILE = os.path.join(DATA_DIR, 'addresses.csv')

class AddressExtractor(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.addresses = []
        self.count = 0
        self.progress_interval = 50000
    
    def add_address(self, tags, lat, lon, osm_id, osm_type):
        addr = {}
        for tag in tags:
            if tag.k.startswith('addr:'):
                key = tag.k[5:]
                addr[key] = tag.v
        
        if not addr.get('street') or not addr.get('housenumber'):
            return
        
        self.addresses.append({
            'street': addr.get('street', ''),
            'house_number': addr.get('housenumber', ''),
            'city': addr.get('city', addr.get('town', addr.get('village', addr.get('hamlet', '')))),
            'postcode': addr.get('postcode', ''),
            'latitude': lat,
            'longitude': lon,
            'osm_id': osm_id,
            'osm_type': osm_type,
            'suburb': addr.get('suburb', ''),
            'state_district': addr.get('state_district', '')
        })
        
        self.count += 1
        if self.count % self.progress_interval == 0:
            print(f'  Found {self.count} addresses so far...', flush=True)
    
    def node(self, n):
        if any(tag.k.startswith('addr:') for tag in n.tags):
            self.add_address(n.tags, n.location.lat, n.location.lon, n.id, 'node')
    
    def way(self, w):
        if any(tag.k.startswith('addr:') for tag in w.tags):
            lat_sum = 0.0
            lon_sum = 0.0
            count = 0
            for node in w.nodes:
                if node.location.valid():
                    lat_sum += node.location.lat
                    lon_sum += node.location.lon
                    count += 1
            if count > 0:
                lat = lat_sum / count
                lon = lon_sum / count
                self.add_address(w.tags, lat, lon, w.id, 'way')

def extract_addresses(osm_file):
    print(f'Parsing OSM file: {osm_file}')
    handler = AddressExtractor()
    
    try:
        handler.apply_file(osm_file, locations=True, idx='sparse_mem_array')
    except Exception as e:
        print(f'Error parsing OSM file: {e}', file=sys.stderr)
        sys.exit(1)
    
    print(f'\nTotal addresses found: {len(handler.addresses)}')
    
    if not handler.addresses:
        print('No addresses found. Check that the OSM file contains addr:* tags.', file=sys.stderr)
        sys.exit(1)
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    print(f'Writing to {OUTPUT_FILE}...')
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'street', 'house_number', 'city', 'postcode', 
            'latitude', 'longitude', 'osm_id', 'osm_type',
            'suburb', 'state_district'
        ])
        writer.writeheader()
        writer.writerows(handler.addresses)
    
    file_size = os.path.getsize(OUTPUT_FILE) / (1024**2)
    print(f'Export complete: {OUTPUT_FILE} ({file_size:.1f} MB)')
    print(f'Total addresses exported: {len(handler.addresses)}')
    
    return OUTPUT_FILE

if __name__ == '__main__':
    osm_file = os.path.join(DATA_DIR, 'italy-latest.osm.pbf')
    if not os.path.exists(osm_file):
        print(f'OSM file not found: {osm_file}', file=sys.stderr)
        print('Run download_osm.py first.', file=sys.stderr)
        sys.exit(1)
    
    extract_addresses(osm_file)
