import psycopg2
import csv
import os
import sys
import re
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

CAP_PROVINCE_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cap_province.csv')
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ADDRESSES_CSV = os.path.join(DATA_DIR, 'addresses.csv')
SCHEMA_SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
PROVINCES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provinces.csv')

def load_cap_province_mapping():
    mapping = {}
    with open(CAP_PROVINCE_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mapping[row['cap_prefix']] = row['province_code']
    return mapping

def get_province_from_postcode(postcode, cap_mapping):
    if not postcode:
        return None
    postcode = postcode.strip()
    match = re.match(r'^(\d{5})', postcode)
    if match:
        prefix = match.group(1)[:2]
        return cap_mapping.get(prefix)
    return None

def sanitize_postcode(postcode):
    if not postcode:
        return None
    postcode = postcode.strip()
    match = re.match(r'^(\d{5})', postcode)
    if match:
        return match.group(1)
    return None

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=os.getenv('PGDATABASE'),
            user=os.getenv('PGUSER'),
            password=os.getenv('PGPASSWORD'),
            host=os.getenv('PGHOST'),
            port=int(os.getenv('PGPORT', '5432'))
        )
        return conn
    except Exception as e:
        print(f'Error connecting to database: {e}', file=sys.stderr)
        print('\nCreate a .env file with your DB credentials:', file=sys.stderr)
        print('  PGHOST=your-host\n  PGPORT=5432\n  PGDATABASE=your-db\n  PGUSER=your-user\n  PGPASSWORD=your-password', file=sys.stderr)
        sys.exit(1)

def init_schema(conn):
    print('Creating database schema...')
    with open(SCHEMA_SQL, 'r') as f:
        with conn.cursor() as cur:
            cur.execute(f.read())
    conn.commit()
    print('Schema created.')

def load_provinces(conn):
    print('Loading provinces...')
    with open(PROVINCES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        provinces = [(row['code'], row['name'], row['region']) for row in reader]
    
    with conn.cursor() as cur:
        execute_values(
            cur,
            'INSERT INTO provinces (code, name, region) VALUES %s ON CONFLICT (code) DO NOTHING',
            provinces
        )
    conn.commit()
    print(f'Loaded {len(provinces)} provinces.')

def load_addresses(conn):
    print('Loading addresses...')
    
    if not os.path.exists(ADDRESSES_CSV):
        print(f'CSV file not found: {ADDRESSES_CSV}', file=sys.stderr)
        sys.exit(1)
    
    cap_mapping = load_cap_province_mapping()
    
    with conn.cursor() as cur:
        cur.execute('SELECT code FROM provinces')
        province_map = {row[0] for row in cur.fetchall()}
        
        cur.execute('SELECT id, name, province_code FROM cities')
        city_cache = {(name, prov): cid for cid, name, prov in cur.fetchall()}
        
        cur.execute('SELECT id, name, city_id, province_code FROM streets')
        street_cache = {(name, city_id): sid for sid, name, city_id, prov in cur.fetchall()}
    
    cities_to_insert = set()
    
    with open(ADDRESSES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_name = row['city'].strip()
            
            if not city_name:
                continue
            
            province_code = get_province_from_postcode(row.get('postcode'), cap_mapping)
            if province_code and province_code not in province_map:
                province_code = None
            
            city_key = (city_name, province_code)
            if city_key not in city_cache:
                cities_to_insert.add(city_key)
    
    print(f'  New cities to insert: {len(cities_to_insert)}')
    
    if cities_to_insert:
        print('Inserting cities...')
        with conn.cursor() as cur:
            execute_values(
                cur,
                '''INSERT INTO cities (name, province_code) 
                   VALUES %s 
                   ON CONFLICT (name, province_code) DO NOTHING''',
                list(cities_to_insert),
                page_size=1000
            )
        conn.commit()
        
        with conn.cursor() as cur:
            cur.execute('SELECT id, name, province_code FROM cities')
            city_cache = {(name, prov): cid for cid, name, prov in cur.fetchall()}
    
    streets_to_insert = set()
    
    with open(ADDRESSES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_name = row['city'].strip()
            
            if not city_name:
                continue
            
            province_code = get_province_from_postcode(row.get('postcode'), cap_mapping)
            if province_code and province_code not in province_map:
                province_code = None
            
            city_key = (city_name, province_code)
            city_id = city_cache.get(city_key)
            
            if city_id is None:
                continue
            
            street_name = row['street'].strip()
            street_key = (street_name, city_id)
            if street_key not in street_cache:
                streets_to_insert.add((street_name, city_id, province_code))
    
    print(f'  New streets to insert: {len(streets_to_insert)}')
    
    if streets_to_insert:
        print('Inserting streets...')
        with conn.cursor() as cur:
            execute_values(
                cur,
                '''INSERT INTO streets (name, city_id, province_code) 
                   VALUES %s 
                   ON CONFLICT (name, city_id) DO NOTHING''',
                list(streets_to_insert),
                page_size=1000
            )
        conn.commit()
        
        with conn.cursor() as cur:
            cur.execute('SELECT id, name, city_id, province_code FROM streets')
            street_cache = {(name, city_id): sid for sid, name, city_id, prov in cur.fetchall()}
    
    print('Inserting addresses...')
    batch_size = 10000
    address_batch = []
    count = 0
    
    with open(ADDRESSES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city_name = row['city'].strip()
            
            if not city_name:
                continue
            
            province_code = get_province_from_postcode(row.get('postcode'), cap_mapping)
            if province_code and province_code not in province_map:
                province_code = None
            
            city_key = (city_name, province_code)
            city_id = city_cache.get(city_key)
            
            if city_id is None:
                continue
            
            street_name = row['street'].strip()
            street_key = (street_name, city_id)
            street_id = street_cache.get(street_key)
            
            if street_id is None:
                continue
            
            address_batch.append((
                street_id,
                row['house_number'].strip(),
                city_id,
                sanitize_postcode(row['postcode']),
                province_code,
                row['latitude'],
                row['longitude'],
                int(row['osm_id']),
                row['osm_type']
            ))
            
            count += 1
            if count % 50000 == 0:
                print(f'  Processed {count} rows...', flush=True)
            
            if len(address_batch) >= batch_size:
                with conn.cursor() as cur:
                    execute_values(
                        cur,
                        '''INSERT INTO addresses 
                           (street_id, house_number, city_id, postcode, province_code, latitude, longitude, osm_id, osm_type) 
                           VALUES %s 
                           ON CONFLICT (street_id, house_number, city_id) DO NOTHING''',
                        address_batch,
                        page_size=1000
                    )
                conn.commit()
                address_batch = []
    
    if address_batch:
        with conn.cursor() as cur:
            execute_values(
                cur,
                '''INSERT INTO addresses 
                   (street_id, house_number, city_id, postcode, province_code, latitude, longitude, osm_id, osm_type) 
                   VALUES %s 
                   ON CONFLICT (street_id, house_number, city_id) DO NOTHING''',
                address_batch,
                page_size=1000
            )
        conn.commit()
    
    print(f'\nTotal rows processed: {count}')
    print('\nImport complete!')
    
    with conn.cursor() as cur:
        cur.execute('SELECT COUNT(*) FROM addresses')
        total = cur.fetchone()[0]
        print(f'Total addresses in database: {total}')

def main():
    print('=== Italian Addresses DB Import ===\n')
    
    conn = get_db_connection()
    
    try:
        init_schema(conn)
        load_provinces(conn)
        load_addresses(conn)
    except Exception as e:
        print(f'Error during import: {e}', file=sys.stderr)
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
