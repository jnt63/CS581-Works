CREATE DATABASE IF NOT EXISTS web_metadata_db;
USE web_metadata_db;

-- table for successful requests, 200
CREATE TABLE IF NOT EXISTS requests (
-- id serves as primary key 
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    country VARCHAR(100),
    client_ip VARCHAR(45),
    gender VARCHAR(20),
    age_range VARCHAR(50),
    income VARCHAR(50),
    is_banned BOOLEAN DEFAULT FALSE,
    time_of_day DATETIME DEFAULT CURRENT_TIMESTAMP,
    requested_file VARCHAR(255),
    INDEX idx_country (country),
    INDEX idx_gender (gender),
    INDEX idx_banned (is_banned)
);

-- table for failed requests, not 200
CREATE TABLE IF NOT EXISTS failed_requests (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    time_of_request DATETIME DEFAULT CURRENT_TIMESTAMP,
    requested_file VARCHAR(255),
    error_code INT NOT NULL,
	INDEX idx_error_code (error_code)
);

