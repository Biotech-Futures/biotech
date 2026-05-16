# Functionality Testing Guidebook

This guide is the standard test path for this repo. It covers the Django
backend, the Vue user frontend, and the React admin web app.

Run commands from the repo root unless a command block changes directory.

## Repo Surfaces

- `backend/`: Django API, Django admin, Channels, file storage, email flows,
  matching, events, resources, chat, tasks, groups, users, announcements,
  certificates, and dashboard APIs.
- `frontend/`: Vue user-facing app running on Vite at `http://localhost:5173`.
- `adminweb/`: React admin app running on Vite at `http://localhost:3000`.
- `docker-compose.dev.yml`: optional local PostgreSQL service for manual
  backend smoke tests.

## Quick Gates

Use these before handing off a branch:

```bash
cd backend
.venv/bin/python manage.py test --settings=config.settings_test
```

```bash
cd frontend
npm ci
npm run build
```

```bash
cd adminweb
pnpm install --frozen-lockfile
pnpm typecheck
pnpm test
pnpm build
```

If the change does not touch `adminweb/`, the admin web commands are optional.
If the change is documentation-only, run `git diff --check`.

## Backend Setup

Backend automated tests use `config.settings_test`, which runs against an
in-memory SQLite database, disables migrations, uses fast password hashing, and
does not require local Postgres, Redis, or Azure Blob credentials.

First-time setup:

```bash
cd backend
python3.10 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Check the backend interpreter if dependency installation fails:

```bash
cd backend
.venv/bin/python --version
```

Use Python 3.10 for the backend test environment. On macOS, `python3` may point
to Python 3.13; if `.venv/bin/python --version` reports 3.13 and dependency
installation fails while building `cbor2`, recreate `.venv` with `python3.10`.

Useful dependency checks:

```bash
cd backend
.venv/bin/python -m pip check
.venv/bin/python -m pip list --format=freeze
```

## Backend Automated Tests

Run the whole Django suite:

```bash
cd backend
.venv/bin/python manage.py test --settings=config.settings_test
```

Run focused suites while developing:

```bash
cd backend
.venv/bin/python manage.py test tests.apps.services tests.apps.users tests.apps.user_sessions --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.dashboard tests.apps.groups --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.chat --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.resources --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.events --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.tasks --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.announcements tests.apps.certificates --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.admin tests.apps.matching_runtime --settings=config.settings_test
```

Run a single test file or test class:

```bash
cd backend
.venv/bin/python manage.py test tests.apps.events.test_events --settings=config.settings_test
.venv/bin/python manage.py test tests.apps.chat.test_chat_contract --settings=config.settings_test
```

Check syntax for touched Python files:

```bash
cd backend
.venv/bin/python -m compileall apps config tests
```

Check generated API schema:

```bash
cd backend
.venv/bin/python manage.py spectacular --file /tmp/biotech-openapi.yml --settings=config.settings_test
```

Current known caveat: the full backend suite currently reaches the app tests
and has an existing `tests.apps.matching_runtime` `403 != 200` failure. Triage
that separately unless your change touches matching/admin authorization.

## Backend Manual Smoke

Use manual API smoke tests when route wiring, auth, permissions, file handling,
email, or frontend API paths change.

Start the backend:

```bash
cd backend
.venv/bin/python manage.py runserver --settings=config.settings_local
```

If local Postgres is needed for manual data persistence:

```bash
docker compose -f docker-compose.dev.yml up -d postgres
```

If using the bundled dev Postgres, make sure `backend/.env` points at the same
database values from `docker-compose.dev.yml`.

```text
DB_NAME=biotech_dev
DB_USER=biotech
DB_PASSWORD=biotech
DB_HOST=127.0.0.1
DB_PORT=5432
```

Optional local data setup:

```bash
cd backend
.venv/bin/python manage.py migrate --settings=config.settings_local
.venv/bin/python manage.py populate_countries --settings=config.settings_local
.venv/bin/python manage.py import_p11 "../P11 Test User Data.xlsx" --settings=config.settings_local
.venv/bin/python manage.py create_test_accounts --settings=config.settings_local
.venv/bin/python manage.py createsuperuser --settings=config.settings_local
```

`create_test_accounts` creates a global admin, track admin, mentor, supervisor,
and basic user. The default password for newly created accounts is
`Password123!`; pass `--reset-password` to overwrite existing account
passwords.

Open API docs:

```text
http://localhost:8000/api/docs/
http://localhost:8000/api/schema/
```

Unauthenticated health-style checks:

```bash
curl -i "http://localhost:8000/api/schema/"
curl -i "http://localhost:8000/services/csrf/"
curl -i "http://localhost:8000/api/v1/services/csrf/"
```

Most app endpoints require an authenticated Django session. For manual
functional testing, log in through the Vue app or admin web app, then inspect
the browser network panel while exercising the workflows below.

### Backend Route Smoke

Canonical API paths should use `/api/v1/...`; legacy paths still resolve for
backward compatibility.

```bash
curl -i "http://localhost:8000/api/v1/events/?when=upcoming&page_size=1"
curl -i "http://localhost:8000/events/v1/?when=upcoming&page_size=1"
curl -i "http://localhost:8000/api/v1/dashboard/progress/"
curl -i "http://localhost:8000/dashboard/progress/"
```

Expected result for authenticated requests:

- Canonical `/api/v1/...` endpoints return the same functional data as legacy
  paths.
- Unauthenticated requests return a controlled auth response, not a 500.
- New frontend work should prefer `/api/v1/...`.

### Backend Functional Checklist

Auth and sessions:

- Fetch CSRF from `/api/v1/services/csrf/`.
- Request and verify login code through the user frontend.
- Test password login through `/api/v1/login/` if using password auth.
- Request and confirm password reset.
- Log out and confirm protected endpoints stop returning user data.
- Confirm session cookies are scoped correctly for `localhost:5173` and
  `localhost:3000`.

Users, roles, and groups:

- List users and the current user profile.
- Create or update a user through admin APIs.
- Bulk upload users from CSV in the admin web app.
- Toggle user status and track assignment.
- List groups, open a group detail view, and remove or restore members where
  supported.
- Run `sync_role_groups` after role changes.

Dashboard:

- Open dashboard summary, progress, next event, and groups preview.
- Verify dashboard counts match visible groups, tasks, resources, and events.
- Check empty-state behavior with a new user or no assigned group.

Chat:

- Load group messages.
- Send a plain message and a message with a URL.
- Confirm link preview creation and duplicate preview reuse.
- Add and remove reactions.
- Check read receipts and typing status.
- Search mentions.
- Search GIFs; without `TENOR_API_KEY`, the endpoint should fail soft with an
  empty list rather than a 500.
- Upload an allowed attachment and reject a disallowed extension or MIME type.

Resources:

- List resource files, roles, resource types, and tracks.
- Upload a file from admin.
- Download or open a file as a user with permission.
- Assign and remove role access.
- Verify soft-delete and restore paths.

Events:

- List upcoming and past events.
- Create, edit, and delete an event from admin.
- Invite individual users and groups.
- RSVP as the current user.
- Check `/api/v1/events/rsvps/me/`.
- Dry-run RSVP reminders:

```bash
cd backend
.venv/bin/python manage.py send_rsvp_reminders --dry-run --settings=config.settings_local
```

Tasks:

- List tasks.
- Create, update, and delete a task.
- Toggle a task with `/api/v1/tasks/{id}/check/`.
- Bulk toggle tasks with `/api/v1/tasks/bulk/check/`.
- Restore deleted tasks with `/api/v1/tasks/{id}/restore/`.

Announcements:

- Create, update, archive, and notify an announcement from admin.
- Verify user-facing announcement list visibility by role or track.
- Confirm email notification failures are handled without crashing the request.

Matching:

- Run student matching recommendations.
- Confirm a student match.
- Run mentor matching recommendations.
- Replace, unassign, and bulk replace inactive mentors.
- Review `tests.apps.admin` and `tests.apps.matching_runtime` for expected
  admin authorization behavior before changing these flows.

Certificates and audit:

- Generate or list mentor certificates.
- Verify certificate lookup or verification endpoints.
- Confirm audit logs are created for admin actions that should be audited.

Soft-delete recovery paths:

Frontend-focused soft-delete testing is documented in
`backend/docs/soft_delete_frontend_testing.md`.

```text
GET  /api/v1/groups/groups/?include_deleted=true
POST /api/v1/groups/groups/{groupId}/restore/

GET  /api/v1/chat/groups/{groupId}/messages/deleted/
POST /api/v1/chat/groups/{groupId}/messages/{messageId}/restore/

GET  /api/v1/tasks/?deleted=true
POST /api/v1/tasks/{taskId}/restore/

GET  /api/v1/resources/resource-files/?deleted=true
POST /api/v1/resources/resource-files/{resourceId}/restore/

GET  /api/v1/events/?deleted=true&when=all
POST /api/v1/events/{eventId}/restore/
```

Restore responses should return HTTP `200` and `deleted_at: null`.

## Vue User Frontend

The user frontend lives in `frontend/` and uses npm.

First-time setup:

```bash
cd frontend
npm ci
```

Use `frontend/.env.example` as the local shape:

```text
VITE_API_BASE_URL=http://localhost:8000
VITE_ADMIN_FRONTEND_URL=http://localhost:3000
```

Run the production build and type-check:

```bash
cd frontend
npm run build
```

Run unit tests:

```bash
cd frontend
npm run test:unit
```

Run Playwright end-to-end tests:

```bash
cd frontend
npx playwright install
npm run test:e2e
```

`npm run test:e2e` starts or reuses the Vite dev server at
`http://localhost:5173`. In CI, Playwright uses preview at
`http://localhost:4173`.

Run the local frontend:

```bash
cd frontend
npm run dev
```

Manual user app checklist:

- `/login`: login code and password-reset entry points render.
- `/auth/callback`: magic-link callback handles success and failure states.
- `/auth/reset-password` and `/auth/set-password`: forms validate and submit.
- `/dashboard`: dashboard cards, next event, progress, and group preview load.
- `/groups` and `/groups/{id}`: group detail, chat, messages, reactions,
  attachments, mentions, GIF search, and link previews work.
- `/resources` and `/resources/{id}`: resources list, filters, permissions,
  details, and downloads work.
- `/events`: event list, filters, detail state, and RSVP actions work.
- `/announcements`: announcements load and archived items stay hidden.
- `/profile`: user profile loads and session state stays consistent.
- Browser network calls prefer `/api/v1/...` and avoid unnecessary legacy 404
  fallback requests.

Do not use `npm run lint` as a passive check: this repo's lint script runs
ESLint with `--fix` and can modify files.

## React Admin Web

The admin web app lives in `adminweb/` and uses pnpm.

First-time setup:

```bash
cd adminweb
pnpm install --frozen-lockfile
```

Create `adminweb/.env` for local backend testing:

```text
VITE_PUBLIC_API_URL=http://localhost:8000
```

Run checks:

```bash
cd adminweb
pnpm typecheck
pnpm test
pnpm build
```

Run the local admin app:

```bash
cd adminweb
pnpm dev
```

Manual admin app checklist:

- `/signin`: admin login and CSRF bootstrap work.
- `/setup-password` and `/reset-password`: password setup and reset flows work.
- Admin shell: navigation, current user menu, and protected-route redirect work.
- User and student pages: search, filters, create/edit, status changes, bulk
  CSV upload, and track assignment work.
- Group pages: group table, detail drawer, member operations, matched and
  unmatched group panels work.
- Matching pages: student matching board, mentor matching board, manual assign,
  replace, unassign, and bulk replace flows work.
- Resource pages: upload sheet, filters, detail drawer, role assignment, file
  replacement, and download work.
- Event pages: create/edit/delete events, target groups/roles/tracks, RSVP
  viewing, and invitation actions work.
- Announcement pages: rich text editor, create/edit/archive, role or track
  targeting, and notify action work.
- Task pages: create/edit/delete, toggle, status, and restore behavior work.

Admin API network calls should go to:

```text
http://localhost:8000/api/v1/admin/...
http://localhost:8000/api/v1/...
```

## Full Local Stack Smoke

Use this when a change crosses backend and frontend boundaries.

Terminal 1:

```bash
cd backend
.venv/bin/python manage.py runserver --settings=config.settings_local
```

Terminal 2:

```bash
cd frontend
npm run dev
```

Terminal 3:

```bash
cd adminweb
pnpm dev
```

Then verify:

- User frontend opens at `http://localhost:5173`.
- Admin web opens at `http://localhost:3000`.
- Backend docs open at `http://localhost:8000/api/docs/`.
- Login works in each app surface you changed.
- Browser network panel shows no unexpected 500s, CORS failures, CSRF failures,
  or repeated `/api/v1/...` to legacy fallback 404s.
- Refreshing a protected page keeps or intentionally clears session state.

## Suggested Test Matrix

Backend-only change:

```bash
cd backend
.venv/bin/python manage.py test --settings=config.settings_test
.venv/bin/python -m compileall apps config tests
git diff --check
```

Backend feature-specific change:

```bash
cd backend
.venv/bin/python manage.py test tests.apps.<area> --settings=config.settings_test
.venv/bin/python manage.py test --settings=config.settings_test
```

Vue user frontend-only change:

```bash
cd frontend
npm run build
npm run test:unit
```

Vue route or user workflow change:

```bash
cd frontend
npm run build
npm run test:e2e
```

React admin web-only change:

```bash
cd adminweb
pnpm typecheck
pnpm test
pnpm build
```

Shared API and frontend change:

```bash
cd backend
.venv/bin/python manage.py test tests.apps.events tests.apps.chat tests.apps.resources tests.apps.groups tests.apps.tasks --settings=config.settings_test
cd ../frontend
npm run build
cd ../adminweb
pnpm typecheck
pnpm build
```

Before deploy:

```bash
cd backend
.venv/bin/python manage.py test --settings=config.settings_test
cd ../frontend
npm run build
cd ../adminweb
pnpm typecheck
pnpm test
pnpm build
git diff --check
```

## Troubleshooting

`cbor2` fails to build:

- The venv is probably Python 3.13 or `autobahn` is not pinned.
- Recreate the backend venv with `python3.10`.
- Confirm `backend/requirements.txt` includes `autobahn==24.4.2`.

Dependency install cannot reach package indexes:

- Retry with network access.
- If only one package is missing, confirm whether it is already installed with
  `.venv/bin/python -m pip show <package>`.

CSRF or CORS failures:

- Confirm backend uses `config.settings_local`.
- Confirm frontend origins are listed in `CORS_ALLOWED_ORIGINS` and
  `CSRF_TRUSTED_ORIGINS`.
- Confirm frontend env points to `http://localhost:8000`.

Backend manual server cannot connect to Postgres:

- Automated tests do not need Postgres; use `config.settings_test`.
- For manual testing, start `docker-compose.dev.yml` Postgres and verify
  `backend/.env` matches it.

Playwright cannot start:

- Run `npx playwright install`.
- Check whether another process is already using port `5173`.

Admin web command is missing `pnpm`:

- Install pnpm with your normal Node toolchain, then rerun
  `pnpm install --frozen-lockfile`.
