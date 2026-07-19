# Admin Backend

This Django app provides the admin-facing API for the BIOTech Futures mentoring platform. It is mounted at:

```text
/api/v1/admin/
```

The app coordinates admin workflows for users, groups, matching, events, resources, announcements, mentors, and admin tasks. Most endpoint classes live in `views.py`; business logic is kept in `services/`; matching logic is kept in `algorithms/`.

## Stack

- Django 5.2
- Django REST Framework
- PostgreSQL
- Session authentication
- Azure Blob Storage for resource files
- SMTP email for announcement delivery

## App Layout

```text
apps/admin/
├── algorithms/          # Student and mentor matching algorithms
├── migrations/          # Admin app migrations
├── services/            # Business logic used by API views
├── templates/emails/    # Announcement email templates
├── apps.py              # Django app config
├── models.py            # Admin-owned persistence, including MatchRun
├── permissions.py       # Admin permission checks
├── urls.py              # Admin API route map
└── views.py             # DRF API views
```

## Local Setup

Run commands from the backend root:

```bash
cd /path/to/biotech/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Open API docs at:

```text
http://127.0.0.1:8000/api/docs/
```

## Configuration

The backend reads settings from `.env`. Important values for this app include:

- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- `USE_AZURE_BLOB_STORAGE`
- `AZURE_ACCOUNT_NAME`, `AZURE_ACCOUNT_KEY`, `AZURE_CONNECTION_STRING`
- `AZURE_CONTAINER`, `AZURE_RESOURCE_CONTAINER`
- `RESOURCE_FILE_MAX_UPLOAD_SIZE`
- `RESOURCE_FILE_ALLOWED_EXTENSIONS`
- `RESOURCE_FILE_ALLOWED_MIME_TYPES`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_SSL`
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`
- `FRONTEND_BASE_URL`, `ADMIN_FRONTEND_BASE_URL`

See the backend `.env.example` for the full list.

## Authentication And Authorization

Most admin API views require:

- An authenticated session user.
- At least one `AdminScope` row for that user.

`IsAdminScoped` denies access when the user is unauthenticated or has no admin scope.

The password helper endpoints under `auth/` require only an authenticated session because they are used while completing first-time admin setup.

Admin scope behavior:

- A row in `admin_scope` marks the user as an admin; all admins can access all admin-managed records (single global tier).
- `apps.common.rbac.is_admin(user)` is the canonical check.

## API Surface

All routes below are relative to `/api/v1/admin/`.

### Users

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `user/` | List users with pagination, search, role, track, active, group, and sort filters. |
| `POST` | `user/` | Create a user. |
| `GET` | `user/tracks/` | List user tracks visible to the admin. |
| `POST` | `user/bulk/` | Bulk-create users from JSON. |
| `POST` | `user/bulk-csv/` | Bulk-create users from CSV text. |
| `GET` | `user/ungrouped-check/` | Check whether ungrouped students exist. |
| `GET` | `user/<user_id>/` | Fetch a user by ID. |
| `PUT` | `user/<user_id>/` | Update a user. |
| `DELETE` | `user/<user_id>/` | Delete a user. |
| `PATCH` | `user/<user_id>/status/` | Update user active status. |

Common list query parameters:

```text
page, limit, search, role, track, active, inGroup, sortBy, sortOrder
```

### Groups

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `group/` | List groups with pagination and filters. |
| `GET` | `group/<group_id>/` | Fetch one group. |
| `PUT` | `group/<group_id>/` | Update group name or track. |
| `GET` | `group/<group_id>/messages/` | List group message history. |
| `DELETE` | `group/<group_id>/messages/<message_id>/` | Remove a group message. |
| `DELETE` | `group/<group_id>/members/<user_id>/` | Remove a user from a group. |

Common list query parameters:

```text
page, limit, searchName, searchGroup, track, mentorStatus
```

### Student Matching

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `match/student/` | Generate student-group recommendations. |
| `GET` | `match/individual/` | List individual students eligible for matching. |
| `POST` | `match/confirm/` | Confirm student assignments into groups. |

Student matching logic lives in:

```text
algorithms/student.py
services/match.py
```

### Events

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `event/` | List events. |
| `POST` | `event/` | Create an event. |
| `GET` | `event/<event_id>/` | Fetch an event. |
| `PUT` | `event/<event_id>/` | Update an event. |
| `DELETE` | `event/<event_id>/` | Delete an event. |
| `GET` | `event/<event_id>/rsvp/` | List RSVPs for an event. |
| `POST` | `event/<event_id>/rsvp/` | Create an RSVP. |
| `GET` | `event/<event_id>/targets/` | List event audience targets. |
| `GET` | `event/meta/groups/` | List groups for event targeting. |
| `GET` | `event/meta/roles/` | List roles for event targeting. |
| `GET` | `event/meta/tracks/` | List tracks for event targeting. |
| `PUT` | `event/rsvp/<rsvp_id>/` | Update an RSVP. |

### Resources

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `resource/` | List resources. |
| `POST` | `resource/` | Create resource metadata. |
| `POST` | `resource/upload/` | Upload a resource file and create the resource. |
| `GET` | `resource/<resource_id>/` | Fetch a resource. |
| `PUT` | `resource/<resource_id>/` | Update a resource. |
| `PATCH` | `resource/<resource_id>/` | Partially update a resource. |
| `DELETE` | `resource/<resource_id>/` | Delete a resource. |
| `GET` | `resource/<resource_id>/access/` | Return access information or a signed URL. |
| `GET` | `resource/<resource_id>/download/` | Download resource content. |
| `POST` | `resource/<resource_id>/upload/` | Replace a resource file. |
| `POST` | `resource/<resource_id>/assign-role/` | Assign a role to a resource. |
| `DELETE` | `resource/<resource_id>/remove-role/` | Remove a role from a resource. |
| `GET` | `resource/roles/` | List resource roles. |
| `GET` | `resource/types/` | List resource types. |
| `GET` | `resource/tracks/` | List tracks for resources. |

Resource storage helpers live in `services/resource.py`. File uploads also use `apps.resources.services.upload`.

### Announcements

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `announcement/` | List announcements. |
| `POST` | `announcement/` | Create an announcement. |
| `GET` | `announcement/<announcement_id>/` | Fetch an announcement. |
| `PUT` | `announcement/<announcement_id>/` | Update an announcement. |
| `POST` | `announcement/<announcement_id>/archive/` | Archive an announcement. |
| `POST` | `announcement/<announcement_id>/notify/` | Send announcement email notifications. |
| `GET` | `announcement/tracks/` | List tracks for announcement targeting. |
| `GET` | `announcement/roles/` | List roles for announcement targeting. |

Announcement email HTML is rendered from:

```text
templates/emails/announcement.html
```

### Mentors

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `mentor/` | List mentors visible to the admin. |
| `PATCH` | `mentor/<mentor_id>/active/` | Update mentor active status. |

### Admin Tasks

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `task/` | List admin-visible tasks. |
| `POST` | `task/` | Create an admin task. |
| `GET` | `task/<task_id>/` | Fetch one task. |
| `PATCH` | `task/<task_id>/` | Update a task. |
| `DELETE` | `task/<task_id>/` | Delete a task. |
| `POST` | `task/<task_id>/toggle/` | Toggle task completion. |

### Admin Auth Helpers

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `auth/password-status/` | Check whether the current admin has a usable password. |
| `POST` | `auth/set-password/` | Set the current admin password. |

### Mentor Matching

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `mentor-match/recommend/` | Generate mentor-group recommendations. |
| `GET` | `mentor-match/mentors/` | List mentors for matching. |
| `GET` | `mentor-match/groups/` | List groups without assigned mentors. |
| `GET` | `mentor-match/matched-groups/` | List groups with assigned mentors. |
| `POST` | `mentor-match/confirm/` | Confirm mentor assignments. |
| `POST` | `mentor-match/replace/` | Replace a mentor assignment. |
| `POST` | `mentor-match/unassign/` | Unassign mentors from groups. |

Mentor matching logic lives in:

```text
algorithms/mentor.py
services/mentor_match.py
```

## Response Shape

Most services return dictionaries with:

```json
{
  "msg": "Human-readable result",
  "data": {}
}
```

Paginated endpoints usually return `data` plus pagination metadata. Check the corresponding service function for exact fields before changing frontend contracts.

## Tests

Admin tests are located in:

```text
tests/apps/admin/
```

Run the admin test set from the backend root:

```bash
python manage.py test tests.apps.admin
```

Useful targeted tests include:

```bash
python manage.py test tests.apps.admin.test_user_service
python manage.py test tests.apps.admin.test_group_service
python manage.py test tests.apps.admin.test_resource_upload
python manage.py test tests.apps.admin.test_admin_event_api
python manage.py test tests.apps.admin.test_student_algorithm_parity
python manage.py test tests.apps.admin.test_mentor_algorithm_parity
python manage.py test tests.apps.admin.test_announcement_email_delivery
```

## Development Notes

- Add new admin routes in `urls.py`, then implement a DRF `APIView` in `views.py`.
- Keep database and integration logic in a service module rather than in the view.
- Apply track scoping in services whenever a result should be limited for track admins.
- Preserve camelCase response fields where the admin frontend already depends on them.
- Store matching run payloads and results in `MatchRun` when auditability is useful.
- Prefer adding or updating tests under `tests/apps/admin/` for any behavior change.
