-- Fix legacy orders table columns so Day-13 checkout can persist orders cleanly
ALTER TABLE orders MODIFY COLUMN customer_name VARCHAR(150) NULL DEFAULT NULL;
ALTER TABLE orders MODIFY COLUMN address TEXT NULL DEFAULT NULL;
ALTER TABLE orders MODIFY COLUMN phone VARCHAR(20) NOT NULL;
ALTER TABLE orders MODIFY COLUMN city VARCHAR(100) NOT NULL;
ALTER TABLE orders MODIFY COLUMN state VARCHAR(100) NOT NULL;

-- Add created_at and profile_image to users table if not present
ALTER TABLE users ADD COLUMN created_at TIMESTAMP NULL DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE users ADD COLUMN profile_image VARCHAR(255) NULL DEFAULT NULL;

