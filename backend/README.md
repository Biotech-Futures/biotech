## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # optional: pytest + pytest-django
cp .env.example .env                  # edit secrets and DB credentials
```

Ensure PostgreSQL is running and matches `DB_*` / `POSTGRES_*` in `.env`.

## Database migrations

Use **`config.settings_local`** for local Postgres and file storage (see `config/settings_local.py`).

```bash
cd backend
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_local

python manage.py migrate
python manage.py showmigrations
python manage.py makemigrations --check --dry-run   # should print "No changes detected" if models match DB
```

Or run migrations via the helper (same defaults):

```bash
chmod +x scripts/db_migrate.sh
./scripts/db_migrate.sh migrate
./scripts/db_migrate.sh showmigrations
```

After changing `models.py`, create and apply migrations:

```bash
python manage.py makemigrations
python manage.py migrate
```

Target / reference DDL for future schema work lives in `table_statements.sql`; Django migrations remain the source of truth for the live database.

# SOFT3888_TU08_02
BIOTech Futures Mentoring Platform

## Faculty of Engineering, BIOTech Futures

### Project Title: BIOTech Futures Mentoring Platform

Project description and scope: 
Develop a modular, web-based Mentoring Platform that allows students and mentors to self-register, form or import student groups, and be matched automatically by configurable rules. Students select year level (9–12) and interest areas; mentors register with expertise tags and availability. The platform will deliver:  User Onboarding: Google OAuth2 login, role-based profiles (student/mentor) Group Management: Bulk student import, auto-grouping, manual group editor Mentor Directory: Profile CRUD, admin approval, tag-based discovery Matching Engine: Weighted algorithm for interest & year-level matching, admin review panel Collaboration Tools: Real-time chat, shared task lists, email/in-app notifications Analytics Dashboard: Engagement metrics, task-completion rates, exportable reports

Expected outcomes/deliverables: Module Prototypes: Working Flask + MongoDB blueprints for each core function (Auth, Students, Mentors, Matching, Chat/Tasks, Analytics) API Documentation: OpenAPI/Swagger spec for all REST endpoints Responsive Front End: HTML/CSS/JS interface with onboarding forms, group editor, chat UI, analytics dashboard Integration Demonstration: End-to-end workflow from signup through matching to collaboration and reporting Deployment Artifacts: Docker Compose configuration and deployment scripts for a staging environment
Specific required knowledge, skills, and/or technology: Python & Flask (backend API development)
MongoDB (NoSQL data modeling)
RESTful design & JWT-based authentication (Google OAuth2 integration) 
Front-end web development: HTML5, CSS3, JavaScript (vanilla or lightweight framework) 
DevOps fundamentals: Docker containers, CI/CD pipelines 

Related general fields/disciplines (if applicable): Web Development;Software Development;Data Science/Analytics;Information Systems;

Can you provide dataset for this project?: Not applicable

How many groups would you like to work with on this project?: 3 groups


