# Soft Delete Runbook

This runbook explains how to operate and verify the soft-delete functionality on
this branch. Use it as the high-level checklist, then use
`backend/docs/soft_delete_frontend_testing.md` and
`backend/docs/soft_delete_recovery_integration.md` for deeper UI and API
contracts.

## Scope

Soft delete is implemented for these product areas:

| Area | Normal delete result | Recovery surface |
| --- | --- | --- |
| Groups | Group leaves active lists and active group access | Admin web Group Recovery |
| Group messages | Message is tombstoned and hidden or shown as deleted based on caller/UI | Admin web group message dialog with Show deleted |
| Tasks | Task leaves active lists | User frontend task Show deleted, admin web Task Recovery for group tasks |
| Resources | Resource leaves active catalogue lists | Admin web Resource Recovery |
| Events | Event leaves active event lists | Admin web Event Recovery |

Soft delete means the row remains in the database with a non-null `deleted_at`.
Restore is always a dedicated `POST .../restore` or `POST .../restore/`
mutation. Do not restore by PATCHing `deleted_at`.

## Roles

Use these role expectations when validating behavior:

| Actor | Expected capability |
| --- | --- |
| Global admin | Can delete and restore in every track-scoped admin surface. |
| Track admin | Can delete and restore rows in their assigned track scope. |
| Mentor | Can create, delete, and restore group tasks for their group scope. |
| Supervisor | Can view relevant group/task context, but should not manage group task recovery unless explicitly granted. |
| User/student | Can restore their own deleted individual tasks from the user frontend. |

Admin checks should use the project admin scope model: global admin or track
admin. Do not rely on Django `is_staff` or `is_superuser` for product recovery
rules.

## Local Setup

Start the backend:

```bash
cd backend
.venv/bin/python manage.py runserver --settings=config.settings_local
```

Start the user frontend:

```bash
cd frontend
npm run dev
```

Start the admin web app:

```bash
cd adminweb
pnpm dev
```

Create local test accounts:

```bash
cd backend
.venv/bin/python manage.py create_test_accounts --settings=config.settings_local --reset-password
```

Default password:

```text
Password123!
```

Default accounts:

| Email | Role |
| --- | --- |
| `global.admin@example.com` | Global admin |
| `track.admin@example.com` | Track admin |
| `mentor@example.com` | Mentor |
| `supervisor@example.com` | Supervisor |
| `user@example.com` | Basic user |

Local URLs:

| App | URL |
| --- | --- |
| User frontend | `http://localhost:5173` |
| Admin web | `http://localhost:3000` |
| Backend API docs | `http://localhost:8000/api/docs/` |

## Browser Verification Setup

Before running any UI test:

1. Open browser developer tools.
2. Open the Network tab.
3. Enable Preserve log.
4. Filter by Fetch/XHR.
5. Keep the Console tab visible.

For every delete and restore, record:

- Request URL, method, and status.
- Response body.
- Whether `deleted_at` changed as expected.
- Whether the visible list updates without a refresh.
- Whether a browser refresh preserves the expected active/deleted state.

## Core API Contract

Normal list endpoints should return active rows only unless a deleted/recovery
filter is explicitly used.

| Entity | Active list | Deleted list | Restore |
| --- | --- | --- | --- |
| App groups | `GET /api/v1/groups/groups/` | `GET /api/v1/groups/groups/?include_deleted=true` | `POST /api/v1/groups/groups/{id}/restore/` |
| App chat messages | `GET /api/v1/chat/groups/{groupId}/messages/` | `GET /api/v1/chat/groups/{groupId}/messages/deleted/` | `POST /api/v1/chat/groups/{groupId}/messages/{id}/restore/` |
| App tasks | `GET /api/v1/tasks/` | `GET /api/v1/tasks/?deleted=true` | `POST /api/v1/tasks/{id}/restore/` |
| App resources | `GET /api/v1/resources/resource-files/` | `GET /api/v1/resources/resource-files/?deleted=true` | `POST /api/v1/resources/resource-files/{id}/restore/` |
| App events | `GET /api/v1/events/` | `GET /api/v1/events/?deleted=true&when=all` | `POST /api/v1/events/{id}/restore/` |
| Admin groups | `GET /api/v1/group` | `GET /api/v1/group?deleted=true` | `POST /api/v1/group/{id}/restore` |
| Admin group messages | `GET /api/v1/group/{groupId}/messages` | `GET /api/v1/group/{groupId}/messages?deleted=true` | `POST /api/v1/group/{groupId}/messages/{id}/restore` |
| Admin tasks | `GET /api/v1/admin/task/` | `GET /api/v1/admin/task/?task_type=group&deleted=true` | `POST /api/v1/admin/task/{id}/restore/` |
| Admin resources | `GET /api/v1/resource` | `GET /api/v1/resource?deleted=true` | `POST /api/v1/resource/{id}/restore` |
| Admin events | `GET /api/v1/event` | `GET /api/v1/event?deleted=true` | `POST /api/v1/event/{id}/restore` |

Expected restore response:

- HTTP `200`.
- Restored object has `deleted_at: null` or equivalent admin-web field.
- Chat message restore returns `is_deleted: false`.

Expected delete response:

- HTTP `200` or `204`, depending on the endpoint.
- Follow-up deleted-list request includes the row.
- Follow-up active-list request excludes the row.

## Admin Web Runbook

### Group Recovery

Surface:

```text
/group
```

Checklist:

1. Log in as global admin or an in-scope track admin.
2. Create a test group or select a safe existing group.
3. Delete the group from the group table.
4. Verify `DELETE /api/v1/group/{id}` succeeds.
5. Verify the group leaves the active group table.
6. In Group Recovery, verify the deleted group appears.
7. Restore the group.
8. Verify `POST /api/v1/group/{id}/restore` succeeds.
9. Verify the group leaves Group Recovery and returns to the active table.

Name reuse rule:

- A deleted group name can be reused.
- Two active groups with the same name in the same track must not exist.
- If restore fails because the name is already active again, rename or delete
  the conflicting active group before restoring.

### Group Message Recovery

Surface:

```text
/group
Group row -> message dialog
```

Checklist:

1. Open a group message dialog from admin web.
2. Delete a message.
3. Verify `DELETE /api/v1/group/{groupId}/messages/{messageId}` succeeds.
4. In the same dialog, enable Show deleted.
5. Verify `GET /api/v1/group/{groupId}/messages?deleted=true` runs.
6. Confirm deleted messages show deleted metadata.
7. Restore a deleted message.
8. Verify `POST /api/v1/group/{groupId}/messages/{messageId}/restore`
   succeeds.

Display expectations:

- If an admin deletes a group message, user-facing discussion boards should show
  `Admin deleted a message` to all users.
- Deleted message text, attachments, GIFs, and previews should not leak through
  the deleted-state UI.
- Restored messages should reappear through the normal message list.

### Task Recovery

Surface:

```text
/task
```

Checklist:

1. Log in as global admin or an in-scope track admin.
2. Create or select a group task.
3. Delete the group task from the task table.
4. Verify `DELETE /api/v1/admin/task/{id}/` succeeds.
5. Verify the task leaves the active task table.
6. In Task Recovery, verify the deleted group task appears.
7. Restore the task.
8. Verify `POST /api/v1/admin/task/{id}/restore/` succeeds.
9. Verify the task leaves Task Recovery and returns to the active table.

Important:

- Admin web Task Recovery is for group tasks.
- Individual tasks should not appear in the admin recovery table.
- Individual tasks should not show admin restore actions.
- Users restore their own deleted individual tasks from the user frontend.

### Resource Recovery

Surface:

```text
/resource
```

Checklist:

1. Log in as global admin or an in-scope track admin.
2. Upload or select a safe resource.
3. Delete the resource.
4. Verify `DELETE /api/v1/resource/{id}` succeeds.
5. Verify the resource leaves the active resource table.
6. In Resource Recovery, verify the deleted resource appears.
7. Restore the resource.
8. Verify `POST /api/v1/resource/{id}/restore` succeeds.
9. Verify the resource leaves Resource Recovery and returns to the active table.

Notes:

- Resource recovery covers admin-managed resource catalogue rows.
- Chat uploaded files are message attachments, not resource catalogue rows.
- If an uploaded/downloaded blob returns `BlobNotFound`, verify the stored blob
  path and the storage container before treating it as a soft-delete issue.

### Event Recovery

Surface:

```text
/event
```

Checklist:

1. Log in as global admin or an in-scope track admin.
2. Create or select a safe event.
3. Delete the event.
4. Verify `DELETE /api/v1/event/{id}` succeeds.
5. Verify the event leaves the active event table.
6. In Event Recovery, verify the deleted event appears.
7. Restore the event.
8. Verify `POST /api/v1/event/{id}/restore` succeeds.
9. Verify the event leaves Event Recovery and returns to the active table.

Notes:

- Restoring an event preserves RSVP rows.
- If an event targets a deleted group, restore the group first.

## User Frontend Runbook

### Group Tasks

Surface:

```text
/groups/{groupId}
```

Checklist:

1. Log in as a user who can manage the task.
2. Create or select a test task.
3. Delete the task.
4. Verify `DELETE /api/v1/tasks/{id}/` succeeds.
5. Verify the task leaves the normal task list.
6. Refresh the page and verify it does not reappear in the normal list.
7. Enable Show deleted.
8. Verify `GET /api/v1/tasks/?deleted=true` runs.
9. Restore the task if the logged-in user is allowed.
10. Verify `POST /api/v1/tasks/{id}/restore/` succeeds.

Expected permissions:

- Users can restore their own deleted individual tasks.
- Mentors and admins can restore group tasks.
- Supervisors and students should not create, delete, or restore group tasks.

Filter expectations:

- Show deleted should show deleted tasks only.
- If no deleted tasks match the filter, the task list should be empty.
- Refreshing the page while Show deleted is enabled should keep deleted tasks
  visible.

### Discussion Board Messages

Surface:

```text
/groups/{groupId}
```

Checklist:

1. Send a normal text message.
2. Delete it as the sender.
3. Verify the sender sees `You deleted a message`.
4. Verify other users see `{user_name} deleted a message`.
5. Send a message and delete it as a global admin or track admin.
6. Verify all users see `Admin deleted a message`.
7. Refresh the page and verify the deleted-state display is still correct.
8. Send a GIF message and keep the board open for at least 10 seconds.
9. Verify the GIF does not disappear after recent-message sync runs.

Network expectations:

- Delete uses `DELETE /api/v1/chat/groups/{groupId}/messages/{id}/`.
- WebSocket `message.deleted` should update the board without requiring a
  refresh.
- Recent message sync should not change GIF messages into text messages.

## Dependency Restore Order

When restore is blocked, restore parents first:

1. Restore a deleted group.
2. Restore deleted group tasks/messages/resources/events linked to that group.
3. Restore deleted child tasks after their parent task is active.

Common blockers:

| Status | Meaning | Action |
| --- | --- | --- |
| `400` | Active name conflict or deleted parent dependency | Resolve the conflict or restore the parent first. |
| `403` | Caller is outside admin/user scope | Use the correct global admin, track admin, mentor, or owner account. |
| `404` | Row is not visible or does not exist | Confirm the ID, route, deleted filter, and track scope. |
| `500` | Unexpected backend error | Check backend logs and reproduce with the API route directly. |

## Regression Checklist

Run this checklist before merging soft-delete changes:

- Active lists exclude deleted rows.
- Deleted recovery lists include only deleted rows.
- Restore uses a dedicated restore endpoint.
- Restore returns the row with `deleted_at: null`.
- Browser refresh preserves the correct active/deleted state.
- Admin web exposes dedicated recovery tables for groups, tasks, resources, and
  events.
- Admin web group message dialog exposes Show deleted.
- Group task recovery excludes individual tasks.
- User frontend allows users to restore their own individual tasks.
- Admin delete of group messages displays `Admin deleted a message`.
- GIF messages remain visible after WebSocket delivery and recent-message sync.
- Track admins cannot recover rows outside their track scope.
- Global admins can recover rows across tracks.

## Automated Checks

Backend:

```bash
cd backend
.venv/bin/python manage.py test --settings=config.settings_test
```

Focused backend tests:

```bash
cd backend
.venv/bin/python manage.py test tests apps.users apps.resources --settings=config.settings_test --noinput
```

User frontend:

```bash
cd frontend
npm run build
```

Admin web:

```bash
cd adminweb
pnpm install --frozen-lockfile
pnpm build
```

## Troubleshooting

Deleted rows still show in active UI:

- Confirm the request is not using `deleted=true` or `include_deleted=true`.
- Confirm the backend queryset filters `deleted_at__isnull=True` for normal
  list/detail flows.
- Confirm the frontend removes or refetches the row after successful delete.

Show deleted displays active rows:

- Confirm the request includes `deleted=true`.
- Confirm the response rows have non-null `deleted_at`.
- Confirm the frontend does not fall back to the active list when the deleted
  response is empty.

Restore button is missing:

- Confirm the user has the correct role/scope.
- Confirm the current table is a recovery table, not an active table.
- For admin tasks, confirm the row is a group task. Individual task restore is
  intentionally not exposed in admin web.

Admin message delete does not update immediately:

- Confirm the delete request succeeds.
- Confirm the WebSocket receives `message.deleted`.
- Confirm the frontend handler updates or removes the existing message without
  waiting for a full refresh.

`Admin deleted a message` does not appear:

- Confirm the deleting account is a global admin or track admin in product
  admin scope.
- Confirm the delete response or WebSocket payload includes admin delete
  metadata.
- Confirm the frontend uses `deleted_by_is_admin` or `deletedByIsAdmin` instead
  of Django staff/superuser checks.

GIF messages disappear:

- Confirm the message payload has `message_type: "gif"` and a GIF URL in either
  `gif.gif_url`, `gif.url`, `gifUrl`, or `gif_url`.
- Confirm recent-message sync preserves already-normalized `messageType` and
  `gifUrl`.

Resource upload returns HTTP 500:

- Check backend logs for the concrete exception.
- Verify Azure/local storage settings are present.
- Verify uploaded file validation and blob upload complete before the resource
  row is created.

Static web deploy fails because of staging environments:

- Delete unused Azure Static Web App preview environments.
- Re-run the workflow after the preview environment quota is below the limit.

