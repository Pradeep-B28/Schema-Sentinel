-- Create users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Add a column to orders
ALTER TABLE orders ADD COLUMN status VARCHAR(50) DEFAULT 'pending';

-- Create an index
CREATE INDEX idx_users_email ON users (email);

-- Drop a table (risky!)
DROP TABLE IF EXISTS temp_logs;

-- Add a foreign key constraint
ALTER TABLE orders ADD CONSTRAINT fk_orders_user_id FOREIGN KEY (user_id) REFERENCES users(id);

-- Rename a table
RENAME TABLE old_data TO archived_data;

-- This is a comment, not an operation