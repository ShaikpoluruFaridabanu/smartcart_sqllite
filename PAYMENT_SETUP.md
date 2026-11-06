# SmartCart payment setup

1. Copy `.env.example` to `.env` in the same folder as `app.py`.
2. Set your MySQL password, Flask secret, and current Razorpay **test-mode** Key ID and Key Secret in `.env`. Do not commit `.env` to GitHub.
3. Install `python-dotenv` if it is not already installed: `pip install python-dotenv`.
4. Open MySQL Workbench, select `smartcart_db`, back up the database, then run `payment_schema.sql`.
5. If `orders` or `order_items` already exist, `CREATE TABLE IF NOT EXISTS` will not modify them. Compare their columns with `payment_schema.sql`; add missing columns after taking a backup. The Flask payment route expects the listed columns.
6. Restart Flask and test with Razorpay test-mode credentials and test payment details. Do not use real customer payments while testing.

## What changed

- Payment verification now attempts to capture a Razorpay payment if its status is `authorized`, then verifies it is `captured`.
- Detailed traceback information is printed to the Flask terminal when order recording fails. The cart/session is retained and the user is warned not to pay again until the payment is reconciled.
- The payment button handles a blocked/missing Razorpay checkout script and resets on dismissal/failure.
- The stylesheet now uses a warm ivory, deep teal and amber-inspired visual refresh while retaining existing template class names.

## Important credential note

The uploaded project contained live-looking email and Razorpay credentials. Rotate/revoke those credentials and use newly generated credentials in your local `.env` file.
