# Matching App Documentation

**Goal:** This is a Django app that implements a **student-mentor matching system** for an educational/biotech program. It handles:
- Importing student and mentor data from Excel spreadsheets
- Automatically grouping students (by preassigned groups or shared interests)
- Assigning mentors to student groups based on track policies and interest overlap
- Admin interface for managing the matching process

---

## File Structure

```
matching/
├── __init__.py
├── apps.py
├── models.py
├── views.py
├── urls.py
├── admin.py
├── management/
│   └── commands/
│       └── import_p11.py
├── tests/
│   ├── __init__.py
│   ├── test_helpers.py
│   ├── test_views_api.py
│   ├── test_model_smoke.py
│   └── test_command_import.py
└── templates/
    └── admin/matching/
        ├── replace_group_mentor.html
        └── studentgroup/change_list.html
```

---

## Data Models (`models.py`)

### Track (Enum)
Geographic/program tracks:
| Value | Description |
|-------|-------------|
| `AUS-NSW` | Australia - New South Wales |
| `AUS-QLD` | Australia - Queensland |
| `AUS-VIC` | Australia - Victoria |
| `AUS-WA` | Australia - Western Australia |
| `BRA` | Brazil |
| `GLOBAL` | International/other |

### Experience (Enum)
Mentor background categories:
| Value | Description |
|-------|-------------|
| `UG` | University - Undergraduate |
| `PG` | University - Postgraduate |
| `HDR` | University - HDR |
| `AC` | Academic |
| `IN` | Industry |

### Interest
Simple lookup table for interest areas (e.g., "AI", "Robotics", "Biology").

**Fields:**
- `name` (CharField, max=80, unique)

### Student
Student entity participating in the program.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `first_name` | CharField(80) | Student's first name |
| `last_name` | CharField(80) | Student's last name |
| `email` | EmailField(unique) | Email address |
| `supervisor_email` | EmailField(blank) | Supervisor's email |
| `school` | CharField(200, blank) | School name |
| `year_level` | PositiveSmallIntegerField | Year level (9-12) |
| `country` | CharField(80) | Country |
| `region` | CharField(80, blank) | State/region |
| `preassigned_group` | CharField(64, blank) | Preassigned group number from spreadsheet |
| `track` | CharField(16) | Assigned track (default: GLOBAL) |
| `interests` | ManyToManyField(Interest) | Student's interest areas |

### StudentGroup
A group of students (typically ≤5) assigned to one mentor.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(120) | Group name |
| `track` | CharField(16) | Group's track |
| `year_min` | PositiveSmallIntegerField | Minimum year level of members |
| `year_max` | PositiveSmallIntegerField | Maximum year level of members |
| `interests` | ManyToManyField(Interest) | Union of member interests |
| `members` | ManyToManyField(Student) | Group members |
| `mentor` | ForeignKey(Mentor, nullable) | Assigned mentor |

### Mentor
Mentor entity with capacity and track assignment.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `first_name` | CharField(80) | Mentor's first name |
| `last_name` | CharField(80) | Mentor's last name |
| `email` | EmailField(unique) | Email address |
| `is_active` | BooleanField(default=True) | Active status |
| `background` | CharField(120, blank) | Background description |
| `institution` | CharField(200, blank) | Institution/company |
| `country` | CharField(80) | Country |
| `region` | CharField(80, blank) | State/region |
| `track` | CharField(16) | Assigned track (default: GLOBAL) |
| `max_groups` | PositiveSmallIntegerField(default=1) | Maximum groups mentor can handle |
| `interests` | ManyToManyField(Interest) | Mentor's interest areas |

### MentorAvailability
Time availability slots for mentors.

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `mentor` | ForeignKey(Mentor) | Related mentor |
| `weekday` | PositiveSmallIntegerField | Day of week (0=Mon, 6=Sun) |
| `start` | TimeField | Start time |
| `end` | TimeField | End time |

---

## API Endpoints (`views.py` + `urls.py`)

### `POST /api/reset_groups/`
Reset group/mentor assignments.

**Query Parameters:**
| Param | Values | Default | Description |
|-------|--------|---------|-------------|
| `mode` | `delete_all`, `clear_mentors`, `clear_members` | `delete_all` | Reset mode |
| `reset_seq` | `1`, `0` | `1` | Reset auto-increment sequence |

**Modes:**
- `delete_all`: Delete all groups (including membership and mentor assignments)
- `clear_mentors`: Keep groups and members, only clear mentors
- `clear_members`: Keep groups, clear members and mentors

**Response:**
```json
{
  "mode": "delete_all",
  "deleted_groups": 10,
  "sequence_reset": true
}
```

---

### `POST/GET /api/auto_group/`
Primary grouping logic - creates student groups.

**Process:**
1. **Step 1 - Preassigned Groups:** Create groups from `preassigned_group` field
   - Split into chunks of 5 if group exceeds capacity
   - Naming: `GN`, `GN-1`, `GN-2` for overflow

2. **Step 2 - Interest-based Grouping:** For students without preassigned groups
   - Group by shared interests within same track
   - Maximum 5 students per group

**Response:**
```json
{
  "created_from_preassigned": [
    {
      "group": "Group-1",
      "track": "GLOBAL",
      "size": 4,
      "members": ["John Doe", "Jane Smith"],
      "interests": ["AI", "Robotics"]
    }
  ],
  "created_auto": [...]
}
```

---

### `POST/GET /api/auto_group_fallback/`
Fallback grouping for remaining ungrouped students.

**Process:**
1. **Pass 1:** Shared-interest grouping within same track
2. **Pass 2:** Greedy grouping by:
   - Year-distance (closest year levels)
   - Country proximity (for GLOBAL track, prefer same country)

**Response:**
```json
{
  "created_groups": [
    {"name": "Group-5", "track": "GLOBAL", "size": 3}
  ]
}
```

---

### `POST/GET /api/assign_mentors/`
Assign mentors to groups without one.

**Algorithm:**
1. For each group without a mentor:
   - Build candidate layers based on track policy:
     - Regional tracks (AUS-*, BRA): same track → GLOBAL → others
     - GLOBAL track: GLOBAL → others
   - Filter by: mentor capacity remaining AND ≥1 overlapping interest
   - Score candidates: `(overlap_count × 100) + (same_country ? 1 : 0)`
   - Select highest scoring mentor from first non-empty layer

**Response:**
```json
{
  "assigned": [
    {
      "group": "Group-1",
      "track": "GLOBAL",
      "mentor": "John Mentor",
      "background": "AI Research",
      "remaining_capacity": 0
    }
  ],
  "skipped": [
    {"group": "Group-2", "track": "BRA", "reason": "no_available_mentor"}
  ]
}
```

---

### `GET /api/health/`
Simple health check endpoint.

**Response:**
```json
{"status": "ok"}
```

---

### `POST /api/replace_group_mentor/`
Replace a group's mentor.

**Request Body:**
```json
{
  "group_id": 1,
  "new_mentor_id": 5
}
```

**Side Effects:**
- Sends email notification to:
  - All group members
  - Their supervisors (if email provided)
  - Old mentor
  - New mentor

**Response:**
```json
{
  "group": "Group-1",
  "old_mentor": "Previous Mentor",
  "new_mentor": "New Mentor"
}
```

---

### `POST /api/deactivate_mentor/`
Deactivate a mentor account.

**Request Body:**
```json
{"mentor_id": 5}
```

**Side Effects:**
- Sets `is_active = False`
- Clears mentor from all assigned groups
- Sends notification emails

**Response:**
```json
{
  "deactivated": 5,
  "cleared_groups": ["Group-1", "Group-2"]
}
```

---

### `GET /api/bulk_inactive_mentors_preview/`
Placeholder for future bulk deactivation preview.

**Response:**
```json
{
  "inactive_candidates": [],
  "criteria": "placeholder; to be implemented"
}
```

---

### `POST /api/bulk_replace_inactive_mentors/`
Placeholder for future bulk replacement.

**Response:**
```json
{
  "status": "placeholder",
  "reassigned": [],
  "deactivated": []
}
```

---

## Helper Functions (`views.py`)

| Function | Description |
|----------|-------------|
| `_union_interests(members)` | Returns union set of interests from a list of students |
| `_chunk(lst, n)` | Yield successive n-sized chunks from a list |
| `_year_distance(a, b)` | Absolute difference between two year levels |
| `_mentor_capacity_left(m)` | Remaining groups a mentor can take |
| `_interest_overlap_score(group_interests, mentor_interests)` | Count of overlapping interests |
| `_mentor_score(group, mentor)` | Scoring: `(overlap × 100) + (same_country ? 1 : 0)` for GLOBAL |
| `_get_json_body(request)` | Parse JSON body from request |
| `_notify_replacement(group, old_mentor, new_mentor)` | Send email notifications |

---

## Admin Interface (`admin.py`)

### NoAddMixin
Mixin to completely disable the "Add" action in Django admin.

### InterestAdmin
- Search by name
- No add permission (interests managed via import)

### StudentAdmin
- **List Display:** ID, name, email, year level, track, country, region, group, mentor
- **Filters:** Track, year level, country, region, preassigned group
- **Search:** First name, last name, email, school
- **Computed Columns:** Groups list, Mentors list

### StudentGroupAdmin
- **List Display:** ID, name, track, year range, mentor, member count, members
- **Filters:** Track, mentor
- **Actions:**
  - `action_replace_group_mentor`: Replace mentor for selected groups
- **Custom Views:**
  - `replace_mentor_view`: Form for mentor replacement
  - `reassign_mentors_view`: Bulk reassign mentors for groups without one

### MentorAdmin
- **List Display:** ID, name, email, track, background, max groups, current load, groups
- **Filters:** Track, background, country
- **Actions:**
  - `action_deactivate_mentors`: Deactivate selected mentors and clear their assignments

---

## Data Import Command (`management/commands/import_p11.py`)

### Usage
```bash
python manage.py import_p11 <xlsx_path> [--students-sheet SHEET] [--mentors-sheet SHEET]
```

### Helper Functions

| Function | Purpose |
|----------|---------|
| `norm(s)` | Normalize string (trim, None→"") |
| `titleish(s)` | Convert to Title Case, collapse spaces |
| `parse_interests(raw)` | Parse interest string split by `;,/\|` delimiters |
| `map_track(country, region)` | Map country/region to Track enum |
| `map_experience(raw)` | Map experience text to Experience enum |
| `pick(df, key, alias_map, default)` | Get DataFrame column by flexible aliases |
| `cell(col, i)` | Get single cell value from Series or scalar |

### Column Alias Maps
The import command uses flexible column name matching to handle spreadsheet variations:

**Student Columns:**
- `first_name`: "First Name (Synthestic)", "First Name (Synthetic)", "First Name", etc.
- `last_name`: "Last Name (Synthestic)", "Last Name (Synthetic)", "Last Name", etc.
- `email`: "Email (Synthestic)", "Email (Synthetic)", "Email", etc.
- `year_level`: "Year Level *", "Year Level", "YEAR LEVEL", etc.
- `interests`: "Area(s) of Interest", "Interests", etc.
- `group_number`: "Group Number", "Group", "Group #"

**Mentor Columns:**
- Similar flexible matching for mentor fields

---

## Matching Algorithm Summary

### Grouping Flow
```
1. Preassigned Groups
   ├── Students with preassigned_group field
   ├── Split into chunks of 5 if needed
   └── Naming: GN, GN-1, GN-2 for overflow

2. Interest-based Grouping
   ├── Students without preassigned groups
   ├── Group by shared interests within track
   └── Maximum 5 students per group

3. Fallback Grouping
   ├── Pass 1: Shared-interest grouping (retry)
   └── Pass 2: Greedy by year-distance + country proximity
```

### Mentor Assignment Flow
```
For each group without mentor:
  1. Build candidate layers by track policy:
     - Regional (AUS-*, BRA): same_track → GLOBAL → others
     - GLOBAL: GLOBAL → others

  2. Filter candidates:
     - Capacity remaining (max_groups - current_groups) > 0
     - At least 1 overlapping interest

  3. Score candidates:
     - score = (overlap_count × 100) + (same_country ? 1 : 0)

  4. Select highest scoring from first non-empty layer
```

---

## Email Notifications

The system sends email notifications for:
1. **Mentor Replacement:** When a group's mentor changes
   - Recipients: Group members, supervisors, old mentor, new mentor

2. **Mentor Deactivation:** When a mentor is deactivated
   - Recipients: The deactivated mentor, affected group members and supervisors

---

## Test Suite (`tests/`)

| File | Description |
|------|-------------|
| `test_helpers.py` | Unit tests for import helpers (`norm`, `titleish`, `parse_interests`, `map_track`, `map_experience`) |
| `test_views_api.py` | API endpoint tests |
| `test_model_smoke.py` | Basic model instantiation tests |
| `test_command_import.py` | Import command tests |