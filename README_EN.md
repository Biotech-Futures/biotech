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
docker compose -f docker-compose.dev.yml up -d   # Postgres 16 on localhost:5433 (POSTGRES_HOST_PORT overrides)
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

### Student profile and guardian invitations

Students without a linked supervisor can edit their name, school, year, country,
region, interests and guardian details from their profile. An actual guardian
change clears the previous permission, consent timestamp and reminder history.

Set `GUARDIAN_CONSENT_URL` in `backend/.env` to the approved HTTPS guardian form
URL. The existing form must continue identifying the student by email and posting
the consent result to the authenticated `updjoinperms` webhook. Confirm that
contract with the form owner before enabling it in a deployed environment.
The invitation uses the shared System Emails settings/template and the guardian
email saved on the student's profile; resend is limited to once per 24 hours.
With `config.settings_local`, outgoing emails are saved under
`backend/sent_emails/`, not delivered to real inboxes.

Automatic reminders are disabled by default. After arranging a regular scheduler
for `python manage.py send_guardian_reminders`, set
`GUARDIAN_REMINDER_INTERVAL_DAYS` (for example, `7`). Successfully sent invitations
then record a next reminder due date. The command only processes due reminders
for active students who still need permission; it doesn't send an initial email
to every existing student. No scheduler is created by these code changes.

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
