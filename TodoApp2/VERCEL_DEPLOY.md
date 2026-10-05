# Deploying Daymark on Vercel

## Project settings

Set the Vercel Root Directory to the folder containing `main.py`, `requirements.txt`, `templates/`, and `static/`. Vercel's FastAPI preset detects the root `main.py` application, so this project does not need an extra API wrapper or catch-all rewrite. `.python-version` selects Python 3.12.

## Environment variables

Add these in Vercel Project Settings under Environment Variables for every environment you deploy:

- `SQLALCHEMY_DATABASE_URL`: a persistent PostgreSQL connection URL from your database provider. `DATABASE_URL` is also accepted. Prefer the provider's pooled URL for serverless connections.
- `SECRET_KEY`: a long, random signing secret. Keep it private and do not reuse the example value.
- `ALGORITHM`: `HS256`.

Vercel does not read your local `.env` file. The `.env.example` file documents names only; never commit `.env` or put production credentials in source control. Do not use `todos.db` as production storage because Vercel function filesystems are not persistent.

## Database migration

Before routing production traffic to this version, run the migration once against the same PostgreSQL database configured in Vercel. Install the migration tooling locally with `pip install -r requirements-dev.txt`, then run:

```powershell
$env:SQLALCHEMY_DATABASE_URL = '<your-postgres-connection-url>'
alembic upgrade head
```

The application no longer creates tables during function import. Running migrations separately avoids database DDL during Vercel cold starts and supports both fresh databases and databases previously initialized by `create_all`.

## Deploy

Connect the repository in Vercel and deploy with the Root Directory set as above. The existing FastAPI mount serves the templates' `/static` assets; Vercel includes mounted static directories in the function bundle and can promote them to its CDN.
