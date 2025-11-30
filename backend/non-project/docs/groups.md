# Groups API

Base path: `/groups/`  
Lookup field: `group_number` (e.g., `/groups/R_49n3r8XlHkOmYKJ_1/`)

Permissions:
- List/Retrieve: authenticated users
- Create/Update/Delete/Actions: admin (is_staff)

Pagination/Search/Ordering:
- Pagination: `?page=` and `?page_size=` (default page_size=10, max=100)
- Search: `?search=` across `group_name`, `group_number`, `track__track_name`
- Ordering: `?ordering=group_name` or `?ordering=creation_datetime` (default `-creation_datetime`)
- Filter: `?track=<track_id>`
- Include deleted (admin only): `?include_deleted=true`

## List Groups
GET `/groups/`
- Auth: required
- Query params: `page`, `page_size`, `search`, `ordering`, `track`, `include_deleted` (admin)

Example:
```
GET /groups/?search=alpha&track=5&ordering=group_name&page=2&page_size=5
```

Response 200:
```json
{
  "count": 23,
  "next": "...",
  "previous": null,
  "results": [
    {
      "group_number": "R_49n3r8XlHkOmYKJ_1",
      "group_name": "team_alpha",
      "track": 5,
      "cohort_year": 2025,
      "creation_datetime": "2025-09-29T12:34:56Z",
      "deleted_flag": false,
      "deleted_datetime": null
    }
  ]
}
```

## Retrieve Group
GET `/groups/{group_number}/`
- Auth: required

Response 200:
```json
{
  "group_number": "R_49n3r8XlHkOmYKJ_1",
  "group_name": "team_alpha",
  "track": 5,
  "cohort_year": 2025,
  "creation_datetime": "2025-09-29T12:34:56Z",
  "deleted_flag": false,
  "deleted_datetime": null
}
```

## Create Group
POST `/groups/`
- Auth: admin
- Body fields (typical): `group_number` (unique), `group_name`, `track` (id), `cohort_year`

Example:
```json
{
  "group_number": "R_xxx",
  "group_name": "team_beta",
  "track": 5,
  "cohort_year": 2025
}
```

Responses:
- 201 Created with serialized group
- 400 Bad Request (validation errors)

## Update/Partial Update Group
PUT/PATCH `/groups/{group_number}/`
- Auth: admin

Responses:
- 200 OK with serialized group
- 400 Bad Request
- 404 Not Found

## Soft Delete Group
DELETE `/groups/{group_number}/`
- Auth: admin
- Behavior: marks `deleted_flag=true`, sets `deleted_datetime`

Responses:
- 204 No Content (idempotent; also returned if already deleted)
- 404 Not Found

## Restore Group (custom action)
POST `/groups/{group_number}/restore/`
- Auth: admin
- Body:
```json
{
  "new_group_name": "optional new name"  // optional; defaults to current name
}
```

Responses:
- 200 OK
```json
{
  "restored": true,
  "renamed": false,
  "group": { "...serialized group..." }
}
```
- 400 Bad Request
```json
{ "new_group_name": ["Name cannot be blank"] }
```
- 409 Conflict if an active group with same name/track/year exists
```json
{ "error": "Another group in 2025: AUS-NSW has been made with this name." }
```

## Register Student (custom action)
POST `/groups/register_student/`
- Auth: admin
- Purpose: Idempotently ensure/restore a group by `GroupNumber`, ensure/create a user by email, and add membership.
- Body: accepts either at root or under `"body"` key, fields:
  - Required: `GroupNumber`, `Title` (student email)
  - Optional: `FirstName`, `Surname`, `Country`, `Region`, `Created` (ISO string for cohort inference)

Example request:
```json
{
  "GroupNumber": "R_49n3r8XlHkOmYKJ_1",
  "Title": "john.smith@education.com",
  "FirstName": "John",
  "Surname": "Smith",
  "Country": "Australia",
  "Region": "NSW",
  "Created": "2025-09-17T09:05:22Z"
}
```

Behavior:
- Cohort year is inferred from `Created` (fallback to current year).
- Track is resolved via `get_supported_track(Country, Region)`:
  - Australia: `AUS-<STATE_SHORT>`
  - Brazil: `BRA`
  - Others: `GLO`
- If group exists and is deleted, it’s auto-restored unless there’s an active name clash (then 409).
- User matched by email; created if missing.
- Membership created if missing (idempotent).

Responses:
- 201 Created (when group newly created) or 200 OK
```json
{
  "group_created": true,
  "user_created": false,
  "member_added": true,
  "group": { "...serialized group..." },
  "student": {
    "id": 42,
    "email": "john.smith@education.com",
    "first_name": "John",
    "last_name": "Smith"
  }
}
```
- 400 Bad Request (field-scoped errors):
```json
{ "group_number": "Group Number not provided." }
```
```json
{ "student_email": "Student Email not provided" }
```
Track resolution errors (from helper):
```json
{ "Country": ["Country 'X' not found."] }
{ "State": ["State 'NSW' not found in country 'Australia'."] }
{ "Track": ["Region (state short form) is required for Australia."] }
{ "Track": ["No Track configured with name 'AUS-NSW'."] }
```
- 409 Conflict (auto-restore name clash):
```json
{ "detail": "Attempted to auto-restore existing group for 2025: AUS-NSW with name team_alpha however one already exists. Rename via /restore." }
```
- 200 OK with partial success if membership add fails (as implemented):
```json
{
  "group_created": false,
  "user_created": true,
  "member_added": false,
  "member_error": "error details",
  "group": { "...serialized group..." }
}
```

Notes:
- Default ordering: newest first (`-creation_datetime`).
- Admins can include deleted groups via `?include_deleted=true`.
- All IDs in payloads referring to related objects (e.g., `track`) are numeric primary keys unless otherwise stated.

## Bulk Import Groups with Members (custom action)
POST `/groups/import/`
- Auth: admin
- Purpose: Accept an object of any number of groups which are lists of students. Creates/ensures groups, ensures users, and add memberships in batch.
- Idempotency:
  - Unique `group_number` per group.
  - Optional header `Idempotency-Key` to stop duplicate processing.
- Transactions: Per-group atomic (one failing group doesn't block other groups from being processed)

Request body:
```json
{
  "groups": [
    {
      "group_name": "Team Alpha",        // optional; fallback to generated group_number
      "country": "Australia",            // required (used to resolve track)
      "region": "NSW",                   // required (used to resolve track)
      "cohort_year": 2025,               // required
      "members": [
        "a@school.edu",
        "b@school.edu"
      ]
    }
  ]
}
```

Rules and behavior:
- Track resolution:
  - Resolved via `get_supported_track(country, region)`:
    - Australia → `AUS-<STATE_SHORT>`
    - Brazil → `BRA`
    - Others → `GLO`
  - If resolution fails, the group item returns a field-scoped error (see errors below).
- Group number:
  - Generated by server (e.g., `G-<uuid>`). Returned in response.
- Group name:
  - If provided, used as-is (subject to uniqueness rule below).
  - If missing, set to the generated `group_number`.
- Name conflicts (quick solution):
  - If an active group already exists in the same `(track, cohort_year, group_name)`, server auto-suffixes the name: `Team Alpha-2`, `Team Alpha-3`, … until unique.
  - Response includes `name_conflict: true` and `final_group_name`.
  - Alternative (future): allow client to opt into “error on conflict” mode for strictness.
- Members:
  - Each member is a string email.
  - Assumed users already exist and are not currently in a group.
  - For each email, server fetches existing user and creates membership.
  - If user not found or already in a group, a per-member error is returned (the rest of the group still processes).
- Transactions:
  - Per-group atomic (errors in one group don’t affect others).

  Responses:
- 200 OK (mixed outcomes allowed)
```json
{
  "results": [
    {
      "group_number": "G-3b1a2c",
      "requested_group_name": "Team Alpha",
      "final_group_name": "Team Alpha-2",
      "name_conflict": true,
      "track": 5,
      "cohort_year": 2025,
      "group_created": true,
      "group_restored": false,
      "member_added_count": 2,
      "member_errors": [null, null],
      "errors": []
    },
    {
      "requested_group_name": "Team Beta",
      "errors": [
        {"Country": ["Country 'X' not found."]}
      ]
    }
  ]
}
```

Error semantics (per group item):
- Track resolution (from helper):
  - {"Country": ["Country 'X' not found."]}
  - {"State": ["State 'NSW' not found in country 'Australia'."]}
  - {"Track": ["Region (state short form) is required for Australia."]}
  - {"Track": ["No Track configured with name 'AUS-NSW'."]}
- Validation:
  - {"country": ["This field is required."]}
  - {"region": ["This field is required."]}
  - {"cohort_year": ["This field is required."]}
- Member-level:
  - For each email index, `null` for success or an error object, e.g.:
    - {"email": ["User not found."]}
    - {"email": ["User is already in a group."]}


> [!IMPORTANT]
> Discuss groupingType since a teacher is not making a group, do we make groups based on if the group should allow members to be from different schools?

