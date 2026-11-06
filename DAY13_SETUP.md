# SmartCart Day-13: Payment Verification and Orders

This update follows the uploaded Day-13 notes and integrates with the existing SmartCart cart, selected-item checkout, delivery address, and Razorpay page.

## Included

- `/verify-payment` endpoint (the older `/payment-success` endpoint remains as a compatibility alias).
- Server-side Razorpay signature verification and payment fetch/capture status checks.
- Amount, currency, and Razorpay order-ID validation.
- `orders` and `order_items` persistence using one MySQL transaction (`commit` / `rollback`).
- Duplicate callback protection using Razorpay order/payment IDs.
- Cart cleanup only after an order is committed; only purchased quantities are removed.
- `/user/order-success/<order_id>` order confirmation/detail page.
- `/user/my-orders` page for the logged-in customer, with links to each order's details.
- Customer ownership checks when reading order details.

## Database setup

1. Back up `smartcart_db`.
2. Open MySQL Workbench and select `smartcart_db`.
3. Run `payment_schema.sql`. It creates the order tables if they do not already exist.
4. If these tables existed before this update, `CREATE TABLE IF NOT EXISTS` will not alter them. Compare their columns with `payment_schema.sql` and add missing columns carefully; do not drop existing customer/order data.
5. The Day-13 handout defines foreign keys to `users(user_id)` and `products(product_id)`. Run `payment_foreign_keys.sql` only after checking `SHOW CREATE TABLE` and confirming each parent/child ID column has the same integer type and signedness. If MySQL reports a type mismatch, align the child column type to the parent column before adding that constraint.

## Razorpay setup

- Configure `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` in `.env` using Razorpay test-mode credentials.
- Keep `.env` out of GitHub.
- Install project dependencies in your virtual environment (including `Flask`, `mysql-connector-python`, `Flask-Mail`, `bcrypt`, `razorpay`, and `python-dotenv`).
- Restart Flask after changing `.env`.

## Test flow

1. Log in as a customer and add products to the cart.
2. Select the products to purchase and save a valid delivery address.
3. Open the Razorpay checkout and complete a test-mode payment.
4. Confirm that one row is inserted into `orders` and the corresponding rows are inserted into `order_items`.
5. Confirm that only the purchased cart quantities are removed.
6. Open **My Orders**, then **View Order Details**.
7. Refresh the success page or retry the callback; it must not create a duplicate order.

## Important

The app cannot be tested against your local MySQL database or Razorpay account from this workspace. Run the test flow locally. If an order is paid at Razorpay but a database write fails, the app retains the cart, logs the traceback in the Flask terminal, and displays the payment ID. Do not pay again until that payment is reconciled.
