# Development Runbook

## Purpose

This document explains how to run and test the current codebase in a development environment.

It covers:

- backend setup
- frontend setup
- how to get both services running together
- how to log in locally
- what works today
- what breaks today
- practical workarounds for local development

## Current State Summary

The repository does not currently ship with a clean, self-contained local development setup.

Important caveats:

- the main backend runtime uses `backend/config/settings.py`
- that settings file hardcodes Azure PostgreSQL and Azure Blob configuration
- the repo does not include a dedicated local settings module
- the frontend expects the backend at `http://localhost:8000`
- the frontend login page works best with OTP entry, not the current magic-link callback
- websocket chat depends on Channels, but `daphne` is not listed in `backend/requirements.txt`

Because of that, the easiest way to get the project running locally is:

1. use Python 3.10
2. create a local backend settings override
3. run Django on `localhost:8000`
4. run Vite on `localhost:5173`

## Recommended Local Dev Stack

| Component | Recommended local choice | Why |
|---|---|---|
| Python | 3.10 | The pinned backend dependencies install cleanly there; Python 3.13 caused install issues |
| Node.js | 20+ or 22+ | Matches the frontend engine declaration |
| Backend DB | local SQLite or local Postgres | Avoids relying on the hardcoded Azure DB |
| File storage | local filesystem | Avoids Azure Blob during dev |
| Email | console backend | OTP codes are visible directly in backend logs |
| Backend server | `runserver` for basic API work | Fastest dev loop |
| Frontend server | Vite dev server | Standard workflow already present |

## Repo Layout

```text
biotech/
├── backend/
│   ├── manage.py
│   ├── config/
│   ├── apps/
│   └── non-project/docs/
└── frontend/
    ├── package.json
    └── src/
```

## Prerequisites

Install the following on your machine:

- Python 3.10
- Node.js 20+ or 22+
- npm

Optional but useful:

- PostgreSQL if you want a local DB that better matches production
- `daphne` for websocket-first testing
- `pytest` if you want to run the legacy matching tests

## Backend: Local Setup

### 1. Create and activate a virtual environment

From the repo root:

```bash
cd backend
python3.10 -m venv .venv
source .venv/bin/activate
```

### 2. Install backend dependencies

```bash
pip install -r requirements.txt
```

Optional test/dev packages not currently pinned in `requirements.txt`:

```bash
pip install daphne pytest pytest-django
```

Notes:

- `daphne` is useful for Channels/websocket development
- `pytest` is needed because part of the repo uses pytest-style tests
- Python 3.13 is not recommended for this repo as-is

## Backend: Create a Local Settings Override

The main settings file points to Azure resources. For local development, create an untracked local settings file.

Suggested file:

`backend/config/settings_local.py`

Suggested contents:

```python
from .settings import *

# Dev-only secret
SECRET_KEY = "dev-only-not-for-production"

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# Use local SQLite for dev
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.local.sqlite3",
    }
}

# Use local file storage instead of Azure Blob
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
MEDIA_ROOT = BASE_DIR / "media"
MEDIA_URL = "/media/"

# Keep email local and visible in terminal
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Dev cookies
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# Local frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Dev callback
MAGIC_LINK_REDIRECT_URL = "http://localhost:5173/#/auth/callback"

# Channels dev config
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}
```

Recommended `.gitignore` entry:

```gitignore
backend/config/settings_local.py
backend/.venv/
backend/media/
```

## Backend: Database Setup

Run migrations using the local settings module:

```bash
python manage.py migrate --settings=config.settings_local
```

Create an admin user:

```bash
python manage.py createsuperuser --settings=config.settings_local
```

Optional system check:

```bash
python manage.py check --settings=config.settings_local
```

## Backend: Run the Development Server

Standard dev server:

```bash
python manage.py runserver 8000 --settings=config.settings_local
```

Backend URLs you will likely use first:

- `http://localhost:8000/api/docs/`
- `http://localhost:8000/admin/`
- `http://localhost:8000/services/send-login-code/`
- `http://localhost:8000/api/v1/users/me/`

### Notes on websockets

For basic API development, `runserver` is enough.

If you want to exercise websocket behavior more explicitly, install `daphne` and use:

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

## Frontend: Local Setup

### 1. Install dependencies

From the repo root:

```bash
cd frontend
npm ci
```

### 2. Run the Vite dev server

```bash
npm run dev
```

By default, the frontend will be available at:

- `http://localhost:5173`

The frontend currently assumes:

- backend base URL is `http://localhost:8000`
- session-cookie auth is used for API requests

## Running Frontend and Backend Together

Use two terminals.

### Terminal 1: backend

```bash
cd backend
source .venv/bin/activate
python manage.py runserver 8000 --settings=config.settings_local
```

### Terminal 2: frontend

```bash
cd frontend
npm ci
npm run dev
```

Open:

- `http://localhost:5173`

## Local Login Walkthrough

### Current working path

The most reliable local login path today is:

1. make sure the user already exists in the backend database
2. open the frontend login page
3. enter that email address
4. click `Send Login Link`
5. read the OTP code from the backend terminal output
6. enter the 6-digit OTP in the frontend
7. the frontend should call `/api/v1/users/me/` and route to `/dashboard`

### Why this works

- the backend currently uses the console email backend in development
- OTP emails are printed to the terminal instead of being sent externally
- manual OTP verification aligns with the current backend session flow

### Current magic-link caveat

The frontend `AuthCallbackPage` still expects JWT tokens in the callback URL, but the backend magic-link flow now creates a Django session and redirects with simple query parameters instead.

That means:

- manual OTP entry is the safer dev path
- magic-link callback is currently out of sync and may fail

## How to Create a Local User for Testing

### Option A: Django admin

1. create a superuser
2. log into `http://localhost:8000/admin/`
3. create a regular `User`
4. optionally create role assignments manually

### Option B: shell

```bash
python manage.py shell --settings=config.settings_local
```

Then:

```python
from apps.users.models import User
from apps.resources.models import Roles, RoleAssignmentHistory
from django.utils import timezone

u = User.objects.create_user(
    email="student@example.com",
    first_name="Dev",
    last_name="Student",
)

role, _ = Roles.objects.get_or_create(role_name="student")
RoleAssignmentHistory.objects.create(
    user=u,
    role=role,
    valid_from=timezone.now(),
)
```

After that, log in from the frontend using `student@example.com`.

## Backend Testing

## Basic smoke checks

```bash
python manage.py check --settings=config.settings_local
python manage.py showmigrations --settings=config.settings_local
```

## Django test suites

Run app-specific suites:

```bash
python manage.py test apps.users.tests --settings=config.settings_local
python manage.py test apps.resources.tests --settings=config.settings_local
python manage.py test apps.chat.tests --settings=config.settings_local
```

### Current caveats

- some tests were originally written assuming the Azure/Postgres setup
- some tests fail under local SQLite because of `Now()`-based model check constraints
- user endpoint tests currently expect stale URLs and may fail with 404s
- chat tests rely on constraints and test infra that are not yet cleanly portable

## Legacy matching tests

The `matching` app behaves more like a parallel/legacy project and uses pytest-style tests.

Run:

```bash
pytest backend/matching/tests -q
```

Current caveats:

- install `pytest` first
- install `pytest-django` if you want proper pytest Django integration
- some matching tests currently fail because model and import logic have drifted

## Frontend Testing

## Build

```bash
npm run build
```

This is the most reliable frontend verification command right now.

## Unit tests

```bash
npm run test:unit -- --run
```

Current caveat:

- at the time of writing, the frontend does not contain real Vitest test files, so this exits with "No test files found"

## End-to-end tests

```bash
npm run test:e2e -- --project=chromium
```

Current caveats:

- Playwright configuration may fail in restricted environments
- the committed E2E test still expects the default Vite starter heading and is stale relative to the current app

## Suggested Daily Dev Workflow

1. start backend with local settings
2. start frontend with Vite
3. use admin or shell to seed a test user and role
4. log in via manual OTP
5. work on one bounded area at a time:
   - auth/onboarding
   - roles/RBAC
   - resources
   - chat
   - matching

## Recommended First Improvements

To make development predictable, the next team should add:

1. a committed `settings_dev.py` or `.env`-driven local settings path
2. local Postgres via Docker Compose
3. pinned dev/test dependencies including `pytest`, `pytest-django`, and `daphne`
4. seed commands for roles and test users
5. frontend environment variables for API base URLs
6. a repaired magic-link callback or a purely session-based callback page

## Troubleshooting

### `ModuleNotFoundError: No module named django`

You are not in the backend virtual environment.

Fix:

```bash
cd backend
source .venv/bin/activate
```

### Backend tries to connect to Azure DB

You are still using `config.settings` instead of your local override.

Fix:

```bash
python manage.py runserver 8000 --settings=config.settings_local
```

### Frontend cannot load resources or `/users/me/`

Check:

- backend is running on `localhost:8000`
- session cookie exists
- the logged-in user exists in DB
- the user has an active role assignment

### Magic link login redirects but frontend still fails

Use manual OTP entry instead. The callback contract is currently out of sync.

### Websocket/chat behavior does not work

Check:

- `daphne` is installed if you want a Channels-first dev loop
- you are using the ASGI app
- your user is authenticated and belongs to the target group

## Final Notes

You can get the project running locally today, but it requires a small amount of setup that the repository should have automated already.

If you only need a quick smoke-test loop:

1. backend local settings override
2. migrate
3. create a user
4. run backend
5. run frontend
6. log in with OTP from console output

That is the shortest practical path to a working local dev environment for the current codebase.
