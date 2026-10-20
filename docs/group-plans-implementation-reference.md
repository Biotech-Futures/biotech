# Group plans: implementation reference

This supports the [three-person working plan](group-plans-technical-plan-final-3-people.md). It contains the proposed model/API contract and checks needed for implementation. Read the working plan first for scope, ownership, dependencies and decided defaults. TK4 remains separate.

**Client Q&A conflict:** Will's response to item 2 permits student ticks; this reference still describes the earlier no-student-shared-ticks default. Reconcile that difference before implementing permission checks, checkbox states or their tests. Do not treat the current denial rule as client-approved.

**Ownership:** Person 1 owns GP2 (8 points); Person 2 owns GP1 + GP5 (10); Person 3 owns GP3 + GP4 (10). Person 2 shares models/helpers first, enabling Persons 1 and 3's backends. Person 2 can build reporting with test data after GP1; the full create/tick/report check waits for GP2–GP4. Person 1 integrates shared admin API/navigation changes and coordinates release; Person 2 verifies migrations/seeds, and Person 3 verifies member-role scenarios.

**TK4 is not a GP dependency:** start `feat/group-plans` from the agreed updated `main` without waiting for TK4. Use existing admin components and keep plan models/migrations/endpoints independent; do not import unmerged TK4-specific components. Keep separate PRs and no TK4 blocker on the GP epic. Either PR can merge first after its own review/checks; the second branch incorporates updated `main`, resolves shared-file overlaps and reruns affected checks. Person 1 coordinates these GP integration edits; TK4 work remains with its separate owner.

**Branch workflow:** each person branches from the shared `feat/group-plans`. Person 2 uses `feat/group-plans-foundation` for the early GP1 handover, with a PR back into the shared branch. Persons 1 and 3 merge the updated shared branch into their own branches to get the models/helpers. Keep individual feature work off the shared branch until reviewed. Run local checks for these PRs; use a draft shared-branch PR into `main` for integrated CI.

## 1. Implementation details

### Verified building blocks

| Existing code | What it establishes |
|---|---|
| `backend/apps/tasks/models.py` | Ordinary tasks have one completion flag; their target constraint prevents assigning both a group and a person |
| `backend/apps/groups/models/group_members.py` | One active membership per user/group, with a group-specific role and `left_at` |
| `backend/apps/common/rbac.py` and `backend/apps/admin/permissions.py` | Backend admins are identified by an `AdminScope` row, not staff status alone; `group_participant_qs` reads active memberships |
| `backend/apps/submissions/services.py` | `current_cohort()` uses the newest active deadline's year through `timezone.localtime()`, otherwise the current local year |
| `frontend/src/components/submission/GroupSubmissionSection.vue` | Existing route-driven sections, lazy mounting and group-change requests can be extended for Plan |
| `frontend/src/views/admin/AdminTasksPage.vue`, `components/admin/FormSheet.vue` and `utils/adminAPI.ts` | Existing table, form, session/CSRF and response-envelope patterns can be reused without TK4 |

Unprefixed paths within the frontend row are relative to `frontend/src/`. Reuse UI and transport patterns, not ordinary tasks' assignment/status behaviour.

### Data model

Use a separate `backend/apps/plans/` app. Existing `Task` stores a single completion flag and cannot represent each person's completion within a group. The new app keeps the plan migration independent of role tasks.

Preserve existing per-user tasks created by the old role-assignment approach: group plans must not delete, convert or migrate those records. TK4 remains separate, but its owner must preserve the same client requirement.

| Model | Fields and rules |
|---|---|
| `PlanStage` | `name` (max 255), `description` (optional introduction), `position` (non-negative integer), `deleted_at`, creation/update timestamps |
| `PlanTask` | Required `stage` FK (`PROTECT`), `position` (non-negative integer), `name` (max 255), `description` (instructions), optional `resource_url` and `resource_label`, nullable `due_date` (`DateField`), `audience_role`, `completion_mode` (default `per_person`), nullable `created_by` (`SET_NULL`), `deleted_at`, creation/update timestamps |
| `PlanTaskCompletion` | `task`, `group`, nullable `user`, `completed` (default false), update timestamp. `user=null` means the shared per-group record. No separate status field |

Audience values are `student`, `mentor`, `supervisor`; modes are `per_person`, `per_group`. Match audience to `GroupMembership.membership_role`, rather than the person's platform role.

Add conditional unique constraints for `(task, group, user)` when user is present, and `(task, group)` when user is null. The service chooses the correct record type from the task mode. Completion foreign keys use `CASCADE`: hard deletion removes dependent records; soft deletion retains them.

Every live task belongs to an active stage. Order stages by `(position, id)` and tasks within each stage by `(position, id)`; duplicate positions are allowed and IDs break ties. Use simple numeric order fields in the admin forms, without drag-and-drop. Moving a task changes its stage/order only, preserving its ID and completion records. Reject deletion of a stage containing live tasks; soft-delete an empty stage and retain its deleted tasks and records. Reject task writes to deleted stages. Define active task reads centrally as both task and stage not deleted, and use that filter in member lists, toggles, admin reads and reporting.

The initial migration creates all three models and depends on groups and users, not tasks; generate dependencies against the chosen implementation baseline. Do not use a field default that calls `current_cohort()`, because it queries the database during migrations. Register all three models read-only in Django admin for inspection, so that interface cannot bypass service validation, locking or audit. Stage mutations are admin-only and audited, like task mutations.

Resource fields are optional; the resulting task must have both a valid HTTP/HTTPS URL and a non-empty label, or both empty. Validate the merged existing/new values on PATCH, so changing only a label is allowed. Trim names/labels, reject blank names and negative/non-integer positions, and reject invalid roles/modes and dates. Render guidance as plain text and resource links with `rel="noopener noreferrer"` if opened in a new tab; no embedded content or rich-text editor is needed.

**Seed data (Person 2):** extend `backend/apps/admin/management/commands/seed_dummy_data.py` after groups are created. Prefix stage/task names with `SEED_PREFIX`. In `_wipe`, delete seeded tasks before seeded stages (the stage FK is protected), and before seed users/groups. Refuse stage cleanup if a non-seed task references it. Use a local database whose active cohort matches the seeded group year; do not change a real deadline to make demo data visible.

### Shared visibility and permissions

Keep eligibility in `visibility.py`:

- `current_plan_groups(year)`: non-deleted groups with the supplied year. Read `current_cohort()` once per request.
- `group_sees_plan(group, year)`: uses that same rule.
- `active_audience_memberships(group_ids)`: memberships with `left_at=null` and one of the three audience roles. Include active memberships regardless of account login status.

In `permissions.py`, compute the viewer's `is_admin`, active group membership role and permission to complete per-group tasks once per request. Use `is_admin` and `group_participant_qs` from `apps/common/rbac.py`. Reuse `_is_active_group_mentor` and `_supervises_any_in_group` from `apps/tasks/permissions.py`; these helpers exist but are private, so document the cross-app imports and leave their behaviour unchanged. Make `can_tick_plan_task` a query-free function, and return its result as `can_toggle` on each item.

An admin, active group member, or supervisor with per-group completion permission may access the group plan. Return 404 for other viewers. Per-person completion is available only when the viewer's active group role matches the audience, even for an admin. Prefetch only this group's viewer/shared completion records, and join stages when reading tasks, to avoid a query per task or stage. Never accept another user's ID in a completion request.

For task visibility, admins receive all active tasks. Other viewers receive tasks matching their active group membership role, plus every per-group task if they hold shared-task completion permission. A supervisor linked only through a student's profile can see/tick shared tasks, but needs an active supervisor membership to receive supervisor per-person tasks. Students cannot tick shared tasks. Apply this same visibility filter to list and completion endpoints.

### Completion, locks and audit

Apply completion changes within a transaction. Per-person requests affect only the requesting user's record; per-group requests use `user=null`. An explicit untick with no existing record creates nothing and writes no audit entry. A tick followed by an untick retains its record.

**Concurrent requests:** a transaction alone does not protect the “no ticks yet” check. Task edits/deletion and completion writes must lock the same `PlanTask` row with `select_for_update()`, then re-read mode, audience, deletion and completion-lock state before changing anything. This also serialises first ticks and flips when no completion row exists yet. Stage deletion and task creation/moves must lock the affected stages in a consistent ID order before locking tasks, then recheck that target stages are active and deleted stages have no live tasks. Persons 1 and 3 agree this protocol before implementing mutations; verify it on PostgreSQL, since SQLite tests do not prove row locking works.

Use the same completion-record check for backend validation and the admin form's `has_completions` flag: any record for the task in `current_plan_groups(year)`, including an unticked record. Previous-year and soft-deleted-group records do not lock the task. Audit create, update, delete and completion changes, including the actor and before/after values; completion events also identify the group and mode.

**Returning-group operating rule:** before restoring a group or changing the deadline back to an earlier cohort, an admin checks task audit history for changes to audience/mode while the group was excluded. If settings changed, or compatibility cannot be established, soft-delete the affected task and create a new task before the group returns. The new task has a new ID and no inherited ticks for any group. If settings are unchanged, existing ticks may reappear. Include audience and mode in task mutation audit snapshots to support this check. Person 1 owns the admin checklist; this version does not automatically detect or block incompatible group restoration/deadline changes, and does not introduce yearly templates.

### Dates and progress

Send due dates as `YYYY-MM-DD` or `null`; reject datetime strings. Use stage/task position as the default order on the member page and progress matrix; due dates label tasks rather than determine the journey. The admin task table may still offer due-date sorting, with undated tasks last. Format dates with `formatShortDate(value, 'UTC')`; compare with `toTimeZoneDateKey(new Date(), getSetTimeZone())` from `utils/date.ts`. Show Overdue only for `completed === false` with a due date before today, not for null personal completion viewed by an admin.

Use `PlanTask.objects.active().in_plan_order()` for display lists. This shared helper orders by stage position, stage ID, task position and task ID; the model has no implicit ordering. Build distinct/grouped reporting queries from an unordered queryset, or clear an existing display order with `.order_by()` before `values(...).distinct()` or `values(...).annotate(...)`.

Due dates are fixed, without per-group extensions. All groups read the shared task live, so an admin's date edit during the current cohort appears for every current-year group on its next load; no completion records are reset or copied.

Calculate progress with grouped queries, rather than a query for every cell:

- **Per person:** completed records belonging to current active audience members / number of current active audience members.
- **Per group:** `0/1` or `1/1`.
- **Empty per-person audience:** show `0/0`, without calculating a percentage. Shared tasks always use `0/1` or `1/1`, even if that group has no members in the named audience.

For per-person counts, match each completion to an active membership with the same group, user and task audience; do not count every saved tick. Count shared records separately from person records. Exclude deleted tasks/stages and ineligible groups. Sort groups with `group_name_sort_key()` from `apps/groups/models/groups.py`, then ID. Use grouped queries for counts and audience sizes; keep query counts independent of the number of tasks and groups. A fixed query count does not bound payload size: GP5 should check matrix rendering with the expected number of groups/tasks before release.

Member stage summaries are calculated in the frontend from visible items: count `completed === true` over items with a boolean `completed` value. Exclude null values, hide a zero-denominator summary, and update the summary after a successful tick. Label it “Your view” to distinguish it from the admin's group-wide totals: one personal task plus one shared task gives a denominator of two, not the number of group members. Stages with no visible tasks are omitted. No new completion records or progress endpoint are needed for stages.

### Frontend integration

Add `GroupPlanSection.vue` through the existing `GroupSubmissionSection.vue` section switcher. The parent fetches `{year, stages, items}` when the group changes and passes stages/items to the child; show the Plan tab only when items exist. Key/reset the child by group ID and ignore late responses for another group, following the existing `fetchFinalist` watch. Do not initialise the child from items alone or leave ticks from a previous group in memory. Add the uniquely named `/groups/:id/plan` route pointing to `GroupDetailPage.vue`, and `group-plan` to `SECTION_ROUTES`. Empty or inaccessible plans fall back to Tasks and Chat; transient load errors should offer retry rather than be presented as an empty plan.

Use `can_toggle` to enable checkboxes. When `completed` is null, show “Each person ticks their own”. Label shared tasks “Whole group”. Send the explicit desired boolean, disable that checkbox while saving, replace the item with the successful response and leave it unchanged on failure. Display API errors. Re-fetch on a later visit to Plan so admin edits appear; no live push is required.

Group the tasks under stage headings with the stage introduction and “Your view” progress summary. Display each task's instructions and optional labelled resource link. Keep all stages available; completing an earlier stage is not a prerequisite for opening the next one.

Build the admin list/form using `AppDataTable.vue` and `admin/FormSheet.vue`, with `AppSelect` (on the inspected `origin/main`) for audience and stage, and radio buttons for mode. Disable audience and mode when `has_completions` is true, with an explanation. On the same builder page, allow stage creation/editing/deletion and numeric ordering; add task fields for order and resource link/label. With no stages, prompt the admin to create one before adding a task. Add `/admin/plan` and `/admin/plan/progress` with `meta: { requiresAdmin: true }`, plus one Plan link in `App.vue`'s `sidebarSections` admin links array, active for both routes. The progress page shows a group-by-task matrix and group-name filter, with the stage name in each task column heading and an empty state for no groups/tasks.

Keep existing section behaviour. Its `canSeeSubmission` checks normalised frontend roles; in the inspected `stores/auth.ts`, unknown roles fall back to student, so it does not currently exclude every account with an unrecognised role as the earlier plan claimed. Backend authorisation remains the source of truth. Frontend `isAdmin` also includes staff/superusers, while `IsAdminScoped` requires `AdminScope`; handle denied API requests rather than using the UI role as proof of access.

## 2. API contract

Admin endpoints use authentication plus `IsAdminScoped` and the existing `{msg, data}` response envelope. Member endpoints require authentication and return plain JSON.

Person 1 owns admin API types in `adminAPI.ts`; Person 3 owns member types in `plansAPI.ts`. Agree the common stage/task fields with Person 2 before mocks diverge. Use `adminRequest` for admin calls only. For member calls, follow the session/CSRF/header/error pattern in `tasksAPI.ts`, targeting `/api/v1/plans/`; the admin helper prepends a different URL and must not be used for these calls. New plan paths are canonical `/api/v1/` routes with no legacy fallback. Person 2 adds `apps.plans` to `INSTALLED_APPS` and `path("plans/", include("apps.plans.urls"))` to `_api_v1_patterns` in `backend/config/urls.py`.

| Method | Path | Result |
|---|---|---|
| GET / POST | `/api/v1/admin/plan-stage/` | Ordered stage list / create stage |
| PATCH / DELETE | `/api/v1/admin/plan-stage/<id>/` | Edit / soft-delete an empty stage |
| GET / POST | `/api/v1/admin/plan-task/` | Paginated list / create task |
| GET / PATCH / DELETE | `/api/v1/admin/plan-task/<id>/` | Read / edit / soft-delete task |
| GET | `/api/v1/admin/plan-task/progress/` | Current-year progress matrix |
| GET | `/api/v1/plans/groups/<group_id>/tasks/` | Visible tasks with completion and `can_toggle` |
| POST | `/api/v1/plans/groups/<group_id>/tasks/<task_id>/check/` | Set or flip completion; return updated item |

**Stage:** `{id, name, description, position}`. This shared response shape is called `AdminPlanStage` in the admin client and `PlanStage` in the member client; `Stage` below is shorthand for that shape. Admin GET returns `data: {items: Stage[]}` containing all active stages, including empty ones, ordered by position then ID. POST/PATCH return the stage in `data`. Writes accept name, description and position; name is required on create, description defaults to empty and position to zero. Return 400 when deleting a stage with live tasks and 404 for missing/deleted stages. DELETE succeeds with an empty 204 response.

**Member item:** `{id, stage_id, position, name, description, resource_url, resource_label, due_date, audience_role, completion_mode, completed, can_toggle}`. Empty resource fields are empty strings. `completed` is boolean, or null for a per-person task viewed by someone outside its audience. The list is `{year, stages, items}`; return only stages represented in the viewer's visible items, with both arrays in stage/task order. A previous-year or empty plan returns empty arrays.

**Admin item:** `{id, stage_id, position, name, description, resource_url, resource_label, due_date, audience_role, completion_mode, has_completions, created_by, created_at, updated_at}`, with `created_by: {id, name} | null`. GET-detail, POST and PATCH return this item in `data`, including a freshly calculated `has_completions`. List data is `{items, total, page, limit, has_more}`. Support positive integer `page` (default 1), `limit` (default 10, maximum 100), and `sortBy` values `position`, `name`, `due`, `createdAt`, with `sortOrder=asc|desc`. Default to stage/task position ascending with ID tie-breakers. Reject invalid query values with 400 instead of allowing integer-conversion errors to become 500s.

**Progress data:** `{year, stages, tasks, groups}`. Tasks contain `{id, stage_id, position, name, audience_role, completion_mode, due_date}`. Include stages represented by active tasks and order tasks by stage/task position. Each group contains `{id, name, cells}`, where `cells` maps task IDs to `{completed, total}`.

**Writes:** task create requires name, audience and an active `stage_id`; mode defaults to `per_person`, position to zero and resource fields to empty strings. PATCH accepts the editable task fields, including stage, order and resource fields. Return 201 for create, 200 for reads/updates and 204 for delete; invalid input or locked-setting changes return 400, missing/deleted tasks return 404.

**Completion body:** `{completed: true|false}` sets the value; `{}` flips it. Accept actual JSON booleans only; reject null, strings, numbers, user IDs and unknown fields with 400. Return the updated member item as plain JSON. For authenticated requests, check group access/year and task visibility first (404), then completion permission (403), then body validation (400). An authorised list request for a previous-year group returns 200 with empty `stages` and `items`.

Use consistent admin errors `{msg, data: null}` and member validation errors `{detail}`. Explicitly map validation failures to 400: existing `AdminTaskDetailView.patch` can return 200 for service errors, so do not copy that behaviour. Authentication failures follow existing DRF authentication configuration.

## 3. Checks before completion

Each owner tests their stories. Cover these behaviours once in the appropriate model, service, API or component tests:

- Unique completion records, both modes, role visibility, own-record completion and denied requests.
- Field locks, validation, soft deletion and audit records.
- Editing a due date updates two current-year groups after reload without changing ticks; existing legacy per-user task rows remain untouched.
- A replacement task starts unticked for every group; deleted-task ticks are retained but never applied to its replacement. Cover both individual and shared completion.
- Late joiners, leavers, mentor replacement and moves between groups.
- Current-year visibility, Waiting Area inclusion and rollover through the active deadline.
- Accurate progress, including empty per-person audiences, shared tasks with no audience members, and suspended/deactivated accounts with active memberships.
- Stable query counts as task/group counts grow.
- Plan tab visibility/routing, checkbox states, null completion, date formatting and admin form locks.
- Stage/task ordering, moving tasks without losing ticks, and rejecting deletion of stages with live tasks.
- Resource URL/label validation and rendering, stage summaries excluding null completion, and hiding stages with no visible tasks.
- First-tick/edit races, concurrent shared ticks and stage delete/move races on a local PostgreSQL database using transaction tests. SQLite unit tests alone cannot validate the locking protocol.
- Seed creation/cleanup respecting stage protection, API envelopes and validation status codes, and changing groups while a request is in flight.

Update the section-switcher tests' route list and API mocks; rerun its existing tests and `GroupDetailPage.spec.ts`.

During development, run each story's focused tests. Before the combined PR is ready, run `python manage.py test tests --settings=config.settings_test`, `python manage.py makemigrations --check --dry-run` with migrations enabled against a local setup, and `python manage.py migrate` on the local PostgreSQL development database. In `frontend/`, run `npm run type-check`, `npm run test:unit -- --run` and `npm run build-only`. Use `timezone.now()` / `timezone.localdate()` in date-sensitive tests so shifted-clock CI runs remain valid. Do not run database checks against production.

Verified CI runs backend tests with SQLite and migrations disabled, enforces 60% coverage, and repeats tests with a 400-day shift and just after New Year. Frontend CI runs type checking and unit tests. Workflows are filtered to relevant paths and `main` PRs/pushes, so the early draft PR enables checks on feature changes; documentation-only pushes do not exercise the feature. The proposed plan has not passed these checks yet because it is not implemented.

For integration, seed two or three stages with instructions and resource links, covering all audiences, both modes and past/future/no dates. Complete tasks as each role and confirm stage summaries and admin totals. Move a completed task to another stage and confirm its ticks remain. Change the active deadline to next year, confirm the old groups disappear while their records remain, then restore it without changing task audience/mode in between. Separately walk through the admin checklist for changed settings: replace the task before restoring the old cohort and confirm no old ticks appear on the replacement.



