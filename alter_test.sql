-- Adding nullable column (low risk)
ALTER TABLE users ADD COLUMN phone_number VARCHAR(20);

-- Adding NOT NULL column without default (HIGH RISK)
ALTER TABLE orders ADD COLUMN status_code INT NOT NULL;

-- Adding NOT NULL column with default (low risk)
ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE;

-- Dropping column (HIGH RISK)
ALTER TABLE users DROP COLUMN phone_number;

-- Changing data type (HIGH RISK)
ALTER TABLE orders ALTER COLUMN total TYPE DECIMAL(15,2);

-- Renaming column (HIGH RISK)
ALTER TABLE users RENAME COLUMN name TO full_name;

-- Adding foreign key (HIGH RISK)
ALTER TABLE orders ADD CONSTRAINT fk_orders_user FOREIGN KEY (user_id) REFERENCES users(id);

-- Dropping constraint (HIGH RISK)
ALTER TABLE orders DROP CONSTRAINT fk_orders_user;