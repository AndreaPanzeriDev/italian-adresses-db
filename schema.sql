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
    UNIQUE(name, city_id)
);

-- Main addresses table
CREATE TABLE IF NOT EXISTS addresses (
    id SERIAL PRIMARY KEY,
    street_id INTEGER REFERENCES streets(id),
    house_number VARCHAR(20),
    city_id INTEGER REFERENCES cities(id),
    postcode VARCHAR(5),
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
JOIN provinces p ON a.province_code = p.code;
