# BIOTech Futures Portal - API Requirements for Backend Alignment

Date: 2026-03-22  
Prepared for: Frontend-Backend integration planning  
Scope: API contract proposal based on current frontend implementation and project requirements.

## 1. Purpose

This document defines the API endpoints needed to fully support the mentoring portal, including:
- Endpoint name and method
- Purpose
- Input (path/query/body)
- Output (response shape)
- Current status from frontend perspective

It is intended as a practical checklist for backend discussions and gap closure.

## 2. API Conventions (Recommended)

- Base URL: `https://<host>/api/v1` (except auth service routes if separated)
- Authentication: secure session cookie and/or JWT (must be consistent)
- CSRF: required for non-GET when using session auth
- Pagination format:
  - Input: `page`, `page_size`
  - Output: `{ count, next, previous, results: [] }`
- Standard error format:
  - `{ code: "string_code", message: "Human-readable message", details?: object }`
- Date/time format: ISO-8601 (`2026-03-22T10:30:00Z`)

## 3. Status Legend

- `Integrated`: frontend already calls this API.
- `UI-ready but Missing API`: UI exists, backend/API integration is missing.
- `Requirement-only`: required by project scope, UI may be partial or not built.

## 4. API Inventory by Domain

## 4.1 Authentication and Session

### 4.1.1 Send Login Code
- API Name: `send_login_code`
- Method/Path: `POST /services/send-login-code/`
- Purpose: Send single-use login code to user email.
- Input Body:
```json
{
  "email": "user@example.com",
  "redirect_url": "http://localhost:5173/#/auth/callback"
}
```
- Output (200):
```json
{
  "message": "Verification code sent",
  "expires_in_seconds": 600,
  "resend_after_seconds": 60
}
```
- Status: `Integrated`

### 4.1.2 Verify Login Code
- API Name: `verify_login_code`
- Method/Path: `POST /services/verify-login-code/`
- Purpose: Verify one-time code and establish authenticated session (and/or return tokens).
- Input Body:
```json
{
  "email": "user@example.com",
  "code": "123456"
}
```
- Output (200, option A - session):
```json
{
  "message": "Login successful",
  "user": {
    "id": 10,
    "email": "user@example.com"
  }
}
```
- Output (200, option B - token):
```json
{
  "access_token": "jwt_access",
  "refresh_token": "jwt_refresh",
  "user": {
    "id": 10,
    "email": "user@example.com"
  }
}
```
- Status: `Integrated`

### 4.1.3 Current User Profile (Auth Context)
- API Name: `get_current_user`
- Method/Path: `GET /users/me/` (or `GET /api/v1/users/me/`)
- Purpose: Return authenticated user profile and role context.
- Input: none
- Output (200):
```json
{
  "id": 10,
  "email": "user@example.com",
  "first_name": "Ana",
  "last_name": "Lee",
  "current_role_id": 3,
  "current_role_name": "mentor",
  "is_staff": false,
  "is_superuser": false,
  "track": "AUS-NSW"
}
```
- Status: `Integrated`

### 4.1.4 Logout
- API Name: `logout`
- Method/Path: `POST /auth/logout/`
- Purpose: Invalidate session/token on server.
- Input Body: `{}` (or refresh token if token-based)
- Output (200): `{ "message": "Logged out" }`
- Status: `UI-ready but Missing API` (frontend currently clears local state only)

### 4.1.5 Refresh Token (if JWT mode)
- API Name: `refresh_token`
- Method/Path: `POST /auth/token/refresh/`
- Purpose: Rotate access token without forcing re-login.
- Input Body:
```json
{ "refresh_token": "jwt_refresh" }
```
- Output (200):
```json
{ "access_token": "new_jwt_access" }
```
- Status: `Requirement-only`

## 4.2 Roles, Permissions, and Tracks

### 4.2.1 List Roles
- API Name: `list_roles`
- Method/Path: `GET /roles/`
- Purpose: Return role catalog for UI rendering and admin assignment.
- Input Query: optional `active=true`
- Output:
```json
{
  "results": [
    { "id": 1, "role_name": "student" },
    { "id": 2, "role_name": "mentor" },
    { "id": 3, "role_name": "supervisor" },
    { "id": 4, "role_name": "local_admin" },
    { "id": 5, "role_name": "global_admin" }
  ]
}
```
- Status: `Requirement-only`

### 4.2.2 Current User Permissions
- API Name: `get_my_permissions`
- Method/Path: `GET /permissions/me/`
- Purpose: Return action-level permissions for frontend gating.
- Input: none
- Output:
```json
{
  "permissions": [
    "group.read",
    "group.chat.post",
    "resource.read",
    "event.register"
  ]
}
```
- Status: `Requirement-only`

### 4.2.3 Track Catalog
- API Name: `list_tracks`
- Method/Path: `GET /tracks/`
- Purpose: Return available regional tracks.
- Input Query: optional `active=true`
- Output:
```json
{
  "results": [
    { "id": 1, "code": "AUS-NSW", "name": "Australia - NSW" },
    { "id": 2, "code": "Brazil", "name": "Brazil" },
    { "id": 3, "code": "Global", "name": "Global" }
  ]
}
```
- Status: `UI-ready but Missing API`

## 4.3 Users and Profiles

### 4.3.1 Update Current User Profile
- API Name: `update_my_profile`
- Method/Path: `PATCH /users/me/`
- Purpose: Save profile fields from Profile page.
- Input Body:
```json
{
  "first_name": "Ana",
  "last_name": "Lee",
  "location": "Sydney",
  "interests": ["Biotech", "Mentoring"],
  "contact_method": "both",
  "availability": "Weeknights"
}
```
- Output:
```json
{
  "id": 10,
  "first_name": "Ana",
  "last_name": "Lee",
  "location": "Sydney",
  "interests": ["Biotech", "Mentoring"],
  "contact_method": "both",
  "availability": "Weeknights"
}
```
- Status: `UI-ready but Missing API`

### 4.3.2 Admin User List
- API Name: `list_users`
- Method/Path: `GET /users/`
- Purpose: Power admin table (search/filter).
- Input Query:
  - `search`
  - `role`
  - `track`
  - `status`
  - `page`, `page_size`
- Output:
```json
{
  "count": 125,
  "results": [
    {
      "id": 20,
      "name": "Anita Pickard",
      "email": "anita@example.com",
      "role": "mentor",
      "track": "AUS-NSW",
      "status": "active"
    }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.3.3 Admin User Create / Update
- API Name: `create_user`, `update_user`
- Method/Path:
  - `POST /users/`
  - `PATCH /users/{user_id}/`
- Purpose: Support admin add/edit user workflows.
- Input Body (create example):
```json
{
  "email": "new@example.com",
  "first_name": "New",
  "last_name": "User",
  "role": "student",
  "track": "AUS-NSW"
}
```
- Output: created/updated user object
- Status: `UI-ready but Missing API`

## 4.4 Groups and Membership

### 4.4.1 List Groups
- API Name: `list_groups`
- Method/Path: `GET /groups/`
- Purpose: Group list and dashboard summaries.
- Input Query:
  - `track`
  - `mentor_id`
  - `student_id`
  - `status`
  - `search`
  - `page`, `page_size`
- Output:
```json
{
  "count": 42,
  "results": [
    {
      "id": "BTF046",
      "name": "BTF046",
      "status": "active",
      "track": "AUS-NSW",
      "mentor": { "id": 2, "name": "Anita Pickard" },
      "member_count": 4
    }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.4.2 Group Detail
- API Name: `get_group_detail`
- Method/Path: `GET /groups/{group_id}/`
- Purpose: Populate group detail page.
- Input Path: `group_id`
- Output:
```json
{
  "id": "BTF046",
  "name": "BTF046",
  "track": "AUS-NSW",
  "status": "active",
  "created_at": "2025-08-04",
  "mentor": { "id": 2, "name": "Anita Pickard" },
  "members": [
    { "id": 12, "name": "Student A", "role": "student" }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.4.3 Create/Update Group
- API Name: `create_group`, `update_group`
- Method/Path:
  - `POST /groups/`
  - `PATCH /groups/{group_id}/`
- Purpose: Admin group management.
- Input Body (create example):
```json
{
  "name": "BTF120",
  "track": "AUS-NSW",
  "mentor_id": 2,
  "member_ids": [12, 13, 14]
}
```
- Output: group object
- Status: `Requirement-only`

### 4.4.4 Bulk Group Formation
- API Name: `bulk_create_groups`
- Method/Path: `POST /groups/bulk-create/`
- Purpose: Support administrative bulk formation workflow.
- Input Body:
```json
{
  "track": "AUS-NSW",
  "group_size": 4,
  "student_ids": [12, 13, 14, 15, 16, 17],
  "mentor_ids": [2, 3]
}
```
- Output:
```json
{
  "created_groups": [
    { "id": "BTF201", "member_ids": [12, 13, 14, 15], "mentor_id": 2 }
  ]
}
```
- Status: `Requirement-only`

## 4.5 Connection Plan and Progress Tracking

### 4.5.1 Get Group Plan
- API Name: `get_group_plan`
- Method/Path: `GET /groups/{group_id}/plan/`
- Purpose: Load milestones/tasks in group plan panel.
- Input: `group_id`
- Output:
```json
{
  "group_id": "BTF046",
  "milestones": [
    {
      "id": 1,
      "title": "Getting Started",
      "tasks": [
        {
          "id": 11,
          "title": "Determine Group Topic",
          "completed": false,
          "assigned_to": 12,
          "due_date": "2026-04-01"
        }
      ]
    }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.5.2 Add Milestone / Task
- API Name: `create_milestone`, `create_task`
- Method/Path:
  - `POST /groups/{group_id}/milestones/`
  - `POST /groups/{group_id}/tasks/`
- Purpose: Support "Add Milestone" and "Add Task" buttons.
- Input Body (task example):
```json
{
  "milestone_id": 1,
  "title": "Meeting 1: Initialisation",
  "assigned_to": 12,
  "due_date": "2026-04-05"
}
```
- Output: created milestone/task object
- Status: `UI-ready but Missing API`

### 4.5.3 Update Task Completion
- API Name: `update_task_status`
- Method/Path: `PATCH /groups/{group_id}/tasks/{task_id}/`
- Purpose: Persist task completion toggle.
- Input Body:
```json
{
  "completed": true
}
```
- Output: updated task object
- Status: `UI-ready but Missing API`

### 4.5.4 Assign Plan Template to Group
- API Name: `assign_plan_template`
- Method/Path: `POST /groups/{group_id}/plan/assign-template/`
- Purpose: Requirement states groups can be assigned a connection plan.
- Input Body:
```json
{
  "template_id": 3
}
```
- Output:
```json
{
  "group_id": "BTF046",
  "template_id": 3,
  "assigned_at": "2026-03-22T09:00:00Z"
}
```
- Status: `Requirement-only`

## 4.6 Group Chat and File Sharing

### 4.6.1 List Group Messages
- API Name: `list_group_messages`
- Method/Path: `GET /groups/{group_id}/messages/`
- Purpose: Load discussion history.
- Input Query: `before`, `after`, `limit`
- Output:
```json
{
  "results": [
    {
      "id": 901,
      "group_id": "BTF046",
      "author": { "id": 2, "name": "Anita Pickard" },
      "text": "Hi team!",
      "created_at": "2026-03-22T08:10:00Z",
      "attachments": []
    }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.6.2 Send Group Message
- API Name: `create_group_message`
- Method/Path: `POST /groups/{group_id}/messages/`
- Purpose: Persist new text message.
- Input Body:
```json
{
  "text": "Hello everyone"
}
```
- Output: created message object
- Status: `UI-ready but Missing API`

### 4.6.3 Upload Chat Attachment
- API Name: `upload_group_attachment`
- Method/Path: `POST /groups/{group_id}/attachments/`
- Purpose: File upload from discussion panel.
- Input: `multipart/form-data` (`file`, optional `message_id`)
- Output:
```json
{
  "id": 501,
  "filename": "agenda.pdf",
  "size_bytes": 123456,
  "mime_type": "application/pdf",
  "download_url": "/api/v1/groups/BTF046/attachments/501/download/"
}
```
- Status: `UI-ready but Missing API`

### 4.6.4 Download Attachment
- API Name: `download_group_attachment`
- Method/Path: `GET /groups/{group_id}/attachments/{attachment_id}/download/`
- Purpose: Download shared files.
- Input: path params
- Output: binary stream
- Status: `Requirement-only`

### 4.6.5 Real-time Messaging Channel
- API Name: `group_chat_ws`
- Protocol/Path: `WS /ws/groups/{group_id}/chat/`
- Purpose: Real-time chat updates.
- Input Event:
```json
{ "type": "message.create", "text": "Hello" }
```
- Output Event:
```json
{
  "type": "message.created",
  "payload": {
    "id": 902,
    "group_id": "BTF046",
    "text": "Hello",
    "author": { "id": 12, "name": "Student A" },
    "created_at": "2026-03-22T08:11:00Z"
  }
}
```
- Status: `Requirement-only`

## 4.7 Resource Library

### 4.7.1 List Resource Files
- API Name: `list_resource_files`
- Method/Path: `GET /resources/resource-files/`
- Purpose: Resource library list with filters.
- Input Query:
  - `search`
  - `role`
  - `uploader_id`
  - `order`
  - `page`, `page_size`
- Output:
```json
{
  "count": 27,
  "results": [
    {
      "id": 1001,
      "resource_name": "Mentor Handbook",
      "resource_description": "Guide for mentors",
      "resource_type_detail": { "id": 2, "type_name": "guide" },
      "upload_datetime": "2026-03-20T10:00:00Z",
      "uploader": { "id": 2, "first_name": "Anita", "last_name": "Pickard", "email": "anita@example.com" },
      "visible_roles": [{ "id": 2, "role_name": "mentor" }]
    }
  ]
}
```
- Status: `Integrated`

### 4.7.2 Resource CRUD
- API Name: `create_resource_file`, `get_resource_file`, `update_resource_file`, `delete_resource_file`
- Method/Path:
  - `POST /resources/resource-files/`
  - `GET /resources/resource-files/{id}/`
  - `PATCH /resources/resource-files/{id}/`
  - `DELETE /resources/resource-files/{id}/`
- Purpose: Full admin lifecycle management.
- Input Body (create example):
```json
{
  "resource_name": "New Guide",
  "resource_description": "Description",
  "resource_type_id": 2,
  "role_ids": [2, 3]
}
```
- Output: resource object
- Status: `API exists in frontend utility; UI wiring is partial`

### 4.7.3 Upload/Download Resource Binary
- API Name: `upload_resource_binary`, `download_resource_binary`
- Method/Path:
  - `POST /resources/resource-files/{id}/upload/`
  - `GET /resources/resource-files/{id}/download/`
- Purpose: Actual file content handling (not just metadata).
- Input: multipart upload / path param
- Output: file metadata / binary stream
- Status: `UI-ready but Missing API contract in frontend`

### 4.7.4 Resource Types
- API Name: `list_resource_types`
- Method/Path: `GET /resources/resource-types/`
- Purpose: Replace hardcoded type list in frontend.
- Output:
```json
{
  "results": [
    { "id": 1, "type_name": "document", "type_description": "Document resources" },
    { "id": 2, "type_name": "guide", "type_description": "Step-by-step guides" }
  ]
}
```
- Status: `UI-ready but Missing API` (frontend currently hardcodes)

### 4.7.5 Resource Version History
- API Name: `list_resource_versions`, `create_resource_version`
- Method/Path:
  - `GET /resources/resource-files/{id}/versions/`
  - `POST /resources/resource-files/{id}/versions/`
- Purpose: Requirement asks for simple version control.
- Input Body (create version example):
```json
{
  "change_note": "Updated rubric section",
  "file": "<multipart file>"
}
```
- Output:
```json
{
  "version_id": 4,
  "resource_id": 1001,
  "version_label": "v4",
  "created_at": "2026-03-22T06:00:00Z",
  "created_by": 2
}
```
- Status: `Requirement-only`

## 4.8 Events and Registrations

### 4.8.1 List Events
- API Name: `list_events`
- Method/Path: `GET /events/`
- Purpose: Populate events page.
- Input Query:
  - `from_date`, `to_date`
  - `track`
  - `type` (`virtual`, `in-person`)
  - `search`
- Output:
```json
{
  "results": [
    {
      "id": 2001,
      "title": "Program Kickoff",
      "description": "Kickoff session",
      "date": "2026-04-10",
      "time": "10:00",
      "timezone": "Australia/Sydney",
      "location": "Sydney University",
      "type": "in-person",
      "register_link": "https://humanitix.com/..."
    }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.8.2 Event CRUD (Admin)
- API Name: `create_event`, `update_event`, `delete_event`, `get_event`
- Method/Path:
  - `POST /events/`
  - `GET /events/{event_id}/`
  - `PATCH /events/{event_id}/`
  - `DELETE /events/{event_id}/`
- Purpose: Manage event lifecycle.
- Input Body (create example):
```json
{
  "title": "Mentor Training",
  "description": "Training session",
  "date": "2026-04-12",
  "time": "14:00",
  "timezone": "Australia/Sydney",
  "location": "Online",
  "type": "virtual",
  "register_link": "https://humanitix.com/..."
}
```
- Output: event object
- Status: `UI-ready but Missing API`

### 4.8.3 Event Registration
- API Name: `register_event`, `cancel_event_registration`, `list_event_registrations`
- Method/Path:
  - `POST /events/{event_id}/registrations/`
  - `DELETE /events/{event_id}/registrations/me/`
  - `GET /events/{event_id}/registrations/` (admin)
- Purpose: Native event registration.
- Input Body (register):
```json
{
  "notes": "Interested in biotech track"
}
```
- Output:
```json
{
  "registration_id": 3011,
  "event_id": 2001,
  "user_id": 10,
  "status": "registered"
}
```
- Status: `UI-ready but Missing API`

## 4.9 Announcements

### 4.9.1 List Announcements
- API Name: `list_announcements`
- Method/Path: `GET /announcements/`
- Purpose: Populate announcement page and dashboard previews.
- Input Query:
  - `audience`
  - `search`
  - `track`
  - `published=true`
- Output:
```json
{
  "results": [
    {
      "id": 4001,
      "title": "Welcome",
      "summary": "Kickoff details",
      "content": "Long text",
      "author": "Program Team",
      "audience": "all",
      "track": "Global",
      "published_at": "2026-03-21T08:00:00Z",
      "link": null
    }
  ]
}
```
- Status: `UI-ready but Missing API`

### 4.9.2 Announcement CRUD
- API Name: `create_announcement`, `update_announcement`, `delete_announcement`, `get_announcement`
- Method/Path:
  - `POST /announcements/`
  - `GET /announcements/{id}/`
  - `PATCH /announcements/{id}/`
  - `DELETE /announcements/{id}/`
- Purpose: Admin publish and manage updates.
- Input Body (create example):
```json
{
  "title": "Mentor Info Session Slides",
  "summary": "Slides now available",
  "content": "Full details",
  "audience": "mentor",
  "track": "Global",
  "link": "https://example.org/slides",
  "publish_at": "2026-03-23T09:00:00Z"
}
```
- Output: announcement object
- Status: `Requirement-only`

## 4.10 Notifications

### 4.10.1 List Notifications
- API Name: `list_notifications`
- Method/Path: `GET /notifications/`
- Purpose: Notification center and unread badge.
- Input Query: `unread_only`, `page`, `page_size`
- Output:
```json
{
  "unread_count": 3,
  "results": [
    {
      "id": 5001,
      "type": "event_reminder",
      "title": "Event tomorrow",
      "message": "Program Kickoff starts at 10:00",
      "is_read": false,
      "created_at": "2026-03-22T02:00:00Z",
      "action_url": "/events/2001"
    }
  ]
}
```
- Status: `Requirement-only`

### 4.10.2 Mark Notification(s) Read
- API Name: `mark_notification_read`, `mark_all_notifications_read`
- Method/Path:
  - `PATCH /notifications/{id}/read/`
  - `POST /notifications/mark-all-read/`
- Purpose: Update badge/read state.
- Input Body (single):
```json
{ "is_read": true }
```
- Output: `{ "success": true }`
- Status: `Requirement-only`

## 4.11 Mentor Matching and Reassignment

### 4.11.1 Run Matching
- API Name: `run_matching`
- Method/Path: `POST /matching/runs/`
- Purpose: Trigger allocation algorithm.
- Input Body:
```json
{
  "track": "AUS-NSW",
  "criteria": {
    "capacity_weight": 0.4,
    "interest_weight": 0.4,
    "timezone_weight": 0.2
  }
}
```
- Output:
```json
{
  "run_id": 9001,
  "status": "queued"
}
```
- Status: `Requirement-only`

### 4.11.2 Get Matching Recommendations
- API Name: `list_matching_recommendations`
- Method/Path: `GET /matching/recommendations/`
- Purpose: Display suggested assignments before confirmation.
- Input Query: `run_id`, `track`
- Output:
```json
{
  "results": [
    {
      "group_id": "BTF046",
      "mentor_id": 2,
      "score": 0.91,
      "reasoning": ["Interest match", "Capacity available"]
    }
  ]
}
```
- Status: `Requirement-only`

### 4.11.3 Confirm / Override Assignment
- API Name: `confirm_assignment`, `override_assignment`, `reassign_mentor`
- Method/Path:
  - `POST /matching/assignments/confirm/`
  - `POST /matching/assignments/override/`
  - `POST /groups/{group_id}/reassign-mentor/`
- Purpose: Admin final decision and manual override.
- Input Body (override example):
```json
{
  "group_id": "BTF046",
  "mentor_id": 7,
  "reason": "Language fit"
}
```
- Output:
```json
{
  "group_id": "BTF046",
  "old_mentor_id": 2,
  "new_mentor_id": 7,
  "updated_at": "2026-03-22T07:20:00Z"
}
```
- Status: `Requirement-only`

## 4.12 Admin Communications and Export

### 4.12.1 Create Bulk Communication Job
- API Name: `create_bulk_message_job`
- Method/Path: `POST /admin/communications/bulk-jobs/`
- Purpose: Send announcements/emails to selected user segments.
- Input Body:
```json
{
  "channel": "in_app_email",
  "filters": {
    "role": ["student"],
    "track": ["AUS-NSW"],
    "status": ["active"]
  },
  "subject": "Reminder",
  "message": "Please complete your milestone tasks."
}
```
- Output:
```json
{
  "job_id": 7001,
  "target_count": 320,
  "status": "queued"
}
```
- Status: `Requirement-only`

### 4.12.2 Export Users / Groups
- API Name: `export_users`, `export_groups`
- Method/Path:
  - `POST /admin/exports/users/`
  - `POST /admin/exports/groups/`
- Purpose: Admin export feature.
- Input Body:
```json
{
  "format": "csv",
  "filters": { "track": "AUS-NSW" }
}
```
- Output:
```json
{
  "export_id": 8101,
  "status": "ready",
  "download_url": "/api/v1/admin/exports/8101/download/"
}
```
- Status: `UI-ready but Missing API`

### 4.12.3 Import Users
- API Name: `import_users`
- Method/Path: `POST /admin/imports/users/`
- Purpose: Bulk onboard users from file.
- Input: multipart (`file`)
- Output:
```json
{
  "import_id": 8201,
  "created": 120,
  "updated": 15,
  "failed": 3,
  "errors": [
    { "row": 55, "message": "Invalid email" }
  ]
}
```
- Status: `Requirement-only`

## 4.13 Dashboard Aggregates

### 4.13.1 Dashboard Summary
- API Name: `get_dashboard_summary`
- Method/Path: `GET /dashboard/summary/`
- Purpose: Return role-specific summary counters and previews in one request.
- Input Query: `role`, optional `track`
- Output:
```json
{
  "role": "mentor",
  "counts": {
    "groups": 3,
    "events": 2,
    "resources": 15,
    "announcements": 4
  },
  "next_event": {
    "id": 2001,
    "title": "Program Kickoff",
    "date": "2026-04-10"
  },
  "group_preview": [
    { "id": "BTF046", "name": "BTF046", "member_count": 4 }
  ]
}
```
- Status: `UI-ready but Missing API`

## 5. Priority Gap List (for Backend Discussion)

## Priority 1 (blockers for current UI to stop using mock/demo)
- `GET /groups/`
- `GET /groups/{group_id}/`
- `GET /groups/{group_id}/plan/`
- `PATCH /groups/{group_id}/tasks/{task_id}/`
- `GET /groups/{group_id}/messages/`
- `POST /groups/{group_id}/messages/`
- `POST /groups/{group_id}/attachments/`
- `GET /events/`
- `POST /events/{event_id}/registrations/`
- `GET /announcements/`
- `GET /users/` (admin table)
- `PATCH /users/me/` (profile save)

## Priority 2 (admin operations and production readiness)
- Group create/update/bulk-create
- Announcement CRUD
- Event CRUD
- Bulk communication jobs
- Import/export jobs
- Notification APIs
- Resource binary upload/download and type endpoint

## Priority 3 (advanced requirement completion)
- Mentor matching run/recommend/override APIs
- Resource version history APIs
- WebSocket real-time chat
- Fine-grained permissions API

## 6. Minimal Common Response Schemas (Recommended)

### 6.1 User
```json
{
  "id": 10,
  "email": "user@example.com",
  "first_name": "Ana",
  "last_name": "Lee",
  "role": "mentor",
  "track": "AUS-NSW",
  "status": "active"
}
```

### 6.2 Group
```json
{
  "id": "BTF046",
  "name": "BTF046",
  "track": "AUS-NSW",
  "status": "active",
  "mentor": { "id": 2, "name": "Anita Pickard" },
  "member_count": 4
}
```

### 6.3 Event
```json
{
  "id": 2001,
  "title": "Program Kickoff",
  "date": "2026-04-10",
  "time": "10:00",
  "timezone": "Australia/Sydney",
  "location": "Sydney University",
  "type": "in-person",
  "register_link": null
}
```

### 6.4 Announcement
```json
{
  "id": 4001,
  "title": "Welcome",
  "summary": "Kickoff details",
  "audience": "all",
  "published_at": "2026-03-21T08:00:00Z"
}
```

