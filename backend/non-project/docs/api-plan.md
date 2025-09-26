# API Plan

We will have API endpoints ready for each core resource in the mentoring platform. Please use this as a guideline, these may change in development. Also this is definitely open for extension and modification, any suggestions are appreciated! Let us know in the slack Biotech Slack.

## Purpose & Scope

The purpose of this API Plan is to provide secure, documented APIs for auth, profiles, groups, chat, files, and integrations for WS1 and WS3 to build independently.

Out of scope includes UI, matching logic and content/curriculum resources. We will attempt to provide dummy data where needed.

## API Lifecycle + Governance

APIs will be versioned and follow a clear lifecycle from development to deprecation. Each API will have associated documentation, including usage examples and error handling guidelines. Governance will be established to manage changes to APIs, including a review process for new endpoints and modifications to existing ones.

Versioning follows semantic versioning principles (MAJOR.MINOR.PATCH). Breaking changes will increment the MAJOR version, while new features will increment the MINOR version. Patches will be used for bug fixes.

e.g.

```python
/auth/v1/validate/...
# breaking changes -> /auth/v2/validate/...
```

## Environments

We will attempt to provide separate environments for development, testing, and production. Each environment will have its own set of API keys and configurations to ensure security and stability.

Dev and Staging data will be synthetic and anonymized to protect user privacy. Endpoint URLs will follow a specific semantic:

```
Dev: https://dev.api/auth/v1/validate/...
Staging: https://staging.api/auth/v1/validate/...
Production: https://api/auth/v1/validate/...
```

## Documentation Artifacts

We will provide comprehensive documentation for each API endpoint, including:

- **OpenAPI Specifications**: Machine-readable API definitions.
- **Swagger UI**: Interactive API documentation.
- **Markdown Documentation**: Human-readable API documentation.

## API DOCS

### Auth & User Management

---

**POST `/auth/v1/login`**  
Purpose: Authenticate a user with email + one-time code and issue an access token.

**Request:**

```json
{
  "email": "student@example.edu",
  "code": "123456"
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJhbGciOi...",
  "refresh_token": "def502...",
  "user": {
    "id": "uuid",
    "email": "student@example.edu",
    "role": "student"
  }
}
```

**Errors:**

- `400 invalid_code`
- `429 too_many_attempts`

---

**POST `/auth/v1/register`**

**Purpose:** Create a new user.

**Request:**

```json
{
  "name": "Alice Example",
  "email": "alice@example.com",
  "role": "student"
}
```

**Response (200 OK)**

```json
{
  "id": "uuid",
  "name": "Alice Example",
  "email": "alice@example.com",
  "role": "student",
  "created_at": "2025-08-21T12:00:00Z"
}
```

**Errors:**

- `400 invalid_request`
- `401 unauthorized`
- `409 conflict` (e.g., email already exists)

---

**GET `/users/v1`**

**Purpose:** Retrieves a list of users from a given table. This can be filtered by track, group, role etc. If no filter parameters are provided the request will default to listing all users.

**Query Parameters**

- `role` (string) – filter by role
- `track` (string) – filter by track
- `group` (string) – filter by group
- `interest` (List[string]) - only interest variables permitted
- `offset` (integer) – for pagination

**Request**

- N/A

**Response (200 OK)**

```json
[
  {
    "id": "uuid1",
    "name": "Alice Example",
    "email": "alice@example.com",
    "role": "student"
  },
  {
    "id": "uuid2",
    "name": "Bob Example",
    "email": "bob@example.com",
    "role": "mentor"
  }
]
```

**Errors:**

- `401 unauthorized`

---

**POST** `/users/v1/{id}/activate`

**Purpose:** Activate a user account (admin only).  
**Path Parameters:**

- `id` (string | uuid) — ID of the user to activate

**Request Body:**

- None

**Response (200 OK):**

```json
{
  "id": "uuid",
  "status": "active"
}
```

**Errors:**

- `401 Unauthorized` — If the request is missing or has an invalid access token

- `403 Forbidden` — If the requester does not have admin permissions

- `404 Not Found` — If the specified user ID does not exist

---

**POST** `/users/{id}/v1/deactivate`

**Purpose:** Deactivate a user account (admin only).
**Path Parameters:**

- `id` (string | uuid) — ID of the user to activate

**Request Body:**

- None

**Response (200 OK):**

```json
{
  "id": "uuid",
  "status": "inactive"
}
```

**Errors:**

- `401 Unauthorized` — If the request is missing or has an invalid access token

- `403 Forbidden` — If the requester does not have admin permissions

- `404 Not Found` — If the specified user ID does not exist

---

### Tracks and Groups

**POST `/groups/v1`**  
**Purpose:** Create a new group (e.g., mentor + mentee cluster).

**Request:**

```json
{
  "name": "NSW Biotech Group 1",
  "track": "NSW",
  "members": ["user-uuid-1", "user-uuid-2"]
}
```

**Response (201 Created):**

```json
{
  "id": "group-uuid",
  "name": "NSW Biotech Group 1",
  "track": "NSW",
  "members_count": 2
}
```

**POST `/tracks/v1`**  
**Purpose:** Create a new track (admin only).

**Request:**

```json
{
  "name": "Track Name",
  "region": "NSW"
}
```

**Response (201 Created):**

```json
{
  "name": "Track Name",
  "region": "NSW"
}
```

---

**GET `groups/v1/{groupId}`**

**Purpose:** Retrieve a group by group ID, this will provide groups and their associated users ie. Supervisors, Mentors and Students.

**Path Parameters:**

- `groupId` (string | uuid) – ID of the group to retrieve

**Response (200 OK):**

```json
{
  "id": "uuid",
  "name": "Biotech Mentors Group",
  "track": "WS1",
  "created_at": "2025-08-21T12:00:00Z",
  "supervisors": [
    {
      "id": "uuid1",
      "name": "Dr. Smith",
      "email": "smith@example.edu"
    }
  ],
  "mentors": [
    {
      "id": "uuid2",
      "name": "Alice Mentor",
      "email": "alice@example.edu"
    }
  ],
  "students": [
    {
      "id": "uuid3",
      "name": "Bob Student",
      "email": "bob@example.edu"
    }
  ]
}
```

- **Errors:**
  - `401 unauthorized` – missing or invalid access token
  - `404 not_found` – group with groupId does not exist

---

**GET `/groups/v1/`**

**Purpose:** Retrieve a list of all groups. Supports optional filters for track or group name, and pagination.

**Query Parameters (optional):**

- `track` (string) – filter groups by mentoring track
- `offset` (integer) – pagination offset (default: 0)
- `limit` (integer) – number of results per page (default: 20)

**Response (200 OK):**

```json
[
  {
    "id": "uuid1",
    "name": "Biotech Mentors Group",
    "track": "WS1",
    "created_at": "2025-08-21T12:00:00Z",
    "supervisors_count": 2,
    "mentors_count": 5,
    "students_count": 20
  },
  {
    "id": "uuid2",
    "name": "AI Mentors Group",
    "track": "WS3",
    "created_at": "2025-08-22T09:30:00Z",
    "supervisors_count": 1,
    "mentors_count": 4,
    "students_count": 15
  }
]
```

---

**PUT** `/tracks/v1/{id}`  
**Purpose:** Update an existing track (admin only).  
**Path Parameters:**

- `id` (string | uuid) — ID of the track to update

**Request Body:**

```json
{
  "name": "Updated Track Name",
  "region": "WS1",
  "criteria": "Optional updated criteria"
}
```

**Response (200 OK)**:

```
{
  "id": "uuid",
  "name": "Updated Track Name",
  "region": "WS1",
  "criteria": "Optional updated criteria"
}
```

- **Errors:**

- `401 Unauthorized` — Missing or invalid access token
- `403 Forbidden` — User is not admin
- `404 Not Found` — Track ID does not exist

---

**PUT** `/groups/v1/{id}`

**Purpose:** Update an existing group (admin or mentor). Can be used to rename, close, or archive a group.

**Path Parameters**

- `id` (string | uuid) — ID of the group to update

**Request Body**

```json
{
  "name": "New Group Name",
  "status": "active" // Options: active, closed, archived
}
```

**Response**

```json
{
  "id": "uuid",
  "name": "New Group Name",
  "status": "active",
  "track_id": "ws1"
}
```

**Errors:**

- `401 Unauthorized` — Missing or invalid access token
- `403 Forbidden` — User is not admin/mentor
- `404 Not Found` — Group ID does not exist

---

**DELETE** `/tracks/v1/{id}`  
**Purpose:** Delete an existing track (admin only).  
**Path Parameters:**

- `id` (string | uuid) — ID of the track to delete

**Request Body:**

- None

**Response (204 No Content):**

- Indicates successful deletion, no content returned

**Errors:**

- `401 Unauthorized` — Missing or invalid access token
- `403 Forbidden` — User is not admin
- `404 Not Found` — Track ID does not exist

---

### Chat and Messages

**DELETE** `/groups/{id}`  
**Purpose:** Delete an existing group (admin only).  
**Path Parameters:**

- `id` (string | uuid) — ID of the group to delete

**Request Body:**

- None

**Response (204 No Content):**

- Indicates successful deletion, no content returned

**Errors:**

- `401 Unauthorized` — Missing or invalid access token
- `403 Forbidden` — User is not admin
- `404 Not Found` — Group ID does not exist

---

**GET** `/groups/v1/{id}/messages`
**Purpose:** Retrieve messages from a group using cursor-based pagination.  
**Path Parameters:**

- `id` (string | uuid) — ID of the group

**Query Parameters:**

- `after` (string | message ID) — Return messages after this cursor
- `limit` (integer) — Maximum number of messages to return

**Response (200 OK):**

```json
{
  "messages": [
    {
      "id": "msg1",
      "content": "Hello world",
      "file_id": null,
      "sent_at": "2025-08-21T10:00:00Z",
      "sender_id": "uuid_user1"
    }
  ],
  "next_cursor": "msg1"
}
```

**Errors:**

- `401 Unauthorized` — Missing or invalid access token
- `403 Forbidden` — User not a member of the group
- `404 Not Found` — Group does not exist

---

**POST** /groups/v1/{id}/messages

**Purpose:** Send a message to a group.

**Path Parameters:**

- `id` (string | uuid) — ID of the group

**Request Body:**

```json
{
  "content": "Optional text message",
  "file_id": "Optional file reference"
}
```

**Response (201 Created):**

```json
{
  "id": "msg123",
  "content": "Optional text message",
  "file_id": "file_uuid",
  "sent_at": "2025-08-21T10:05:00Z",
  "sender_id": "uuid_user1"
}
```

**Errors:**

- `401 Unauthorized` — Missing or invalid access token
- `403 Forbidden` — User not allowed to send messages in this group
- `404 Not Found` — Group does not exist

---

**DELETE** `/groups/v1/{gid}/messages/{mid}`

**Purpose:** Soft delete a message (mentor/admin only).
**Path Parameters:**

- `gid` (string | uuid) — Group ID

- `mid` (string | uuid) — Message ID

**Response (204 No Content)**

**Errors:**

- **401 Unauthorized** — Missing or invalid access token
- **403 Forbidden** — User not allowed to delete message
- **404 Not Found** — Group or message does not exist

---

### Resource Library

_Notes_

Here we will be using Azure's Blob cloud service which allows us to request 'presigned' links that allow afe direct upload or download to storage without exposing full storage credentials.

This is the general flow for requesting to upload or download files from our resources DB.

Client → API:
POST /files/presign with metadata (filename, mime, size, scope).

API → Azure:
Requests a SAS URL (write permission, limited lifetime).

API → Client:
Returns { file_id, upload_url/down_url, headers, expires_in }.

Client → Azure Blob:
Uploads/downloads file directly with that URL.

Client → API:
Calls POST /files/complete with { file_id, checksum } to finalize metadata.

---

**POST** `/resources/v1/presign`

**Purpose:** Request a presigned Azure Blob SAS upload URL for direct client upload.

**Permissions:** Only authenticated mentors, supervisors, and admins can later attach files as resources.

**Request Body:**

```json
{
  "filename": "lesson-notes.pdf",
  "mime": "application/pdf",
  "size": 102400,
  "scope": "group|track|role|public",
  "group_id": "g123", // required if scope=group
  "track_id": "t456" // required if scope=track
}
```

**Response (200 OK)**

```
{
  "file_id": "f789",
  "upload_url": "https://storage.blob.core.windows.net/...SAS...",
  "headers": {
    "x-ms-blob-type": "BlockBlob"
  },
  "expires_in": 900
}
```

**Errors:**

- `400 Bad Request` — invalid parameters
- `403 Forbidden` — user not allowed to upload in given scope

---

**GET** `/resources/v1`

**Purpose:** List all files visible to the current user/group/role.

**Query Parameters:**

- scope — group|track|role (at least one)
- group_id (optional)
- track_id (optional)
- page (optional, default=1)
- size (optional, default=20)

**Response (200 OK):**

```json
{
  "resources": [
    {
      "id": "f789",
      "filename": "lesson-notes.pdf",
      "scope": "group",
      "group_id": "g123",
      "uploaded_by": "u123",
      "created_at": "2025-08-22T10:00:00Z"
    }
  ],
  "page": 1,
  "size": 20,
  "total": 57
}
```

---

**DELETE** `/files/v1/{id}`

**Purpose** Soft delete a file (mark as unavailable).

**Permissions:** File owner, mentor, supervisor, or admin.

**Request:**

- None

**Response:**

**200 OK — file marked as deleted**

**Errors:**

- `403 Forbidden` — user not allowed
