# BIOTech Connect

![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)

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
region and interests from their profile. Guardian editing uses the separate
Guardian Details section, which warns first: a new guardian replaces the old one
straight away, and clears the permission already given (media consent too) until
the new guardian signs the platform's consent form, which is emailed to them.

The resend button uses the same `guardian_consent_request` email service as the
admin page, including its ten-minute cooldown and single-use consent link.
Links use `FRONTEND_BASE_URL` and open `/#/consent/<token>`; the earlier
`GUARDIAN_CONSENT_URL` placeholder is no longer needed. Signatures are stored
with the consent record, and its PDF is made from it whenever an admin views
or downloads it, as Mark Summaries and certificates are; no PDF is stored.
With `config.settings_local`, outgoing emails are saved under
`backend/sent_emails/`, not delivered to real inboxes.

Automatic reminders are disabled by default. After arranging a regular scheduler
for `python manage.py send_guardian_reminders`, set
`GUARDIAN_REMINDER_INTERVAL_DAYS` (for example, `7`). Successfully sent invitations
then record a next reminder due date. The command only processes due reminders
for active students who still need permission or have a pending guardian change; it doesn't send an initial email
to every existing student. No scheduler is created by these code changes.

Bounced emails are found by a check of the sending mailboxes through Hostinger's
Mail API (read-only, nothing in a mailbox is changed). It opens only bounce
notices and notes who each one says didn't get our email: on the Management page
it came from (listed as missed, so Resend Email To Missed Individuals emails them
again) and on the System Emails log under Bounced emails. GitHub's
`.github/workflows/bounce-check.yml` starts it about every 10 minutes through
`POST /api/v1/management/bounce-check/`, with the `EMAIL_JOBS_TOKEN` the other
email jobs use. `python manage.py check_bounced_emails` runs it by hand.

To switch it on, set `HOSTINGER_MAIL_API_KEY` on the backend (in production, the
Azure app's Settings > Environment variables > App settings), made in hPanel >
Emails > the domain > Agentic Mail > API access. Never commit it. Without the key
the check answers "off" and does nothing. `BOUNCE_LOOKBACK_DAYS` (default 90, about
3 months) limits how far back its first run, or one after a gap, reads.

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
- Deploys are gated on the checks in `.github/workflows/main_biotechbe.yml`: a change deploys only the sides it touches, and only once every check for it passes, so a change to both the backend and the frontend ships both or neither.

## License

This project is licensed under the Apache License 2.0. See [LICENSE.md](LICENSE.md) for details.
