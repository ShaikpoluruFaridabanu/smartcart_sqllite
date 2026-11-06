# SmartCart deployment and security notes

## Configuration
- Copy `.env.example` to `.env` for local development.
- Set a unique `SMARTCART_SECRET_KEY`.
- Set `MAIL_USERNAME` and a newly generated Gmail App Password.
- Set `RAZORPAY_KEY_ID` and a newly generated Razorpay secret.
- Never commit `.env`.

Generate a secret key with:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

On PythonAnywhere, set the same variables in the WSGI file before importing `app`.
Set `SESSION_COOKIE_SECURE=true` on the HTTPS site.

## Database and uploads
- `smartcart.db` is runtime data and is intentionally excluded from this source archive.
- Keep a separate backup of the production SQLite database before deployment.
- Product/profile images under `static/uploads/` are retained in this archive.

## Git safety
The old Git history included credentials in `config.py` and tracked the SQLite database.
Rotating the exposed credentials is mandatory. Removing `config.py` secrets in a new commit
does not erase old values from earlier Git commits. If the repository is public, rewrite
Git history to purge the old `config.py` and database before pushing, or create a new
repository with a clean history. Coordinate any force-push with collaborators.
