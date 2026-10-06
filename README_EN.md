# BIOTech Connect

The mentoring platform for **BIOTech Futures** — connecting student teams with mentors, and supporting the full programme lifecycle: groups, chat, tasks, events, resources, announcements, competition submissions, and grading.

## Repository layout

| Directory | What it is |
|---|---|
| `backend/` | Django 5.2 + Django REST Framework API. PostgreSQL, Channels (WebSocket chat) with Redis, Azure Blob Storage for files, session-cookie auth with email OTP / magic-link login. |
| `frontend/` | Member-facing SPA (Vue 3 + Pinia + Vite). Students, mentors, supervisors, and in-app admin + grading tooling. |
| `adminweb/` | Standalone admin console (React + TanStack Router). Feature-frozen; active admin work happens in `frontend/`. |
| `resources/` | Workstream planning docs (largely historical). |

Deployment is Azure: the backend to App Service, both SPAs to Static Web Apps (see `.github/workflows/`). Scheduled workflows trigger token-protected backend endpoints for RSVP reminders, submission reminders, and unread-chat digests.

## Local development

### Database

```bash
docker compose -f docker-compose.dev.yml up -d   # Postgres 16 on localhost:5432
```

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate          # Windows (source venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver     # http://127.0.0.1:8000
```

Local settings live in `config/settings_local.py`; production configuration is environment-variable driven (see `config/settings.py` — Azure storage, SMTP, Redis, frontend base URLs are all env-gated and fail loud when missing outside DEBUG).

API docs (DEBUG only): `/api/docs/` (Swagger) and `/api/redoc/`.

### Frontend

```bash
cd frontend
npm ci
npm run dev                    # http://localhost:5173
```

Set `VITE_API_BASE_URL` (see `frontend/.env.example`); it defaults to `http://localhost:8000`.

## Testing

```bash
# Backend (same command CI runs, with coverage gate >= 60%)
# All suites live under backend/tests/, mirrored per app.
cd backend
python manage.py test tests --settings=config.settings_test

# Frontend unit tests
cd frontend
npm run test:unit
npm run type-check
```

## Contributing

- Work on feature branches; merge to `main` via Pull Request.
- Pre-commit hooks type-check `frontend/` and `adminweb/` when files in those trees are staged.
- Backend deploys are gated on the test suite in `.github/workflows/main_biotechbe.yml`.
