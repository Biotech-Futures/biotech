# BIOTech Futures Backend

Django 5.2 service that powers the BIOTech Futures Mentoring Platform. It exposes REST APIs for user onboarding, group coordination, mentoring resources, events, tasks, and notification workflows, and issues session-based authentication used by the Vue frontend.

## Prerequisites
- Python 3.11+ (Django 5.2 requires Python ≥ 3.10)
- pip, virtualenv (or `python -m venv`)
- PostgreSQL (for production) or SQLite (for local development)

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt

python manage.py migrate         # apply database migrations
python manage.py createsuperuser # optional, admin access
python manage.py runserver       # http://localhost:8000
```
The backend is configured for Django session authentication. Use the services endpoints (`/services/send-login-code/` and `/services/magic/`) to drive magic-link login for the frontend or sign in through the Django admin.

## Configuration
Key settings live in `config/settings.py`. Update these before deploying outside of a local sandbox.

| Setting | Purpose | Notes |
| ------- | ------- | ----- |
| `SECRET_KEY` | Cryptographic signing key | Replace with a secure value in production. |
| `DEBUG` | Enables dev/debug behaviour | Set to `False` outside development. |
| `ALLOWED_HOSTS` | Domains allowed to serve requests | Add your server/domain; empty list blocks non-local requests. |
| `DATABASES["default"]` | Database connection | Defaults to BIOTech Azure Postgres. Uncomment the SQLite block for local development or provide your own Postgres credentials via environment overrides. |
| `AZURE_ACCOUNT_NAME`, `AZURE_ACCOUNT_KEY`, `AZURE_CONTAINER` | Azure Blob Storage config | Used by `django-storages` for media uploads (`DEFAULT_FILE_STORAGE`). Provide real values or swap to local storage if Azure is not available. |
| `EMAIL_BACKEND`, `EMAIL_HOST_*` | Outbound email | Default is console backend. Enable SMTP (e.g. Mailtrap sandbox) for OTP delivery. |
| `MAGIC_LINK_REDIRECT_URL` | Frontend callback URL after login | Must correspond to the SPA route handling `/auth/callback`. |
| `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` | Frontend communication | Include every URL the frontend is served from (e.g. staging domains). |
| Session cookie settings | `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`, etc. | Lock down appropriately when deploying over HTTPS. |

> Tip: Keep sensitive production secrets out of version control by exporting environment variables before starting Django (e.g. via a `.env` loader such as `python-dotenv`) and reading them in `settings.py`.

## Core Apps & Routes
All apps are namespaced under `apps/`:
- `apps.users` – user profiles, roles, onboarding forms, `GET /api/v1/users/me/`.
- `apps.resources` – resource library, role management, and access control (`/resources/resource-files/`, `/resources/roles/`).
- `apps.groups` – student groups, tracks, and supervisors (`/groups/`).
- `apps.events` – event scheduling and invite management (`/events/v1/`, invite endpoints).
- `apps.tasks` – task assignments and status tracking.
- `apps.chat` – chat room infrastructure (Channels-based).
- `apps.services` – magic-link login, email previews, logout endpoints under `/services/`.
- `apps.certificates`, `apps.workshops`, `apps.integrations`, `apps.user_sessions`, `matching` – supporting modules for mentoring and reporting workflows.

### API discovery
- OpenAPI schema: `GET /api/schema/`
- Swagger UI: `http://localhost:8000/api/docs/`
- Redoc: `http://localhost:8000/api/redoc/`

## Magic-Link Authentication
1. `POST /services/send-login-code/` with `{"email": "...", "redirect_url": "http://localhost:5173/#/auth/callback"}`.
2. User receives an email (console output by default) containing a link to `/services/magic/?email=...&code=...`.
3. Visiting the link logs the user in (session cookie) and redirects to the configured frontend callback.
4. Optional: `/services/verify-login-code/` can OTP-login without following the link (responds with user payload).
To switch from console email to SMTP, set `EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"` and provide valid Mailtrap (or other) credentials.

## Storage & Static Assets
- Media uploads use Azure Blob Storage via `django-storages`. Configure Azure credentials or replace `DEFAULT_FILE_STORAGE` with Django’s default for local development.
- Static files are currently served from app directories (`STATIC_URL = "static/"`). Run `python manage.py collectstatic` during deployment.

## Database
- Default configuration targets the BIOTech Azure PostgreSQL instance. For local prototyping uncomment the SQLite block in `settings.py` (or change `DATABASES` at runtime).
- `schema.yaml` documents ER diagrams and relationships.
- `table_statements.sql` contains SQL DDL snapshots for reference.

## Testing
- Run Django’s test suite: `python manage.py test`
- Additional pytest-style fixtures live in `conftest.py`.
- `test_blob_upload.py` and other module tests exercise Azure storage and service layers; some tests expect configured credentials or may need to be skipped in offline environments.

## Utilities
- `python manage.py createsuperuser` – create admin login for `/admin/`.
- `python manage.py loaddata <fixture>` – load JSON/YAML fixtures if provided.
- `python manage.py shell_plus` – recommended via `django-extensions` (install manually) for interactive work.
- `check_resource_status.py`, `check_role_status.py` – helper scripts to inspect Azure resources/roles.

## Local Development Tips
- If you run the backend and frontend on different hosts or ports, mirror those origins in the CORS/CSRF settings and restart Django.
- Session cookies are HTTP-only; use the browser devtools Application tab to confirm they are set.
- For debugging email templates, visit `/services/test-email/` or `/services/test-email-preview/` to preview rendered HTML.
