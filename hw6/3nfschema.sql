CREATE DATABASE IF NOT EXISTS web_metadata_db;
USE web_metadata_db;

-- 1: Country->is banned?// country tells us if it would be banned or not
CREATE TABLE IF NOT EXISTS countries (
    country VARCHAR(100) PRIMARY KEY,
    is_banned BOOLEAN DEFAULT FALSE,
    INDEX idx_country_banned (is_banned)
);
-- 2: IP-> country // IP can tell us country, up to 99 percent correctness, so we can treat as relation
CREATE TABLE IF NOT EXISTS ip_locations (
    client_ip VARCHAR(45) PRIMARY KEY,
    country VARCHAR(100),
    FOREIGN KEY (country) REFERENCES countries(country) ON UPDATE CASCADE
);
-- 3: no element relies on the other, it is in 3NF
CREATE TABLE IF NOT EXISTS requests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    client_ip VARCHAR(45),
    gender VARCHAR(20),
    age_range VARCHAR(50),
    income VARCHAR(50),
    requested_file VARCHAR(255),
    time_of_day DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (client_ip) REFERENCES ip_locations(client_ip) ON UPDATE CASCADE
);
-- 4: Failed requests table already in 3NF
CREATE TABLE IF NOT EXISTS failed_requests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    time_of_request DATETIME DEFAULT CURRENT_TIMESTAMP,
    requested_file VARCHAR(255),
    error_code INT NOT NULL,
	INDEX idx_error_code (error_code)
);