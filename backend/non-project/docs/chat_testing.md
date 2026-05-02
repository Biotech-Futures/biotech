# Chat Testing Guide

This document explains how to test the current chat feature set in local development.

This guide is intentionally focused on manual verification against the local Postgres-backed dev stack.

## Scope

The current chat implementation includes:

- REST message listing and creation at `/chat/groups/<group_id>/messages/`
- REST message edit and delete paths
- WebSocket chat at `/ws/chat/<conversation_id>/`
- WebSocket message sending
- WebSocket typing indicators
- Celery side effects after message creation

Important current detail:

- The WebSocket route uses `conversation_id`, but today that ID is the existing `Groups.id`
- In practice, `conversation_id` and `group_id` are the same value in local testing
- The exact route is `/ws/chat/<GROUP_ID>/` with a trailing slash

## What Uses Redis and Celery

The chat stack uses Redis and Celery in different ways:

- Django Channels uses Redis as the channel layer for WebSocket fan-out
- Celery uses Redis as the broker and result backend for background tasks
- The WebSocket consumer persists the message first, broadcasts it second, and queues Celery work last

That means:

- If the Celery worker is stopped but Redis is still up, chat messages should still persist and broadcast
- If Redis is fully down in local dev, both Channels and Celery are affected
- To test "Celery down but chat still works", stop `celery-worker`, not `redis`

## Prerequisites

- Python dependencies installed in `backend/.venv`
- PostgreSQL available
- Redis available
- Optional but recommended: Docker Desktop / Docker Engine
- Optional for manual WebSocket testing: `wscat`

## Option A: Start the Dev Stack with Docker Compose

From the repo root:

```bash
docker compose -f docker-compose.dev.yml up postgres redis web celery-worker
```

Useful companion commands:

```bash
docker compose -f docker-compose.dev.yml logs -f web
docker compose -f docker-compose.dev.yml logs -f celery-worker
docker compose -f docker-compose.dev.yml logs -f redis
```

Services started by this file:

- `postgres`
- `redis`
- `web`
- `celery-worker`

The backend should be available at:

- `http://127.0.0.1:8000`

Important:

- If you use this Docker path, run Django management commands inside the `web` container
- The container already has the local dev DB settings injected
- Running `python manage.py ...` from your host shell may still pick up Azure DB values from your local environment or `.env`
- The current `web` container runs plain Django `runserver`

## Option B: Run the Backend Locally Without Docker

If you want to run the Django app directly:

```bash
cd backend
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_local
export DB_NAME=biotech_dev
export DB_USER=biotech
export DB_PASSWORD=biotech
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_SSLMODE=disable
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
python manage.py runserver
```

You still need PostgreSQL and Redis running somewhere accessible to the app.

Why these exports matter:

- `config.settings_local` does not replace the database config by itself
- the base settings still read `DB_HOST`, `DB_USER`, `DB_PASSWORD`, and `DB_SSLMODE` from environment variables
- if those variables still point at Azure, Django will try to connect there instead of your local Postgres

## Seed Local Chat Test Data

The snippet below creates:

- one student
- one mentor
- one supervisor
- one outsider who is not in the group
- a track and a group
- memberships for the student, mentor, and supervisor
- role assignments needed for moderation tests

If you started the stack with Docker Compose, run the seed inside the `web` container:

```bash
docker compose -f docker-compose.dev.yml exec -T web python manage.py shell <<'PY'
from datetime import datetime, timezone as dt_timezone

from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import User

role_valid_from = datetime(2025, 1, 1, tzinfo=dt_timezone.utc)
role_valid_to = datetime(2099, 1, 1, tzinfo=dt_timezone.utc)

country, _ = Countries.objects.get_or_create(country_name="Australia")
state, _ = CountryStates.objects.get_or_create(country=country, state_name="NSW")
track, _ = Tracks.objects.get_or_create(
    track_name="AUS-NSW-CHAT",
    defaults={"state": state},
)
if track.state_id != state.id:
    track.state = state
    track.save(update_fields=["state"])

group, _ = Groups.objects.get_or_create(group_name="Chat Demo", track=track)

def upsert_user(email, first_name, last_name, password):
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "track": track,
            "account_status": "active",
            "is_active": True,
        },
    )
    user.first_name = first_name
    user.last_name = last_name
    user.track = track
    user.account_status = "active"
    user.is_active = True
    user.set_password(password)
    user.save()
    return user

student = upsert_user("student-chat@example.com", "Student", "Chat", "pw123456")
mentor = upsert_user("mentor-chat@example.com", "Mentor", "Chat", "pw123456")
supervisor = upsert_user("supervisor-chat@example.com", "Supervisor", "Chat", "pw123456")
outsider = upsert_user("outsider-chat@example.com", "Outsider", "Chat", "pw123456")

roles = {
    name: Roles.objects.get_or_create(role_name=name)[0]
    for name in ["basic_student", "mentor", "supervisor"]
}

for user, role_name in [
    (student, "basic_student"),
    (mentor, "mentor"),
    (supervisor, "supervisor"),
]:
    RoleAssignmentHistory.objects.update_or_create(
        user=user,
        role=roles[role_name],
        valid_from=role_valid_from,
        defaults={"valid_to": role_valid_to},
    )

GroupMembership.objects.get_or_create(
    user=student,
    group=group,
    defaults={"membership_role": "student"},
)
GroupMembership.objects.get_or_create(
    user=mentor,
    group=group,
    defaults={"membership_role": "mentor"},
)
GroupMembership.objects.get_or_create(
    user=supervisor,
    group=group,
    defaults={"membership_role": "mentor"},
)

print("Group ID:", group.id)
print("Student:", student.email)
print("Mentor:", mentor.email)
print("Supervisor:", supervisor.email)
print("Outsider:", outsider.email)
PY
```

If you are running Django directly from your host shell, first export the local `DB_*` variables shown above, then run this from `backend/`:

```bash
python manage.py shell <<'PY'
from datetime import datetime, timezone as dt_timezone

from apps.groups.models import Countries, CountryStates, GroupMembership, Groups, Tracks
from apps.resources.models import RoleAssignmentHistory, Roles
from apps.users.models import User

role_valid_from = datetime(2025, 1, 1, tzinfo=dt_timezone.utc)
role_valid_to = datetime(2099, 1, 1, tzinfo=dt_timezone.utc)

country, _ = Countries.objects.get_or_create(country_name="Australia")
state, _ = CountryStates.objects.get_or_create(country=country, state_name="NSW")
track, _ = Tracks.objects.get_or_create(
    track_name="AUS-NSW-CHAT",
    defaults={"state": state},
)
if track.state_id != state.id:
    track.state = state
    track.save(update_fields=["state"])

group, _ = Groups.objects.get_or_create(group_name="Chat Demo", track=track)

def upsert_user(email, first_name, last_name, password):
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "track": track,
            "account_status": "active",
            "is_active": True,
        },
    )
    user.first_name = first_name
    user.last_name = last_name
    user.track = track
    user.account_status = "active"
    user.is_active = True
    user.set_password(password)
    user.save()
    return user

student = upsert_user("student-chat@example.com", "Student", "Chat", "pw123456")
mentor = upsert_user("mentor-chat@example.com", "Mentor", "Chat", "pw123456")
supervisor = upsert_user("supervisor-chat@example.com", "Supervisor", "Chat", "pw123456")
outsider = upsert_user("outsider-chat@example.com", "Outsider", "Chat", "pw123456")

roles = {
    name: Roles.objects.get_or_create(role_name=name)[0]
    for name in ["basic_student", "mentor", "supervisor"]
}

for user, role_name in [
    (student, "basic_student"),
    (mentor, "mentor"),
    (supervisor, "supervisor"),
]:
    RoleAssignmentHistory.objects.update_or_create(
        user=user,
        role=roles[role_name],
        valid_from=role_valid_from,
        defaults={"valid_to": role_valid_to},
    )

GroupMembership.objects.get_or_create(
    user=student,
    group=group,
    defaults={"membership_role": "student"},
)
GroupMembership.objects.get_or_create(
    user=mentor,
    group=group,
    defaults={"membership_role": "mentor"},
)
GroupMembership.objects.get_or_create(
    user=supervisor,
    group=group,
    defaults={"membership_role": "mentor"},
)

print("Group ID:", group.id)
print("Student:", student.email)
print("Mentor:", mentor.email)
print("Supervisor:", supervisor.email)
print("Outsider:", outsider.email)
PY
```

Use the printed `Group ID` for all examples below.

If you see an error like:

```text
django.db.utils.OperationalError: connection failed ... no pg_hba.conf entry ... no encryption
```

that means Django is still trying to connect to the remote Azure/Postgres database instead of your local dev Postgres.

Fix it by doing one of these:

1. Run the seed command inside the `web` container with `docker compose exec web ...`
2. Export local values before running from the host shell:

```bash
export DJANGO_SETTINGS_MODULE=config.settings_local
export DB_NAME=biotech_dev
export DB_USER=biotech
export DB_PASSWORD=biotech
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_SSLMODE=disable
```

## Authenticate and Capture Session Cookies

WebSocket auth currently uses Django session cookies, not JWT.

The easiest manual login flow for developers is the password login endpoint:

- `POST /users/login/`

Example:

```bash
curl -sS -c /tmp/student.cookies \
  -X POST http://127.0.0.1:8000/users/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"student-chat@example.com","password":"pw123456"}'
```

Repeat for the other users:

```bash
curl -sS -c /tmp/mentor.cookies \
  -X POST http://127.0.0.1:8000/users/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"mentor-chat@example.com","password":"pw123456"}'

curl -sS -c /tmp/supervisor.cookies \
  -X POST http://127.0.0.1:8000/users/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"supervisor-chat@example.com","password":"pw123456"}'

curl -sS -c /tmp/outsider.cookies \
  -X POST http://127.0.0.1:8000/users/login/ \
  -H 'Content-Type: application/json' \
  -d '{"email":"outsider-chat@example.com","password":"pw123456"}'
```

For REST calls, reuse the cookie jar with `-b /tmp/<name>.cookies`.

## CSRF for REST Writes

The chat REST endpoints use Django session auth through DRF `SessionAuthentication`.

That means:

- `GET` requests usually work with just the session cookie
- `POST`, `PATCH`, and `DELETE` also require a CSRF token
- WebSocket testing does not use CSRF, because the socket path is authenticated by the session cookie in the handshake

If you skip the CSRF header on a write request, you will see errors like:

```text
CSRF token missing
```

### Fetch a CSRF Cookie

After login, make one GET request that sets a CSRF cookie into the same cookie jar:

```bash
curl -sS \
  -b /tmp/student.cookies \
  -c /tmp/student.cookies \
  http://127.0.0.1:8000/api-auth/login/ > /dev/null
```

Extract the token:

```bash
STUDENT_CSRF=$(awk '$6 == "csrftoken" {print $7}' /tmp/student.cookies)
```

You can do the same for other users:

```bash
curl -sS -b /tmp/mentor.cookies -c /tmp/mentor.cookies http://127.0.0.1:8000/api-auth/login/ > /dev/null
curl -sS -b /tmp/supervisor.cookies -c /tmp/supervisor.cookies http://127.0.0.1:8000/api-auth/login/ > /dev/null

MENTOR_CSRF=$(awk '$6 == "csrftoken" {print $7}' /tmp/mentor.cookies)
SUPERVISOR_CSRF=$(awk '$6 == "csrftoken" {print $7}' /tmp/supervisor.cookies)
```

### Use the CSRF Header on REST Writes

Example `POST`:

```bash
curl -sS \
  -b /tmp/student.cookies \
  -X POST http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $STUDENT_CSRF" \
  -d '{"message_text":"hello from REST","resources":[]}'
```

Example `PATCH`:

```bash
curl -sS \
  -b /tmp/student.cookies \
  -X PATCH http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/<MESSAGE_ID>/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $STUDENT_CSRF" \
  -d '{"message_text":"edited from REST"}'
```

Example `DELETE`:

```bash
curl -i \
  -b /tmp/mentor.cookies \
  -X DELETE http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/<MESSAGE_ID>/ \
  -H "X-CSRFToken: $MENTOR_CSRF"
```

## Manual REST API Checks

Replace `<GROUP_ID>` with the seeded group ID.

### Create a Message via REST

```bash
curl -sS -b /tmp/student.cookies \
  -X POST http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/ \
  -H 'Content-Type: application/json' \
  -H "X-CSRFToken: $STUDENT_CSRF" \
  -d '{"message_text":"hello from REST","resources":[]}'
```

Expected result:

- `201 Created`
- response contains the new message object

### List Messages

```bash
curl -sS -b /tmp/student.cookies \
  "http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/?limit=20"
```

Expected result:

- `200 OK`
- response contains `items`
- most recent messages appear first

### Edit a Message

Use a real message ID from the previous response:

```bash
curl -sS -b /tmp/student.cookies \
  -X PATCH http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/<MESSAGE_ID>/ \
  -H 'Content-Type: application/json' \
  -H "X-CSRFToken: $STUDENT_CSRF" \
  -d '{"message_text":"edited from REST"}'
```

Expected result:

- `200 OK`
- response contains updated `message_text`
- `edited_at` is set

### Delete a Message as Mentor or Supervisor

```bash
curl -i -b /tmp/mentor.cookies \
  -X DELETE http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/<MESSAGE_ID>/ \
  -H "X-CSRFToken: $MENTOR_CSRF"
```

Expected result:

- `204 No Content`

### Delete a Message as Student

```bash
curl -i -b /tmp/student.cookies \
  -X DELETE http://127.0.0.1:8000/chat/groups/<GROUP_ID>/messages/<MESSAGE_ID>/ \
  -H "X-CSRFToken: $STUDENT_CSRF"
```

Expected result:

- `403 Forbidden`

## Manual WebSocket Checks with wscat

Important current limitation:

- `docker compose ... up web` is not enough for manual websocket testing in this repo today
- I reproduced `wscat` returning `Unexpected server response: 404` against the running `web` container
- The route is correct; the issue is that the current container is running plain Django `runserver`, not an ASGI websocket server

### Start a Local ASGI Server for WebSocket Testing

Keep your Docker `postgres`, `redis`, and `celery-worker` services running, but start a separate local ASGI server from the host shell:

```bash
cd backend
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE=config.settings_local
export DB_NAME=biotech_dev
export DB_USER=biotech
export DB_PASSWORD=biotech
export DB_HOST=127.0.0.1
export DB_PORT=5432
export DB_SSLMODE=disable
export REDIS_HOST=127.0.0.1
export REDIS_PORT=6379
./.venv/bin/python -m daphne -b 127.0.0.1 -p 8001 config.asgi:application
```

Safer alternative:

- if your shell has old Azure or other database variables lying around, use a clean environment for Daphne
- this avoids accidental reuse of `DB_HOST`, `DB_USER`, `DB_NAME`, or `DB_SSLMODE` from another terminal session

```bash
cd backend
env -i HOME="$HOME" PATH="$PATH" PYTHONPATH="$PYTHONPATH" \
  DJANGO_SETTINGS_MODULE=config.settings_local \
  DB_NAME=biotech_dev \
  DB_USER=biotech \
  DB_PASSWORD=biotech \
  DB_HOST=127.0.0.1 \
  DB_PORT=5432 \
  DB_SSLMODE=disable \
  REDIS_HOST=127.0.0.1 \
  REDIS_PORT=6379 \
  ./.venv/bin/python -m daphne -b 127.0.0.1 -p 8001 config.asgi:application
```

### Sanity-Check the DB Settings Before Starting Daphne

Run this from the same shell where you plan to start Daphne:

```bash
cd backend
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default'])"
```

Expected values for local host-based Daphne testing:

- `NAME`: `biotech_dev`
- `USER`: `biotech`
- `PASSWORD`: `biotech`
- `HOST`: `127.0.0.1`
- `PORT`: `5432`
- `OPTIONS['sslmode']`: `disable`

If you see values like these instead:

- `biotechDev`
- `biotech_admin`
- `23.101.238.222`
- `sslmode=require`

then Daphne is still pointing at the Azure database configuration, not local Postgres.

Use that ASGI server for websocket testing:

```text
ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/
```

If `wscat` is not installed globally, `npx` is fine:

```bash
npx wscat --help
```

Extract the session cookie values:

```bash
STUDENT_SESSION=$(awk '$6 == "sessionid" {print $7}' /tmp/student.cookies)
MENTOR_SESSION=$(awk '$6 == "sessionid" {print $7}' /tmp/mentor.cookies)
OUTSIDER_SESSION=$(awk '$6 == "sessionid" {print $7}' /tmp/outsider.cookies)
```

### Connect as Two Participants

Terminal 1:

```bash
npx wscat -c ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/ \
  -H "Cookie: sessionid=$STUDENT_SESSION"
```

Terminal 2:

```bash
npx wscat -c ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/ \
  -H "Cookie: sessionid=$MENTOR_SESSION"
```

Expected result:

- both connections succeed

### Send a Message over WebSocket

From Terminal 1:

```json
{"type":"message.send","body":"hello over websocket"}
```

Expected result:

- both Terminal 1 and Terminal 2 receive:

```json
{
  "type": "message.created",
  "message": {
    "id": 123,
    "conversation_id": <GROUP_ID>,
    "sender_id": <student_user_id>,
    "body": "hello over websocket",
    "created_at": "..."
  }
}
```

### Start Typing

From Terminal 1:

```json
{"type":"typing.start"}
```

Expected result:

- Terminal 2 receives:

```json
{
  "type": "typing.started",
  "conversation_id": <GROUP_ID>,
  "user_id": <student_user_id>
}
```

- Terminal 1 does not receive the same typing event back

### Stop Typing

From Terminal 1:

```json
{"type":"typing.stop"}
```

Expected result:

- Terminal 2 receives:

```json
{
  "type": "typing.stopped",
  "conversation_id": <GROUP_ID>,
  "user_id": <student_user_id>
}
```

### Typing Debounce Check

From Terminal 1, quickly send `typing.start` twice:

```json
{"type":"typing.start"}
{"type":"typing.start"}
```

Expected result:

- Terminal 2 should only receive one immediate `typing.started`

### Non-Participant Connect Denial

```bash
npx wscat -c ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/ \
  -H "Cookie: sessionid=$OUTSIDER_SESSION"
```

Expected result:

- the connection is rejected

### Common `wscat` 404 Causes

If `wscat` prints:

```text
error: unexpected server response 404
```

check these first:

1. The URL must include the trailing slash:

```text
ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/
```

not:

```text
ws://127.0.0.1:8001/ws/chat/<GROUP_ID>
```

2. Use the current route, not the old route:

```text
/ws/chat/<GROUP_ID>/
```

not:

```text
/ws/chat/groups/<GROUP_ID>/
```

3. Connect to the Django backend port, not the frontend dev server port:

```text
ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/
```

not:

```text
ws://127.0.0.1:5173/ws/chat/<GROUP_ID>/
```

4. `<GROUP_ID>` must be numeric, because the route only matches digits

5. Make sure the backend process you started is an ASGI server serving `config.asgi:application`

6. If you point `wscat` at the current Docker `web` service on port `8000`, a 404 is expected in the current setup

## Browser-Based WebSocket Check

If you prefer not to use `wscat`:

1. Log in through the backend on `http://127.0.0.1:8000`
2. Open browser devtools on a page served from the same backend origin
3. Run:

```js
const ws = new WebSocket("ws://127.0.0.1:8001/ws/chat/<GROUP_ID>/");
ws.onopen = () => console.log("open");
ws.onmessage = (event) => console.log(JSON.parse(event.data));
ws.onerror = (event) => console.log("error", event);
```

Then send:

```js
ws.send(JSON.stringify({ type: "message.send", body: "hello from browser console" }));
ws.send(JSON.stringify({ type: "typing.start" }));
ws.send(JSON.stringify({ type: "typing.stop" }));
```

If you are testing from a browser console on a different origin than `127.0.0.1:8001`, the browser cookie behavior may differ. `wscat` is the more predictable manual test path here.

## Verify Celery Side Effects

Keep the worker logs open:

```bash
docker compose -f docker-compose.dev.yml logs -f celery-worker
```

Then create a message by REST or WebSocket.

Expected result:

- the worker should pick up `chat.process_chat_message_created`
- the task should prepare recipient-side `MessageStatus` rows for group members other than the sender

Check from the Django shell:

```bash
python manage.py shell <<'PY'
from apps.chat.models import MessageStatus, Messages

message = Messages.objects.order_by("-id").first()
print("Latest message:", message.id, message.message_text)
print(
    list(
        MessageStatus.objects.filter(message=message)
        .order_by("user_id")
        .values("user_id", "status")
    )
)
PY
```

Expected result:

- sender is not included
- other active group members are included
- status should start as `sent`

## Test "Celery Worker Down but Chat Still Works"

Start only:

- `postgres`
- `redis`
- `web`

Do not start:

- `celery-worker`

Then send a message by WebSocket or REST.

Expected result:

- the message still persists
- the WebSocket broadcast still works
- the Celery side-effect task does not execute until a worker is available

Do not stop `redis` for this check. In this project, Redis is also used by Channels, so turning Redis off tests a broader infrastructure outage rather than just a stopped Celery worker.

## Troubleshooting

### WebSocket connect is denied

Check:

- the user is logged in through a Django session
- the `sessionid` cookie is actually being sent
- the user has an active `GroupMembership` row for the target group

### Message creates by REST but WebSocket receives nothing

Check:

- Redis is running
- the Django app is using `config.settings_local`
- you connected to `/ws/chat/<GROUP_ID>/`
- you are testing with group members, not outsiders

### WebSocket works but no Celery side effects appear

Check:

- `celery-worker` is running
- Redis is running
- the worker logs are active
- the worker is pointed at the same settings and Redis instance as the web app

### Delete returns 403 for mentor or supervisor

Check:

- the user has an active `RoleAssignmentHistory` row with a valid future `valid_to`
- the user is also an active member of the same group

### Daphne on `8001` returns websocket `500`

This usually means the ASGI app started, but failed when it tried to access the database during websocket connect.

Common causes:

- Daphne was started from a shell that still had Azure `DB_*` variables
- `DB_SSLMODE` was left at `require`
- the host-shell Daphne process is not pointed at `127.0.0.1:5432`

What to do:

1. Stop Daphne
2. Run the DB settings sanity-check command above
3. Start Daphne again with the clean `env -i ... daphne ...` command

## Useful Files to Read While Testing

- `backend/apps/chat/views.py`
- `backend/apps/chat/management/consumers.py`
- `backend/apps/chat/tasks.py`
- `backend/apps/chat/management/routing.py`
- `backend/tests/apps/chat/test_chat.py`
