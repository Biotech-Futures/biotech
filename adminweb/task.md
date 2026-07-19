# 🧑‍💼 Admin Features

## Admin API Endpoints

Source: `backend/apps/admin/urls.py` and `backend/apps/admin/views.py`.
Base URL for this frontend: `/api/v1/admin`.

### Auth

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/auth/password-status/` | Check whether the signed-in admin has a usable password. |
| POST | `/auth/set-password/` | Set first-time admin password. Body: `password`. |

### Users

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/user/` | List users. Query: `page`, `limit`, `search`, `role`, `track`, `active`, `inGroup`, `sortBy`, `sortOrder`. |
| POST | `/user/` | Create a user. |
| GET | `/user/tracks/` | List tracks available to the requesting admin. |
| POST | `/user/bulk/` | Bulk-create users from `users` array or raw JSON array. |
| POST | `/user/bulk-csv/` | Bulk-create users from CSV text. Body: `csv`. |
| GET | `/user/ungrouped-check/` | Check whether any students are not in groups. |
| GET | `/user/:userId/` | Get a user by ID. |
| PUT | `/user/:userId/` | Update a user. |
| DELETE | `/user/:userId/` | Delete a user. |
| PATCH | `/user/:userId/status/` | Update active status. Body: `isActive`. |

### Groups

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/group/` | List groups. Query: `page`, `limit`, `searchName`, `searchGroup`, `track`, `mentorStatus`. |
| GET | `/group/:groupId/` | Get a group by ID. |
| PUT | `/group/:groupId/` | Update group `name` and `track`. |
| GET | `/group/:groupId/messages/` | List group messages. Query: `page`, `limit`. |
| DELETE | `/group/:groupId/messages/:messageId/` | Delete a group message. |
| DELETE | `/group/:groupId/members/:userId/` | Remove a user from a group. |

### Student Matching

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/match/student/` | Generate student group recommendations for the authenticated admin context. |
| GET | `/match/individual/` | List individual/unmatched students. |
| POST | `/match/confirm/` | Confirm student assignments. |

### Mentor Matching

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/mentor-match/recommend/` | Get mentor recommendations. Query: `mode=strict\|coverage\|balanced`. |
| GET | `/mentor-match/mentors/` | List mentors for matching. |
| GET | `/mentor-match/groups/` | List unmatched groups. |
| GET | `/mentor-match/matched-groups/` | List groups with mentors. |
| POST | `/mentor-match/confirm/` | Confirm mentor assignments. |
| POST | `/mentor-match/replace/` | Replace a mentor assignment. |
| POST | `/mentor-match/unassign/` | Unassign mentors. Body: `groupIds`. |

### Mentors

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/mentor/` | List mentors. |
| PATCH | `/mentor/:mentorId/active/` | Update mentor active status. Body: `isActive`. |

### Events

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/event/` | List events. Query: `page`, `limit`, `hostUserId`, `upcoming`. |
| POST | `/event/` | Create an event. |
| GET | `/event/:eventId/` | Get an event by ID. |
| PUT | `/event/:eventId/` | Update an event. |
| DELETE | `/event/:eventId/` | Delete an event. |
| GET | `/event/:eventId/rsvp/` | List event RSVPs. |
| POST | `/event/:eventId/rsvp/` | Create an event RSVP. |
| GET | `/event/:eventId/targets/` | Get event target groups, roles, and tracks. |
| GET | `/event/meta/groups/` | List groups for event targeting. |
| GET | `/event/meta/roles/` | List roles for event targeting. |
| GET | `/event/meta/tracks/` | List tracks for event targeting. |
| PUT | `/event/rsvp/:rsvpId/` | Update an RSVP. |

### Resources

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/resource/` | List resources. Query: `page`, `limit`, `uploaderUserId`, `groupId`, `resourceKind`, `resourceTypeId`, `resourceType`, `trackId`, `search`, `order`, `uploader`, `roleSlug`. |
| POST | `/resource/` | Create a resource record. |
| GET | `/resource/:resourceId/` | Get a resource by ID. |
| PUT | `/resource/:resourceId/` | Update a resource. |
| PATCH | `/resource/:resourceId/` | Partially update a resource. |
| DELETE | `/resource/:resourceId/` | Delete a resource. |
| GET | `/resource/:resourceId/access/` | Stream resource content inline. |
| GET | `/resource/:resourceId/download/` | Download resource file. |
| POST | `/resource/:resourceId/upload/` | Replace a resource file. |
| POST | `/resource/:resourceId/assign-role/` | Assign a role to a resource. Body: `roleId`. |
| DELETE | `/resource/:resourceId/remove-role/` | Remove a role from a resource. Body: `roleId`. |
| POST | `/resource/upload/` | Upload a new resource file. |
| GET | `/resource/roles/` | List resource roles. |
| GET | `/resource/types/` | List resource types. |
| GET | `/resource/tracks/` | List resource tracks. |

### Announcements

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/announcement/` | List announcements. Query: `page`, `limit`, `search`, `archived`. |
| POST | `/announcement/` | Create an announcement. |
| GET | `/announcement/:announcementId/` | Get an announcement by ID. |
| PUT | `/announcement/:announcementId/` | Update an announcement. |
| POST | `/announcement/:announcementId/archive/` | Archive an announcement. |
| POST | `/announcement/:announcementId/notify/` | Send announcement email notifications. |
| GET | `/announcement/tracks/` | List announcement tracks. |
| GET | `/announcement/roles/` | List announcement roles. |

### Tasks

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/task/` | List admin tasks. Query: `page`, `limit`, `task_type`. |
| POST | `/task/` | Create an admin task. |
| GET | `/task/:taskId/` | Get an admin task by ID. |
| PATCH | `/task/:taskId/` | Update an admin task. |
| DELETE | `/task/:taskId/` | Delete an admin task. |
| POST | `/task/:taskId/toggle/` | Toggle task completion. Body: `completed`. |

## User Management

- [ ] Add users manually (form)
- [ ] Bulk upload users (CSV)
- [ ] Assign roles (Student / Mentor / Supervisor / Admin)
- [ ] Assign track (region)
- [ ] Activate / deactivate accounts

## Matching System (Core Feature)

### 👥 Student Matching

- [x] Auto-group students (2–5 per group)
- [x] Match based on interests
- [x] Match based on background
- [x] Match based on region (Track)
- [x] Match based on year level
- [x] Generate suggested groups
- [x] Calculate matching score
- [x] Provide summary statistics

### Mentor Matching

- [x] Assign mentors to groups
- [x] Display matching scores
- [x] Allow manual adjustment before confirmation

### Advanced Matching Controls

- [x] Replace mentor (single group)
- [x] Bulk replace inactive mentors
- [x] Detect inactive mentors (e.g., no messages)

---

## 🧠 Group Management & Oversight

- [x] View all groups and members
- [ ] Reassign users (single)
- [ ] Reassign users (bulk)
- [ ] Enter any group chat
- [ ] Edit messages
- [ ] Delete messages
- [ ] Post as admin identity
- [ ] Post as personal account

---

## 📚 Resource Management

- [ ] Create resources
- [ ] Edit resources
- [ ] Upload files (PDF, slides, etc.)
- [ ] Set role-based visibility
- [ ] Set track-based visibility
- [ ] Set global visibility
- [ ] Manage access permissions

---

## 📅 Event Management

- [ ] Create events
- [ ] Edit events
- [ ] Set event type (online / in-person)
- [ ] Set track visibility
- [ ] View RSVP lists
- [ ] Manage event lifecycle

---

## 📢 Announcements System

- [ ] Create announcements (rich text / HTML)
- [ ] Send email notifications
- [ ] Edit announcements after publishing
- [ ] Store announcements in platform

---

## 📧 Communication Tools

- [ ] Send email to individual users
- [ ] Send email to filtered groups
- [ ] Trigger automated emails (reassignment, system actions)
