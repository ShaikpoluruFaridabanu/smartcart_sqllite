-- Migration: Foreign Key Relationship between Admin and Products
-- Ensures products are tied to the admin who created them and enforces
-- referential integrity and isolation between different admin accounts.

-- For MySQL:
-- 1. Ensure admin_id exists in products:
-- ALTER TABLE products ADD COLUMN IF NOT EXISTS admin_id INT;

-- 2. Add foreign key constraint:
ALTER TABLE products
  ADD CONSTRAINT fk_products_admin
  FOREIGN KEY (admin_id) REFERENCES admin(admin_id)
  ON UPDATE CASCADE ON DELETE CASCADE;

-- 3. Add index for fast admin-scoped product lookups:
CREATE INDEX idx_products_admin_id ON products(admin_id);

