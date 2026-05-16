# Admin Web

Standalone React admin UI built with Vite, TanStack Router, TanStack Query, shadcn/ui, and Tailwind CSS.

## Getting Started

```bash
pnpm install
pnpm dev
```

The local dev server runs on http://localhost:3000.

Use pnpm for this package. Keep `pnpm-lock.yaml` as the dependency lockfile and do not regenerate `adminweb/package-lock.json`.

## Environment

Create `.env` in this directory when you need to point the app at a local API.

```env
VITE_PUBLIC_API_URL=http://localhost:8000
```

Admin requests use `src/lib/myFetch.ts`, which builds URLs under:

```text
${VITE_PUBLIC_API_URL}/api/v1/admin
```

## Admin API

Endpoint source of truth: `../backend/apps/admin/urls.py` and `../backend/apps/admin/views.py`.

### Auth

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/auth/password-status/` | Check whether the signed-in admin has a usable password. |
| POST | `/auth/set-password/` | Set first-time admin password. Body: `password`. |

### Users

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/user/` | Query: `page`, `limit`, `search`, `role`, `track`, `active`, `inGroup`, `sortBy`, `sortOrder`. |
| POST | `/user/` | Create a user. |
| GET | `/user/tracks/` | List available tracks. |
| POST | `/user/bulk/` | Bulk-create users from `users` or a raw array. |
| POST | `/user/bulk-csv/` | Bulk-create users from CSV text. Body: `csv`. |
| GET | `/user/ungrouped-check/` | Check whether any students are ungrouped. |
| GET | `/user/:userId/` | Get a user. |
| PUT | `/user/:userId/` | Update a user. |
| DELETE | `/user/:userId/` | Delete a user. |
| PATCH | `/user/:userId/status/` | Body: `isActive`. |

### Groups

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/group/` | Query: `page`, `limit`, `searchName`, `searchGroup`, `track`, `mentorStatus`. |
| GET | `/group/:groupId/` | Get a group. |
| PUT | `/group/:groupId/` | Update `name` and `track`. |
| GET | `/group/:groupId/messages/` | Query: `page`, `limit`. |
| DELETE | `/group/:groupId/messages/:messageId/` | Delete a group message. |
| DELETE | `/group/:groupId/members/:userId/` | Remove a member from a group. |

### Matching

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/match/student/` | Generate student group recommendations. |
| GET | `/match/individual/` | List individual/unmatched students. |
| POST | `/match/confirm/` | Confirm student assignments. |
| GET | `/mentor-match/recommend/` | Query: `mode=strict\|coverage\|balanced`. |
| GET | `/mentor-match/mentors/` | List mentors for matching. |
| GET | `/mentor-match/groups/` | List unmatched groups. |
| GET | `/mentor-match/matched-groups/` | List matched groups. |
| POST | `/mentor-match/confirm/` | Confirm mentor assignments. |
| POST | `/mentor-match/replace/` | Replace one mentor assignment. |
| POST | `/mentor-match/bulk-replace-inactive/` | Replace inactive mentor assignments. |
| POST | `/mentor-match/unassign/` | Body: `groupIds`. |

### Mentors

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/mentor/` | List mentors. |
| PATCH | `/mentor/:mentorId/active/` | Body: `isActive`. |

### Events

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/event/` | Query: `page`, `limit`, `hostUserId`, `upcoming`. |
| POST | `/event/` | Create an event. |
| GET | `/event/:eventId/` | Get an event. |
| PUT | `/event/:eventId/` | Update an event. |
| DELETE | `/event/:eventId/` | Delete an event. |
| GET | `/event/:eventId/rsvp/` | List RSVPs. |
| POST | `/event/:eventId/rsvp/` | Create an RSVP. |
| GET | `/event/:eventId/targets/` | Get event targets. |
| GET | `/event/meta/groups/` | List target groups. |
| GET | `/event/meta/roles/` | List target roles. |
| GET | `/event/meta/tracks/` | List target tracks. |
| PUT | `/event/rsvp/:rsvpId/` | Update an RSVP. |

### Resources

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/resource/` | Query: `page`, `limit`, `uploaderUserId`, `groupId`, `resourceKind`, `resourceTypeId`, `resourceType`, `trackId`, `search`, `order`, `uploader`, `roleSlug`. |
| POST | `/resource/` | Create a resource record. |
| GET | `/resource/:resourceId/` | Get a resource. |
| PUT | `/resource/:resourceId/` | Update a resource. |
| PATCH | `/resource/:resourceId/` | Partially update a resource. |
| DELETE | `/resource/:resourceId/` | Delete a resource. |
| GET | `/resource/:resourceId/access/` | Stream resource inline. |
| GET | `/resource/:resourceId/download/` | Download resource file. |
| POST | `/resource/:resourceId/upload/` | Replace resource file. |
| POST | `/resource/:resourceId/assign-role/` | Body: `roleId`. |
| DELETE | `/resource/:resourceId/remove-role/` | Body: `roleId`. |
| POST | `/resource/upload/` | Upload a new resource file. |
| GET | `/resource/roles/` | List resource roles. |
| GET | `/resource/types/` | List resource types. |
| GET | `/resource/tracks/` | List resource tracks. |

### Announcements

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/announcement/` | Query: `page`, `limit`, `search`, `archived`. |
| POST | `/announcement/` | Create an announcement. |
| GET | `/announcement/:announcementId/` | Get an announcement. |
| PUT | `/announcement/:announcementId/` | Update an announcement. |
| POST | `/announcement/:announcementId/archive/` | Archive an announcement. |
| POST | `/announcement/:announcementId/notify/` | Send email notifications. |
| GET | `/announcement/tracks/` | List announcement tracks. |
| GET | `/announcement/roles/` | List announcement roles. |

### Tasks

| Method | Path | Notes |
| --- | --- | --- |
| GET | `/task/` | Query: `page`, `limit`, `task_type`. |
| POST | `/task/` | Create a task. |
| GET | `/task/:taskId/` | Get a task. |
| PATCH | `/task/:taskId/` | Update a task. |
| DELETE | `/task/:taskId/` | Delete a task. |
| POST | `/task/:taskId/toggle/` | Body: `completed`. |

## Commands

```bash
pnpm dev
pnpm build
pnpm typecheck
pnpm test
pnpm preview
```

## Source Layout

```text
src/
├── components/
├── fetch/
├── hooks/
├── lib/
├── provider/
├── query/
├── routes/
├── schema/
├── type/
└── util/
```
