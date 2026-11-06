-- Optional Day-13 relationship migration for SmartCart.
-- First inspect the actual ID types in your database:
SHOW CREATE TABLE users;
SHOW CREATE TABLE products;
SHOW CREATE TABLE orders;
SHOW CREATE TABLE order_items;

-- The child and parent ID columns must have the same integer type and signedness.
-- If orders.user_id and users.user_id match, run:
ALTER TABLE orders
  ADD CONSTRAINT fk_orders_user
  FOREIGN KEY (user_id) REFERENCES users(user_id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- If order_items.product_id and products.product_id match, run:
ALTER TABLE order_items
  ADD CONSTRAINT fk_order_items_product
  FOREIGN KEY (product_id) REFERENCES products(product_id)
  ON UPDATE CASCADE ON DELETE RESTRICT;

-- ON DELETE RESTRICT protects historical orders from being orphaned when a
-- customer account or product is deleted. Keep product_name/price/image as
-- snapshots in order_items so past purchases remain readable.
