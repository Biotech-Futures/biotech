# Development Runbook

## Purpose

This document explains how to run and test the current codebase in a development environment.

It covers:

- backend setup
- frontend setup
- practical workarounds for local development

## Current State Summary

The repository does not currently ship with a clean, self-contained local development setup.

Important caveats:

- the main backend runtime uses `backend/config/settings.py`
- that settings file hardcodes Azure PostgreSQL and Azure Blob configuration
- the repo now has a local Postgres-oriented settings override at `backend/config/settings_local.py`
- the frontend expects the backend at `http://localhost:8000`
- the frontend login page works best with OTP entry, not the current magic-link callback
- websocket chat depends on Channels, but `daphne` is not listed in `backend/requirements.txt`

To get the project running locally is:

1. use Python 3.10
2. start local Postgres with Docker Compose
3. run Django on `localhost:8000`
4. run Vite on `localhost:5173`

## Repo Layout

biotech/
├── backend/
│   ├── manage.py
│   ├── config/
│   ├── apps/
│   └── non-project/docs/
└── frontend/
    ├── package.json
    └── src/


## Prerequisites

- Python 3.10
- Node.js 20+ or 22+
- npm
- Docker Desktop or another working Docker engine

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

## Backend: Local Settings Override

The main settings file points to Azure resources. For local development, this repo uses an untracked local settings file that points to local Postgres.

Create file:

`backend/config/settings_local.py`

Add contents:

```python
import os

from .settings import *

# Dev-only secret
SECRET_KEY = "dev-only-not-for-production"

DEBUG = True
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

# Use local Postgres for dev so schema behavior matches production/migrations.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT"),
        "CONN_MAX_AGE": 0,
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

## Backend: Postgres Database Setup

Start the local Postgres container from the repo root:

```bash
docker compose -f docker-compose.dev.yml up -d postgres
```

Run migrations using the local settings module:

```bash
python manage.py migrate --settings=config.settings_local
```

Create an admin user:

```bash
python manage.py createsuperuser --settings=config.settings_local
```

## Backend: Run the Development Server

Standard dev server:

```bash
python manage.py runserver 8000 --settings=config.settings_local
```

Backend URLs:

- `http://localhost:8000/api/docs/`
- `http://localhost:8000/admin/`


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

### Terminal 1: backend

```bash
export POSTGRES_DB=<DB_Name>
export POSTGRES_USER=<UserName>
export POSTGRES_PASSWORD=<Password>
#Optional:
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
# If you want to the environment variables to persist in new terminal:
# source ~/.zshrc
docker compose -f docker-compose.dev.yml up -d postgres
cd backend
source .venv/bin/activate
python manage.py runserver 8000 --settings=config.settings_local
```

#### Redeploy database
```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d postgres
docker compose -f docker-compose.dev.yml ps

cd backend
source .venv/bin/activate
python manage.py migrate --settings=config.settings_local
python manage.py createsuperuser --settings=config.settings_local
python manage.py runserver 8000 --settings=config.settings_local
```

### Terminal 2: frontend

```bash
cd frontend
npm ci
npm run dev
```

## How to Create a Local User for Testing
```bash
python manage.py shell --settings=config.settings_local
```

Then:

```python
from apps.users.models import User
from apps.resources.models import Roles, RoleAssignmentHistory
from django.utils import timezone

u = User.objects.create_user(
    email="student@usyd.edu.au",
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

After that, log in from the frontend using `student@usyd.edu.au`.