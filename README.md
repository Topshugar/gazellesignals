# Gazelle Signals

The Flask app stores registrations in the configured database (`DATABASE_URL`). Passwords are hashed before they are saved. No trading or security keys are required by the application.

## Render environment variables

Set these values in Render (never commit them to GitHub):

- `DATABASE_URL` — your Render PostgreSQL connection string.
- `SECRET_KEY` — a long random value used to protect login sessions.
- `ADMIN_EMAIL` — the administrator email used to create the first admin account.
- `ADMIN_PASSWORD` — the administrator password used once to bootstrap that account.
- `RENDER=true`

The first deployment creates the admin account in the `admins` table. Open `/admin/login` to view all registrations stored in the database. The application does not store trading keys or security keys.

Render uses the included `Procfile` and starts `wsgi:app`, which enables the admin routes.
