import psycopg2
import csv
import os
import sys
from psycopg2.extras import execute_values
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
ADDRESSES_CSV = os.path.join(DATA_DIR, 'addresses.csv')
SCHEMA_SQL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
PROVINCES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provinces.csv')

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
    
    with conn.cursor() as cur:
        cur.execute('SELECT id, code FROM provinces')
        province_map = {code: pid for pid, code in cur.fetchall()}
        
        cur.execute('SELECT id, name, province_code FROM cities')
        city_cache = {(name, prov): cid for cid, name, prov in cur.fetchall()}
        
        cur.execute('SELECT id, name, city_id FROM streets')
        street_cache = {(name, city_id): sid for sid, name, city_id in cur.fetchall()}
    
    cities_to_insert = []
    streets_to_insert = []
    addresses_to_insert = []
    
    count = 0
    batch_size = 10000
    
    with open(ADDRESSES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            city_name = row['city'].strip()
            province_code = row['state_district'].strip() if row.get('state_district') else None
            
            if not city_name:
                continue
            
            if province_code and province_code not in province_map:
                province_code = None
            
            city_key = (city_name, province_code)
            if city_key not in city_cache:
                cities_to_insert.append((city_name, province_code))
                city_id = None
            else:
                city_id = city_cache[city_key]
            
            street_name = row['street'].strip()
            street_key = (street_name, city_id)
            if street_key not in street_cache and city_id:
                streets_to_insert.append((street_name, city_id))
                street_id = None
            elif city_id:
                street_id = street_cache[street_key]
            else:
                street_id = None
            
            addresses_to_insert.append((
                street_id,
                row['house_number'].strip(),
                city_id,
                row['postcode'].strip(),
                province_code,
                row['latitude'],
                row['longitude'],
                int(row['osm_id']),
                row['osm_type']
            ))
            
            count += 1
            if count % 50000 == 0:
                print(f'  Processed {count} rows...', flush=True)
    
    print(f'\nTotal rows to process: {count}')
    print(f'  New cities: {len(cities_to_insert)}')
    print(f'  New streets: {len(streets_to_insert)}')
    print(f'  New addresses: {len(addresses_to_insert)}')
    
    with conn.cursor() as cur:
        if cities_to_insert:
            print('Inserting cities...')
            execute_values(
                cur,
                '''INSERT INTO cities (name, province_code) 
                   VALUES %s 
                   ON CONFLICT (name, province_code) DO NOTHING''',
                cities_to_insert,
                page_size=1000
            )
            conn.commit()
            
            cur.execute('SELECT id, name, province_code FROM cities')
            city_cache.clear()
            city_cache = {(name, prov): cid for cid, name, prov in cur.fetchall()}
        
        if streets_to_insert:
            print('Inserting streets...')
            street_batch = []
            for street_name, city_id in streets_to_insert:
                if city_id:
                    street_batch.append((street_name, city_id))
            
            if street_batch:
                execute_values(
                    cur,
                    '''INSERT INTO streets (name, city_id) 
                       VALUES %s 
                       ON CONFLICT (name, city_id) DO NOTHING''',
                    street_batch,
                    page_size=1000
                )
                conn.commit()
                
                cur.execute('SELECT id, name, city_id FROM streets')
                street_cache.clear()
                street_cache = {(name, city_id): sid for sid, name, city_id in cur.fetchall()}
        
        print('Inserting addresses...')
        address_batch = []
        for street_id, house_number, city_id, postcode, province_code, lat, lon, osm_id, osm_type in addresses_to_insert:
            if street_id and city_id:
                address_batch.append((
                    street_id, house_number, city_id, postcode,
                    province_code, lat, lon, osm_id, osm_type
                ))
        
        for i in range(0, len(address_batch), batch_size):
            batch = address_batch[i:i+batch_size]
            execute_values(
                cur,
                '''INSERT INTO addresses 
                   (street_id, house_number, city_id, postcode, province_code, latitude, longitude, osm_id, osm_type) 
                   VALUES %s 
                   ON CONFLICT (street_id, house_number, city_id) DO NOTHING''',
                batch,
                page_size=1000
            )
            conn.commit()
            print(f'  Inserted {min(i+batch_size, len(address_batch))}/{len(address_batch)} addresses...', flush=True)
    
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
