# Soft Delete Recovery Integration

This is the backend contract for frontend/admin recovery UI work.

## Core Contract

- Deletes are soft deletes: backend sets `deleted_at`.
- Recovery is a dedicated `POST .../restore/` mutation that clears `deleted_at`.
- Do not clear or send `deleted_at` through generic create/update/PATCH forms. Serializers treat it as read-only.
- Normal list/detail/search/dashboard/chat flows remain active-only.
- Recovery lists opt in with `deleted=true` or, for group APIs, `include_deleted=true`.
- Restore is idempotent: restoring an already-active record returns `200` with the active object.
- Group-bound children cannot be restored while their parent group is deleted.
- Chat message restore is admin/moderator recovery only. Original senders cannot undelete their own messages.
- Resource recovery is for admin-managed resource catalogue rows only. User file uploads in group messaging use `POST /api/v1/chat/groups/{groupId}/messages/upload/` and are represented as chat message attachments, not `Resources` rows.
- Admin access is based on `AdminScope`: global admins use `AdminScope(is_global=True)`, track admins use `AdminScope(track=...)`.

## App API Endpoints

These are the non-admin app routes available to authenticated/scoped clients.

| Entity | Recovery List | Restore |
| --- | --- | --- |
| Groups | `GET /api/v1/groups/groups/?include_deleted=true` operational admin only; track admins see only groups in their tracks | `POST /api/v1/groups/groups/{groupId}/restore/` |
| Chat messages | `GET /api/v1/chat/groups/{groupId}/messages/deleted/` admin only | `POST /api/v1/chat/groups/{groupId}/messages/{messageId}/restore/` admin only |
| Tasks | `GET /api/v1/tasks/?deleted=true` | `POST /api/v1/tasks/{taskId}/restore/` |
| Resources | `GET /api/v1/resources/resource-files/?deleted=true` admin only | `POST /api/v1/resources/resource-files/{resourceId}/restore/` admin only |
| Events | `GET /api/v1/events/?deleted=true&when=all` | `POST /api/v1/events/{eventId}/restore/` |

Events now resolve canonically through `/api/v1/events/...`. Legacy `/events/v1/...` and `/events/...` routes are still available for older clients, but new frontend/admin work should use `/api/v1/events/...`.

## Response Handling

Restore success:

- HTTP `200`.
- Returned object has `deleted_at: null`.
- Chat message restore also returns `is_deleted: false`.
- Chat message restore requires operational admin scope for the message group's track.
- Admin event restore preserves existing RSVP rows.

Recovery list rows:

- Deleted rows include a non-null `deleted_at`.
- Use `deleted_at` for "deleted on" display and for confirming restore state.

Expected blockers:

- `400`: active name conflict on group/resource restore.
- `400`: resource/message/task restore blocked because parent group is deleted.
- `400`: task restore blocked because parent task is deleted.
- `400`: event restore blocked because it targets a deleted group.
- `403`: caller lacks admin/scope permission.
- `404`: row does not exist or is not visible in the caller scope.

## UI Integration Notes

- Add recovery tabs/tables per entity rather than mixing deleted rows into normal views.
- On successful restore, remove the item from the recovery table and refetch the active list if it is visible.
- Surface backend blocker messages directly where possible; they describe the dependency the admin must restore first.
- Do not offer restore for child rows when the UI already knows the parent group is deleted.
- For chat, only expose restore controls in admin/moderation UI. Handle websocket `message.restored` the same way as `message.edited`: replace the local message payload and clear deleted styling.
- Keep delete confirmation copy distinct from hard delete. The backend preserves recoverable records and related data unless a model already has unrelated hard-delete behavior.
