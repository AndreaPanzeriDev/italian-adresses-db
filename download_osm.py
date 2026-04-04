import urllib.request
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
OSM_URL = 'https://download.geofabrik.de/europe/italy-latest.osm.pbf'
OSM_FILE = os.path.join(DATA_DIR, 'italy-latest.osm.pbf')

def download_osm():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    if os.path.exists(OSM_FILE):
        size_gb = os.path.getsize(OSM_FILE) / (1024**3)
        print(f'File already exists: {OSM_FILE} ({size_gb:.2f} GB)')
        response = input('Redownload? (y/N): ')
        if response.lower() != 'y':
            return OSM_FILE
    
    print(f'Downloading Italy OSM data from Geofabrik...')
    print(f'URL: {OSM_URL}')
    
    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(100, (downloaded / total_size) * 100)
            mb = downloaded / (1024 * 1024)
            total_mb = total_size / (1024 * 1024)
            print(f'\rProgress: {percent:.1f}% ({mb:.1f} MB / {total_mb:.1f} MB)', end='', flush=True)
    
    try:
        urllib.request.urlretrieve(OSM_URL, OSM_FILE, reporthook=report_progress)
        print()
        size_gb = os.path.getsize(OSM_FILE) / (1024**3)
        print(f'Download complete: {OSM_FILE} ({size_gb:.2f} GB)')
    except Exception as e:
        print(f'\nError downloading: {e}', file=sys.stderr)
        sys.exit(1)
    
    return OSM_FILE

if __name__ == '__main__':
    download_osm()
