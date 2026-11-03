CREATE DATABASE IF NOT EXISTS web_metadata_db;
USE web_metadata_db;

-- Assume that we geoblock countries only
INSERT IGNORE INTO countries (country, is_banned)
SELECT country, MAX(is_banned)
FROM old_requests
WHERE country IS NOT NULL AND country != ''
GROUP BY country;

-- fill in ip address and its associated country
INSERT IGNORE INTO ip_locations (client_ip, country)
SELECT DISTINCT client_ip, country
FROM old_requests
WHERE client_ip IS NOT NULL AND country IS NOT NULL;

-- Step 3: Migrate client profiles into `clients`
INSERT INTO requests (id, client_ip, gender, age_range, income, requested_file, time_of_day)
SELECT id, client_ip, gender, age_range, income, requested_file, time_of_day
FROM old_requests;