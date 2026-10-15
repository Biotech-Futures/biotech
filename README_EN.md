# BIOTech Futures — Web Platform

A Django and Vue-based platform supporting student groups, mentors, resources, events, and collaborative group work. This repository also contains mentor-management and matching functionality.

## Project Structure

- `backend/` — Django API, database models, migrations, and server-side functionality.
- `frontend/` — Vue frontend, pages, and interactive group workspace.
- `backend/requirements.txt` — Python dependencies.
- `frontend/package.json` and `frontend/package-lock.json` — JavaScript dependencies and locked versions.

## Prerequisites

Install Python, Node.js/npm, and the database required by your local Django configuration. The current BIOTech development setup uses PostgreSQL; check your local environment configuration for the correct connection details. Obtain any required environment variables and test credentials from the team through an approved private channel. Do not commit passwords or `.env` files.

## Quick Start (Local Development)

Run the backend and frontend in **separate terminals**. Commands below start from the repository root.

### 1. Clone or update the repository

```bash
git clone <repository-url>
cd biotech
```

If you already have the repository, pull the appropriate team branch instead of cloning again.

### 2. Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate       # Linux / macOS / WSL
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The development backend normally runs at `http://127.0.0.1:8000/`. Make sure your database is running and your local Django settings are configured before applying migrations. If the project already has a virtual environment, activate it instead of creating another.

### 3. Frontend setup (new terminal)

```bash
cd frontend
npm ci
npm run dev
```

Open the local URL shown by Vite in the terminal (for example, `http://localhost:5173/`; your port may differ).

**Important:** `npm ci` installs **all** frontend dependencies listed in `package-lock.json`, including `y-protocols`. You do **not** need to install `y-protocols` separately or add it to Python's `requirements.txt`.

If `npm ci` fails because the lockfile is out of sync with `package.json`, ask the team to correct and commit the lockfile. Do not manually edit `node_modules`.

## Updating Your Local Copy

After pulling changes from GitHub, refresh dependencies when the dependency files have changed:

```bash
# From the repository root
cd frontend
npm ci
npm run dev
```

For backend dependency changes, activate the Python virtual environment and rerun `python -m pip install -r requirements.txt`. Apply any new Django migrations with `python manage.py migrate`.

> **Note:** `git pull` downloads code and dependency manifests, but does not install new npm or Python packages automatically. The first install (and reinstall after dependency changes) must still be run locally.

## Main Features

- Authentication and sign-in flow.
- Group workspace with Tasks and Meetings views.
- Group meeting details and collaborative meeting notes.
- Group discussion and member collaboration.
- Resource management and document previews.
- Event content and banner display.
- Mentor/student management and matching functionality.

Some functionality may still be under development. Availability depends on the branch, user role, and configured services.

## Testing and Verification

### Frontend

```bash
cd frontend
npm run dev
```

Check the available scripts in `frontend/package.json` for build, type-checking, and test commands before running them.

For the group meetings interface, sign in with an account assigned to a group, open the group page, select **Meetings**, open a meeting, and use **Back to Meetings** to return to the group's Meetings view.

### Backend

```bash
cd backend
source .venv/bin/activate
python manage.py check
python manage.py test
```

The exact tests available depend on the checked-out branch and your local test database configuration.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `Failed to resolve import "y-protocols/awareness"` | Run `npm ci` inside `frontend/`, then restart Vite. |
| `Module not found` in frontend | Confirm you are in `frontend/` and have installed dependencies with `npm ci`. |
| Frontend cannot reach the API | Confirm Django is running and the frontend API base URL points to the correct backend address. |
| Database connection or SSL error | Check PostgreSQL service, credentials, port, and local SSL settings. |
| Unapplied migrations | Run `python manage.py migrate` in `backend/`. |
| Port already in use | Stop the existing development server or use another available port. |
| No group visible | Check that the signed-in user has a group membership; some views require an assigned group. |

## Working as a Team

1. Work on the agreed branch and pull updates before starting new work.
2. Commit source code and dependency manifests when adding packages; do not commit `node_modules/` or Python virtual environments.
3. Keep secrets and machine-specific settings out of commits.
4. Use pull requests and team review procedures before merging shared changes.
5. Update this README whenever setup steps or required dependencies change.

## Legacy Mentor-Management Operations

The original mentor-management documentation described Excel import, automated grouping, mentor assignment, replacement, account deactivation, and email notifications. These workflows may belong to older modules or branches; **verify the current API routes and management commands in the checked-out code before using them**. In particular, avoid running reset/delete-all operations against shared or production data.

For current admin functionality, consult the Django admin routes and the backend's application-specific documentation. Configure email and other external services through approved environment settings, not hard-coded credentials.

## License

See the repository's license information, if provided, or contact the project maintainers.
