# Soft Delete Frontend Testing

This guide explains how to test soft-delete behavior through the user frontend
and admin web interface.

Use it with the backend contract in
`backend/docs/soft_delete_recovery_integration.md`.

## What To Prove

For every soft-delete flow, verify these behaviors:

- Delete removes the row from normal active UI lists.
- The backend response or follow-up request shows a non-null `deleted_at`.
- Refreshing the page does not bring the deleted row back into the active list.
- Recovery lists use `deleted=true` or `include_deleted=true`.
- Restore uses a dedicated `POST .../restore/` request.
- Restored rows return to active UI lists with `deleted_at: null`.
- Child rows cannot be restored before their deleted parent is restored.
- Unauthorized users cannot see or restore deleted rows outside their scope.

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

Create local test accounts if needed:

```bash
cd backend
.venv/bin/python manage.py create_test_accounts --settings=config.settings_local --reset-password
```

Default accounts:

```text
global.admin@example.com   Global admin
track.admin@example.com    Track admin for AUS-NSW
mentor@example.com         Mentor
supervisor@example.com     Supervisor
user@example.com           Basic user
```

Default password:

```text
Password123!
```

Open:

```text
User frontend: http://localhost:5173
Admin web:     http://localhost:3000
Backend docs:  http://localhost:8000/api/docs/
```

## Browser Setup

Open browser developer tools before testing:

1. Go to the Network tab.
2. Enable Preserve log.
3. Filter by `Fetch/XHR`.
4. Keep the Console tab visible for client errors.

For each delete or restore action, capture the request URL, HTTP method, status
code, response body, `deleted_at`, and whether the visible UI list updates.

## Current UI Coverage

Available through UI today:

- User frontend task delete, `Show deleted` display, and restore for permitted
  task rows.
- User frontend chat message delete.
- Admin web resource delete.
- Admin web event delete.
- Admin web task delete.
- Admin web group member and group message removal.
- Admin web user delete.

Recovery UI is not implemented for every entity yet. Where no Restore button
exists, verify the delete path through the frontend and use the Network tab or
backend docs to confirm the corresponding recovery contract.

## User Frontend: Group Tasks

Surface:

```text
http://localhost:5173/groups/{groupId}
```

Test delete:

1. Log in as a user who can manage tasks in a group.
2. Open a group detail page.
3. In the Tasks panel, create a test task if one does not already exist.
4. Delete the task from the task row action.
5. Confirm the delete dialog.
6. In Network, verify `DELETE /api/v1/tasks/{taskId}/`.

Expected:

- The response is successful.
- Response body includes the deleted task with non-null `deleted_at`.
- The task disappears from the normal task list.
- Refreshing the group page does not show the task in the normal task list.

Test deleted visibility:

1. Open the task filter panel.
2. Enable `Show deleted`.
3. Confirm the deleted task is visible as a deleted task row.
4. Disable `Show deleted`.
5. Confirm the deleted task is hidden again.

Expected recovery-list request:

```text
GET /api/v1/tasks/?deleted=true
```

Restore contract:

```text
POST /api/v1/tasks/{taskId}/restore/
```

Test restore:

1. Enable `Show deleted`.
2. Find a deleted individual task assigned to the logged-in user.
3. Click the restore action.
4. In Network, verify `POST /api/v1/tasks/{taskId}/restore/`.
5. Confirm the row leaves the deleted list.
6. Disable `Show deleted`.
7. Confirm the task appears in the normal active task list with
   `deleted_at: null`.

Permission expectations:

- Users can restore their own deleted individual tasks.
- Mentors and admins can restore group tasks.
- Supervisors and students cannot create, delete, or restore group tasks.

## User Frontend: Chat Messages

Surface:

```text
http://localhost:5173/groups/{groupId}
```

Test delete:

1. Log in as the message sender or an admin user.
2. Open a group chat.
3. Send a unique message, for example `soft delete test message`.
4. Use the message action menu to delete it.
5. Confirm the delete dialog.
6. In Network, verify `DELETE /api/v1/chat/groups/{groupId}/messages/{messageId}/`.

Expected:

- The deleted message is removed from the current chat list or rendered as a
  deleted message depending on the event path.
- Refreshing the page does not show the message as active.
- If websocket events are visible, `message.deleted` updates local state
  without a full page reload.

Recovery contract:

```text
GET  /api/v1/chat/groups/{groupId}/messages/deleted/
POST /api/v1/chat/groups/{groupId}/messages/{messageId}/restore/
```

Expected restore behavior:

- Only an operational admin for the group track can restore deleted messages.
- Original senders cannot restore their own deleted messages unless they also
  have admin scope.
- Restored message responses include `is_deleted: false`.

Note: the user frontend currently does not provide a dedicated
deleted-message recovery UI.

## Admin Web: Resources

Surface:

```text
http://localhost:3000/resource
```

Test delete:

1. Log in as `global.admin@example.com` or an in-scope track admin.
2. Create or find a resource that is safe to delete.
3. Delete the resource from the resource row action.
4. Confirm the dialog.
5. In Network, verify `DELETE /api/v1/admin/resource/{resourceId}/`.

Expected:

- The resource disappears from the admin resource table.
- Refreshing `/resource` does not show the resource in the active table.
- A recovery-list request shows the row with non-null `deleted_at`:

```text
GET /api/v1/resources/resource-files/?deleted=true
```

Restore contract:

```text
POST /api/v1/resources/resource-files/{resourceId}/restore/
```

Expected restore behavior:

- Global admin can restore any resource.
- Track admin can restore resources in their scoped tracks.
- A restore blocked by an active name conflict should return `400`.
- A restored resource returns to the active resource table after refresh.

Known limitation: admin web currently exposes resource delete, but not a
dedicated resource recovery table.

## Admin Web: Events

Surface:

```text
http://localhost:3000/event
```

Test delete:

1. Log in as a global admin or in-scope track admin.
2. Create a test event with a unique name.
3. Delete the event from the event row action.
4. Confirm the dialog.
5. In Network, verify `DELETE /api/v1/admin/event/{eventId}/`.

Expected:

- The event disappears from the admin event table.
- Refreshing `/event` does not show it in active event lists.
- The user frontend `/events` page does not show it as an active event.

Recovery-list contract:

```text
GET /api/v1/events/?deleted=true&when=all
```

Restore contract:

```text
POST /api/v1/events/{eventId}/restore/
```

Expected restore behavior:

- Restored event has `deleted_at: null`.
- Existing RSVP rows are preserved.
- Restore should fail with `400` if the event targets a deleted group that must
  be restored first.

Known limitation: admin web currently exposes event delete, but not a dedicated
event recovery table.

## Admin Web: Tasks

Surface:

```text
http://localhost:3000/task
```

Test delete:

1. Log in as a global admin or in-scope track admin.
2. Create a test task.
3. Delete it from the task row action.
4. Confirm the dialog.
5. In Network, verify `DELETE /api/v1/admin/task/{taskId}/`.

Expected:

- The task disappears from the admin task table.
- Refreshing `/task` does not show it in the active table.
- The task does not appear in the user frontend active task list.

Recovery contract:

```text
GET  /api/v1/tasks/?deleted=true
POST /api/v1/tasks/{taskId}/restore/
```

Expected restore behavior:

- Parent task dependencies are enforced.
- If a parent task is deleted, restoring a child first should return `400`.
- After restoring the parent and then the child, both should return to active
  task lists.
- Users can restore their own individual tasks.
- Group tasks can only be created, deleted, and restored by mentors and admins.

Known limitation: admin web currently exposes task delete, but not a dedicated
task recovery table.

## Admin Web: Groups And Group Children

Surfaces:

```text
http://localhost:3000/group
http://localhost:5173/groups/{groupId}
```

Group recovery contract:

```text
GET  /api/v1/groups/groups/?include_deleted=true
POST /api/v1/groups/groups/{groupId}/restore/
```

Group child recovery contracts:

```text
GET  /api/v1/chat/groups/{groupId}/messages/deleted/
POST /api/v1/chat/groups/{groupId}/messages/{messageId}/restore/
GET  /api/v1/tasks/?deleted=true&group_id={groupId}
POST /api/v1/tasks/{taskId}/restore/
```

Expected dependency behavior:

- If a group is deleted, deleted child rows such as messages or tasks should
  not be restorable until the group is restored.
- Track admins should only see deleted groups in their assigned tracks.
- Global admins should see all deleted groups.

Current UI note: admin web exposes group member and group-message removal
flows, but the dedicated deleted group recovery table is not currently present.

## Permissions Matrix

Global admin:

- Can delete and restore in all tracks.
- Should see all recovery-list rows.

Track admin:

- Can delete and restore only within assigned tracks.
- Should not see deleted rows from other tracks.
- Out-of-scope recovery requests should return `403` or `404`.

Mentor, supervisor, and basic user:

- Should not see admin recovery tables.
- Should not be able to restore admin-managed resources, events, groups, or
  deleted chat messages.
- Basic users can restore their own individual tasks.
- Mentors can create, delete, and restore group tasks in groups they mentor.
- Supervisors cannot create, delete, or restore group tasks.

## Regression Checklist

Run this after any soft-delete frontend or API change:

1. Delete one resource from admin web.
2. Delete one event from admin web.
3. Delete one task from admin web or user frontend.
4. Delete one chat message from user frontend.
5. Confirm each deleted row is gone after page refresh.
6. Confirm normal active list requests do not include deleted rows.
7. Confirm recovery-list requests include deleted rows with non-null
   `deleted_at`.
8. Restore each row through the recovery contract or recovery UI if available.
9. Refresh all relevant frontend pages.
10. Confirm restored rows reappear and do not show deleted styling.
11. Repeat one restore request and confirm idempotent `200` behavior.
12. Repeat with a track admin and verify scope restrictions.

## Common Failure Signs

- Deleted rows return to active lists after refresh.
- Generic edit forms send `deleted_at`.
- Restore uses `PATCH` instead of `POST .../restore/`.
- Deleted rows appear in dashboard counts or normal search results.
- Track admins can see deleted rows from other tracks.
- Child rows restore while their parent group is still deleted.
- UI says "permanently deleted" for a soft-delete action.
- Browser console shows CORS or CSRF failures during delete or restore.

## Evidence To Record

For a test run, record:

- Account used.
- Page URL.
- Entity type and row name.
- Delete request method, URL, status, and response.
- Recovery-list request URL and response row showing `deleted_at`.
- Restore request method, URL, status, and response.
- Final page refresh result.
