-- Italian Addresses Database Schema

-- Provinces table (ISTAT codes)
CREATE TABLE IF NOT EXISTS provinces (
    code VARCHAR(2) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    region VARCHAR(100) NOT NULL
);

-- Cities/Comuni table
CREATE TABLE IF NOT EXISTS cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    province_code VARCHAR(2) REFERENCES provinces(code),
    istat_code VARCHAR(6),
    UNIQUE(name, province_code)
);

-- Streets table (normalized to avoid duplication)
CREATE TABLE IF NOT EXISTS streets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(300) NOT NULL,
    city_id INTEGER REFERENCES cities(id),
    province_code VARCHAR(2),
    UNIQUE(name, city_id)
);

-- Main addresses table
CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    street_id INTEGER REFERENCES streets(id),
    house_number VARCHAR(255),
    city_id INTEGER REFERENCES cities(id),
    postcode VARCHAR(50),
    province_code VARCHAR(2) REFERENCES provinces(code),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    osm_id BIGINT,
    osm_type VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(street_id, house_number, city_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_addresses_postcode ON addresses(postcode);
CREATE INDEX IF NOT EXISTS idx_addresses_city ON addresses(city_id);
CREATE INDEX IF NOT EXISTS idx_addresses_province ON addresses(province_code);
CREATE INDEX IF NOT EXISTS idx_addresses_coords ON addresses(latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_streets_name ON streets(name);
CREATE INDEX IF NOT EXISTS idx_streets_province ON streets(province_code);
CREATE INDEX IF NOT EXISTS idx_cities_name ON cities(name);

-- View for easy address queries
CREATE OR REPLACE VIEW v_addresses AS
SELECT 
    a.id,
    s.name AS street,
    a.house_number,
    c.name AS city,
    a.postcode AS cap,
    p.code AS province,
    p.name AS province_name,
    a.latitude,
    a.longitude
FROM addresses a
JOIN streets s ON a.street_id = s.id
JOIN cities c ON a.city_id = c.id
LEFT JOIN provinces p ON a.province_code = p.code;


-- ISP Providers lookup
CREATE TABLE IF NOT EXISTS providers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) NOT NULL UNIQUE
);

-- Connection technology types lookup
CREATE TABLE IF NOT EXISTS connection_technologies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    slug VARCHAR(50) NOT NULL UNIQUE,
    rank SMALLINT NOT NULL DEFAULT 99
);

-- ISP coverage per address (one row per address per provider)
CREATE TABLE IF NOT EXISTS address_provider_coverage (
    id SERIAL PRIMARY KEY,
    address_id INTEGER NOT NULL REFERENCES addresses(id) ON DELETE CASCADE,
    provider_id INTEGER NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    technology_id INTEGER REFERENCES connection_technologies(id),
    covered BOOLEAN NOT NULL DEFAULT false,
    max_download_mbps NUMERIC(10,2),
    max_upload_mbps NUMERIC(10,2),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(address_id, provider_id)
);

-- Coverage indexes
CREATE INDEX IF NOT EXISTS idx_coverage_address ON address_provider_coverage(address_id);
CREATE INDEX IF NOT EXISTS idx_coverage_provider ON address_provider_coverage(provider_id);
CREATE INDEX IF NOT EXISTS idx_coverage_technology ON address_provider_coverage(technology_id);
CREATE INDEX IF NOT EXISTS idx_coverage_covered ON address_provider_coverage(covered);

-- Seed providers
INSERT INTO providers (name, slug) VALUES
    ('OpenFiber', 'openfiber'),
    ('FiberCop', 'fibercop'),
    ('FastWeb', 'fastweb')
ON CONFLICT (slug) DO NOTHING;

-- Seed connection technologies (ordered by quality)
INSERT INTO connection_technologies (name, slug, rank) VALUES
    ('FTTH', 'ftth', 1),
    ('FTTC', 'fttc', 2),
    ('FWA', 'fwa', 3),
    ('ADSL', 'adsl', 4)
ON CONFLICT (slug) DO NOTHING;

-- Flattened view: addresses with their ISP coverage
CREATE OR REPLACE VIEW v_addresses_coverage AS
SELECT
    a.id,
    s.name AS street,
    a.house_number,
    c.name AS city,
    a.postcode AS cap,
    p.code AS province,
    p.name AS province_name,
    a.latitude,
    a.longitude,
    prov.name AS provider_name,
    prov.slug AS provider_slug,
    apc.covered,
    ct.name AS technology,
    ct.slug AS technology_slug,
    apc.max_download_mbps,
    apc.max_upload_mbps,
    apc.updated_at AS coverage_updated_at
FROM addresses a
JOIN streets s ON a.street_id = s.id
JOIN cities c ON a.city_id = c.id
LEFT JOIN provinces p ON a.province_code = p.code
LEFT JOIN address_provider_coverage apc ON apc.address_id = a.id
LEFT JOIN providers prov ON apc.provider_id = prov.id
LEFT JOIN connection_technologies ct ON apc.technology_id = ct.id;
