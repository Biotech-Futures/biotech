# Technical Implementation Plan: Group Plans

## Goal

Build the **Group Plans** feature, inspired by Chronus connection plans, into the mentoring platform. Administrators create one shared journey of stages and tasks for current-year groups. Members follow the guidance and record completion; administrators monitor progress across groups.

**Client Q&A alignment:** Will's reply to item 2 says “Students can tick”: students may tick student-audience shared tasks, as the rule below states. The quoted Q&A approves feature behaviour, not the order of TK4 PR merges.

The feature comprises three primary interfaces:

1. **Admin Plan Builder (`/admin/plan`)**: Create, edit and order stages and tasks. Tasks include instructions, an optional resource link, an optional due date, an audience and an individual/shared completion setting.
2. **Group Plan Section (`/groups/:id/plan`)**: Display tasks under stage headings, with introductions, instructions, resource links, due dates, permitted checkboxes and a stage summary such as “Your view: 2/3 tasks complete”.
3. **Admin Progress Screen (`/admin/plan/progress`)**: Display a group-by-task matrix with completed/total values, ordered by stage, with a group-name filter.

**Agreed behaviour:**

- Eligible groups are non-deleted groups with `Groups.year == current_cohort()` (the active deadline's year, otherwise the current Django-local year). Waiting Area groups are included.
- Audiences are students, mentors or supervisors, matched to active **group membership roles**, rather than platform roles. Members see their audience's tasks; admins see all tasks. Anyone allowed to complete shared tasks also sees all shared tasks.
- **Individual tasks:** each audience member ticks their own checkbox. Nobody, including an admin, completes another person's individual task.
- **Shared tasks:** one tick completes the task for the group. An admin, the active group mentor or a supervisor linked to a student in the group may tick it. Students may also tick student-audience shared tasks, but not mentor- or supervisor-audience ones.
- Individual progress belongs to the person and group: leavers stop counting, late joiners see existing tasks, replacement mentors start unticked and returners recover their ticks. Shared ticks remain when membership changes.
- Suspended and deactivated accounts still count in individual progress totals while their group membership remains active.
- All groups share one template. Changes appear on reload. Audience/mode lock while a non-deleted current-year group has a completion record, even if unticked; other fields stay editable. Previous-year and soft-deleted-group records do not lock settings; the returning-group checklist below protects their reuse.
- Due dates are fixed dates with no per-group extensions. Editing an existing task's date updates it for all current-year groups on their next load, including during the current cohort.
- Existing per-user tasks from the old role-assignment approach stay untouched: do not delete, convert or migrate their task/completion data as part of group plans. Coordinate the same requirement with the separate TK4 owner.
- Stages do not block later tasks. Stage summaries count visible task checkboxes, excluding hidden personal progress.

**Scope:** 28 provisional story points across three people. TK4 remains separate. Group-specific plans/goals, relative dates, reminders, task dependencies, file uploads, yearly versions, historical reporting and a task restore screen are excluded. Plan tasks do not join dashboard task counts.

---

## Architectural Alignment & Reused Infrastructure

| Area | Approach | Reused Existing Code / Endpoints |
|---|---|---|
| **Plan Storage** | New `PlanStage`, `PlanTask` and `PlanTaskCompletion` models in `backend/apps/plans/models.py` | Existing `Task` cannot store per-person completion within a group; keep its behaviour unchanged |
| **Group Eligibility** | One helper for current-year, non-deleted groups | `current_cohort()` in `apps/submissions/services.py`; same group rule as `_this_years_teams` |
| **Membership & Permissions** | Match group roles; compute request permissions once | `group_participant_qs`, `is_admin`, `_is_active_group_mentor`, `_supervises_any_in_group` |
| **Group Page Integration** | Extend the existing route-driven section switcher | `GroupSubmissionSection.vue`, `GroupDetailPage.vue` and the Finalist request/watch pattern |
| **Admin UI** | Table, stage/task form sheets and confirmation dialogs | `AppDataTable.vue`, `admin/FormSheet.vue`, `AppSelect.vue`, `ConfirmDialog.vue`, existing `AdminTasksPage.vue` patterns |
| **API Transport** | Admin envelope; plain member JSON; authenticated session/CSRF requests | `adminAPI.ts` for admin calls; `tasksAPI.ts` transport pattern for member calls |
| **Dates & Audit** | Date-only due dates; audited mutations | `utils/date.ts` helpers and `apps/audit/services.py::log_audit_event` |

Backend paths beginning with `apps/` are relative to `backend/`; frontend paths are relative to `frontend/src/`. New feature names are proposals. The [implementation reference](group-plans-implementation-reference.md) contains full field definitions, response shapes, validation and concurrency details.

---

## Backend Endpoints

Admin endpoints require authentication and `IsAdminScoped`, returning `{msg, data}`. Member endpoints require authentication and enforce group access, audience visibility and completion permissions.

| Method | Endpoint | Description | Permission |
|---|---|---|---|
| `GET` | `/api/v1/admin/plan-stage/` | List active stages, including empty ones, in plan order | `IsAdminScoped` |
| `POST` | `/api/v1/admin/plan-stage/` | Create a stage | `IsAdminScoped` |
| `PATCH` | `/api/v1/admin/plan-stage/<id>/` | Edit stage name, introduction or order | `IsAdminScoped` |
| `DELETE` | `/api/v1/admin/plan-stage/<id>/` | Soft-delete a stage with no live tasks | `IsAdminScoped` |
| `GET` | `/api/v1/admin/plan-task/` | Paginated task list with sorting and completion-lock flags | `IsAdminScoped` |
| `POST` | `/api/v1/admin/plan-task/` | Create a task in an active stage | `IsAdminScoped` |
| `GET` | `/api/v1/admin/plan-task/<id>/` | Retrieve a task for editing | `IsAdminScoped` |
| `PATCH` | `/api/v1/admin/plan-task/<id>/` | Edit a task, respecting audience/mode locks | `IsAdminScoped` |
| `DELETE` | `/api/v1/admin/plan-task/<id>/` | Soft-delete a task; retain its completion records | `IsAdminScoped` |
| `GET` | `/api/v1/admin/plan-task/progress/` | Current-year group progress matrix | `IsAdminScoped` |
| `GET` | `/api/v1/plans/groups/<group_id>/tasks/` | Visible stages/tasks, completion and `can_toggle` | Group access |
| `POST` | `/api/v1/plans/groups/<group_id>/tasks/<task_id>/check/` | Set completion, or flip when the body is empty; return the updated item | Task completion permission |

Member lists return `{year, stages, items}`; authorised previous-year groups return empty arrays. Hidden groups/tasks return 404, denied ticks 403 and invalid input 400. Frontend ticks send `{completed: true|false}`; see the reference for full responses.

---

## Balanced Work Breakdown (3 Team Members)

| Person | Area | Stories | Provisional SP |
|---|---|---|---|
| **Person 1** | Admin Builder, Stage/Task APIs & Navigation | GP2 | 8 |
| **Person 2** | Data Models, Visibility & Admin Reporting | GP1 + GP5 | 10 |
| **Person 3** | Member API & Group Plan Section | GP3 + GP4 | 10 |

```text
                    PERSON 2: Data Foundation (GP1)
                  Models, migration, visibility helpers
                              /          \
                             v            v
       PERSON 1: Admin Builder       PERSON 3: Member Experience
       Stage/task APIs and forms     Member API and group Plan section
       Navigation and admin client   Checkboxes and stage summaries

       PERSON 2 builds Admin Reporting (GP5) using test data in parallel.
       Final check: Person 1 creates -> Person 3 ticks -> Person 2 verifies.
```

Points describe effort, not elapsed time. Re-estimate after contract agreement and allow for integration, migrations and demo preparation.

---

## Detailed Task Lists per Member

### Person 1: Admin Builder, Stage/Task APIs & Navigation (GP2)

1. **Stage and Task Services (`backend/apps/admin/services/plan_stage.py` and `plan_task.py`)**:
   - Implement stage list/create/update/soft-delete and task list/detail/create/update/soft-delete.
   - Validate names, audiences, modes, date-only dates, order values and resource URL/label pairs, including partial edits.
   - Return `has_completions` using the same current-year record check as backend field locks. Reject audience/mode changes once locked; allow moving tasks without changing their IDs.
   - Reject deletion of a stage containing live tasks and task writes to deleted stages. Audit all mutations with before/after values, including audience/mode.
2. **Admin API Views & URLs (`backend/apps/admin/views.py` and `urls.py`)**:
   - Add the stage/task endpoints above with authentication and `IsAdminScoped`.
   - Return 400 for validation errors, including PATCH failures.
   - Coordinate with Person 3 on task-row locks for edits/ticks and stage locks for deletion/moves; use the protocol in the implementation reference.
3. **TypeScript API Client (`src/utils/adminAPI.ts`)**:
   - Add proposed types `AdminPlanStage`, `AdminPlanTask`, list responses and create/update payloads.
   - Add typed functions to list/create/update/delete stages and list/get/create/update/delete tasks through `adminRequest`.
   - Integrate Person 2's progress types and fetch function in this shared file.
4. **Admin Builder Page & Forms (`src/views/admin/AdminPlanTasksPage.vue`, `src/components/admin/plans/`)**:
   - Create the builder page plus proposed `AdminPlanStageFormSheet.vue` and `AdminPlanTaskFormSheet.vue` using `FormSheet`.
   - Manage stage name, introduction and numeric position. Show an empty-state prompt to create a stage before adding a task.
   - Task form: stage, name, instructions, resource link/label, due date, audience, completion mode and numeric position. Use `AppSelect` for stage/audience and radios for individual/shared completion.
   - Show locked-field hints, deletion confirmations and validation errors. Add “View progress”. Numeric ordering is sufficient; no drag-and-drop is required.
5. **Routing, Sidebar & Admin Operating Checklist**:
   - Add `/admin/plan` and `/admin/plan/progress` with `requiresAdmin` metadata; integrate Person 3's `group-plan` route entry.
   - Add one Plan link to `App.vue`'s admin `sidebarSections` array, highlighted on both admin routes.
   - Document the returning-group rule: before restoring an old group/cohort, check audit history. If audience/mode changed while excluded, or compatibility cannot be established, soft-delete the affected task and create a replacement first. The new task starts unticked for every group. This is a manual admin rule, not automatic restoration blocking.
6. **Testing & Release Coordination**:
   - Service/API tests for validation, field locks, stage protection, soft deletion, response codes and auditing; component tests for forms, stage management and navigation.
   - Coordinate the draft PR and release checklist; arrange the plans migration with the deployment owner. TK4 fixes, merging and release remain outside this workload.

---

### Person 2: Data Foundation, Visibility & Admin Reporting (GP1 + GP5)

1. **Database Models & Migration (`backend/apps/plans/`)**:
   - `PlanStage`: name, introduction (`description`), position, soft-delete and timestamps.
   - `PlanTask`: required protected stage FK, position, name, instructions, optional resource URL/label, nullable date-only due date, audience, completion mode, creator, soft-delete and timestamps.
   - `PlanTaskCompletion`: task, group, nullable user, completed flag and update timestamp. A null user represents the shared group record.
   - Enforce unique `(task, group, user)` records when user is present and unique `(task, group)` records when null. Group/user/task completion FKs cascade on hard deletion.
   - Generate the initial migration against the implementation baseline, independent of TK4. Register models read-only in Django admin; add the app to settings and mount `/api/v1/plans/` in `config/urls.py`.
2. **Eligibility and Membership Helpers (`backend/apps/plans/visibility.py`)**:
   - Implement `current_plan_groups(year)`, `group_sees_plan(group, year)` and `active_audience_memberships(group_ids)`.
   - Read `current_cohort()` once per request. Include Waiting Area groups and active memberships regardless of suspended/deactivated account status.
   - Define active task reads to exclude deleted tasks and stages. Order stages/tasks by position then ID.
   - Share tested models, migration and helpers early, before completing seed data, so Persons 1 and 3 can start their backends.
3. **Demo Seed Data (`backend/apps/admin/management/commands/seed_dummy_data.py`)**:
   - Add two or three stages and tasks covering every audience, both modes, partial completions and past/future/no dates. Prefix stage/task names with `SEED_PREFIX`.
   - Delete seed tasks before protected seed stages during cleanup, before seed groups/users. Refuse stage cleanup if a non-seed task references it.
   - Keep the local demo group's year aligned with the active cohort; do not alter a real deadline for seed visibility.
4. **Progress Service & Endpoint (`backend/apps/admin/services/plan_progress.py`)**:
   - Implement `get_plan_progress` with grouped completion counts and active audience sizes, without queries per matrix cell.
   - Individual cells count completed current audience members / active audience members. Empty audiences show `0/0`; shared tasks always show `0/1` or `1/1`.
   - Exclude leavers, deleted groups/tasks/stages and previous-year groups. Sort groups using `group_name_sort_key()`, then ID; sort task columns in stage/task order.
   - Supply `AdminPlanProgressView`, its route, `AdminPlanProgress` type and `fetchAdminPlanProgress` to Person 1 for shared-file integration.
5. **Progress Page (`src/views/admin/AdminPlanProgressPage.vue`)**:
   - Build an `AppDataTable` matrix from response tasks/groups, with stage/task column headings, current year, group-name filter and empty states.
   - Render raw counts without dividing by zero. Check the matrix with the expected group/task volume; stable query count alone does not guarantee a small response.
6. **Testing**:
   - Model constraints, cohort visibility, membership totals, seed cleanup, progress counts and bounded query counts; component tests for matrix columns, filtering and empty states.
   - Apply the migration locally with migrations enabled. Progress tests can create completion records directly, without waiting for Person 3's API.

---

### Person 3: Member API & Group Plan Section (GP3 + GP4)

1. **Plan Permissions (`backend/apps/plans/permissions.py`)**:
   - Compute admin status, active group membership role and shared-task completion permission once per request using existing RBAC/mentor/supervisor helpers.
   - Admins see all active tasks; other viewers see their group-role audience plus all shared tasks they may complete. A supervisor linked only through a student profile may complete shared tasks but needs a group supervisor membership for supervisor individual tasks.
   - Implement query-free `can_tick_plan_task`; never permit another person's individual tick. Leave ordinary task permissions unchanged and document private helper imports.
2. **Member Views & Serializers (`backend/apps/plans/views.py`, `serializers.py`, `urls.py`)**:
   - Implement the list and completion endpoints, with prefetched viewer/shared records for the selected group and stage joins.
   - Return `completed: null` for individual tasks viewed outside the viewer's audience, and server-computed `can_toggle` for each item.
   - Validate actual JSON booleans; never accept a supplied user ID. Apply task-row locks and audit changed completion state within the mutation transaction. An untick with no record creates nothing; ticking then unticking retains the record.
3. **TypeScript Member API Client (`src/utils/plansAPI.ts`)**:
   - Add `PlanStage`, `GroupPlanTask` and `GroupPlanList` types plus `listGroupPlanTasks` and `toggleGroupPlanTask` functions.
   - Follow `tasksAPI.ts` session, CSRF, headers and error handling, targeting `/api/v1/plans/`. Do not use the admin request helper for member calls.
4. **Group Plan Component (`src/components/plans/GroupPlanSection.vue`)**:
   - Render stage headings/introductions, task instructions, labelled resource links, due dates and shared-task tags. Open links safely and render instructions as plain text.
   - Enable checkboxes only with `can_toggle`; show “Each person ticks their own” when completion is null. Send the desired boolean, disable while saving, and update only after success.
   - Calculate stage summaries from visible boolean completion values, excluding nulls; hide zero-denominator summaries. Only false completion can be overdue.
   - Format date-only values with `formatShortDate(value, 'UTC')` and compare today using the configured viewer time zone.
5. **Group Page Integration (`GroupSubmissionSection.vue`, `GroupDetailPage.vue`)**:
   - Fetch `{year, stages, items}` when the group changes, pass stages/items to the child and display the Plan tab only when tasks exist.
   - Reset/key state by group ID and ignore stale requests. Keep all stages accessible without prerequisites; reload on later visits to show admin changes.
   - Add the unique `group-plan` route through Person 1 and add it to `SECTION_ROUTES`. Empty/inaccessible plans fall back to Tasks and Chat; transient errors offer retry.
6. **Testing**:
   - Backend tests for role visibility, own-record completion, denied requests, audit records, membership changes and fixed list query counts.
   - Component tests for stage summaries, checkboxes, dates, links, errors, stale responses and group changes. Update section-switcher route fixtures/API mocks and rerun `GroupDetailPage.spec.ts`.

---

## Dependencies between People

**Real-data handover: Person 2's models -> Persons 1 and 3's features -> Person 2's reporting verification.** Person 2 can build reporting with test data while the other two build their features; they do not need to wait to start GP5.

- **Person 2's GP1 models block both other backends**: Persons 1 and 3 need the stage/task/completion schema and eligibility helpers. Share these first; seed data can follow.
- **Persons 1 and 3 can start frontend work immediately against agreed mocks**: agree field values, stage ordering and responses first. Screens can progress while GP1 is built, but cannot complete real integration without it.
- **Person 3's completion API is needed for final reporting verification**: Person 2 can build GP5 using direct completion fixtures, then verify real group-page ticks once GP3 is available. Reporting does not depend on GP2 to calculate counts.
- **Person 1 coordinates shared admin/navigation files**: owns integration in admin `views.py`/`urls.py`, `adminAPI.ts` and frontend `routes.ts`; Persons 2 and 3 supply their additions and test them. Person 2 creates the initially empty plans URL module; Person 3 owns its routes afterwards.
- **Final testing together**: Person 1 creates a task inside a stage using the admin builder, Person 3 ticks it from the group page, and Person 2 checks that reporting shows the correct progress. Also check what happens when someone joins/leaves a group, a task moves to another stage, or the active competition year changes. Connect and test parts as they become available; this is the final complete-feature check.
- **GP is not blocked by TK4**: the GP epic has no technical dependency on TK4. Its models, migration, endpoints and existing admin UI patterns can be built and tested independently. Start GP while TK4 is updated separately; do not add a TK4 blocker to the GP epic. Avoid importing unmerged TK4-specific components. When TK4 reaches `main`, merge the updated `main` into the GP branch, resolve any overlapping admin/navigation edits and rerun the affected checks.

---

## Verification Plan

### Automated Tests

- **Backend (`backend/tests/apps/plans/` and `backend/tests/apps/admin/`)**: constraints, stage/task CRUD, resource/date validation, completion permissions, locks, soft deletion, audits, cohort rules and accurate counts including suspended/deactivated members.
- **PostgreSQL transaction tests**: first-tick/edit races, simultaneous shared ticks and stage delete/move races. SQLite CI cannot verify the row-lock protocol.
- **Frontend (Vitest)**: admin forms and locked fields, group tab routing, links, checkbox states, stage summaries, request errors, stale responses, matrix filtering and `0/0` rendering.
- **Regression checks**: normal/shifted-clock backend tests; section-switcher tests with new mocks/routes; `GroupDetailPage.spec.ts`. Use `timezone.now()`/`timezone.localdate()` for date-sensitive backend tests.

Run focused tests while developing. Before review, run backend tests with `config.settings_test`, migration generation checks with migrations enabled, local PostgreSQL migration/concurrency checks, and frontend type checking, unit tests and build. Exact commands and full contracts remain in the [implementation reference](group-plans-implementation-reference.md).

### Manual Verification

1. Open `/admin/plan`; create Getting Started and Developing Your Project stages, with numeric order and introductions.
2. Add an individual student task with instructions, a guide link and due date, plus a shared student-audience task.
3. Open a current-year group's Plan section; verify stage/task order, guidance, dates and links. Verify later stages remain accessible.
4. As a student, tick the individual task and the shared student-audience task. Verify other students' individual ticks remain incomplete and the shared tick shows for the whole group.
5. As the group's mentor/supervisor, tick the shared task. Verify the group sees it complete and stage summaries update appropriately.
6. Open admin progress; verify individual completed/total counts, shared `0/1`/`1/1` cells and group filtering. Verify suspended accounts with active memberships still count.
7. Edit a ticked task; verify audience/mode are locked but names, guidance and dates remain editable. Move it to another stage and confirm ticks remain. Reject deletion of a stage with live tasks.
   Verify an edited due date appears in two current-year groups after reload, and existing legacy per-user task records are unchanged.
8. Check a late joiner, a leaver and mentor replacement. Verify individual progress follows the agreed membership rules and shared ticks remain.
9. Move the active deadline to next year in the local demo, confirm old groups disappear and records remain, then move it back without changing task audience/mode.
10. Walk through the returning-group checklist for changed settings: replace affected tasks before restoring the old cohort. Verify replacement tasks inherit no old ticks; deletion hides tasks without deleting saved completion records.

Person 1 coordinates the draft PR/release and admin checklist; Person 2 verifies migrations/seeds; Person 3 verifies member-role scenarios. Use `feat/group-plans` as the shared integration branch, created from updated `main`; TK4 does not need to be merged first. Each person works on a separate branch from it. Person 2 starts on `feat/group-plans-foundation` and opens a PR into `feat/group-plans` for the tested models/helpers first. Persons 1 and 3 merge that updated shared branch into their own branches, then connect their backends; Person 2 continues with reporting. Open an early draft PR from the shared branch into `main` for CI. Individual PRs into the shared branch need local checks because the inspected CI targets `main`. Keep the TK4 and GP PRs separate. Either may merge first once its own checks and review are complete; whoever merges second brings in `main`, resolves overlaps and reruns affected checks. Verify locally: frontend previews use the production API. Arrange the plans migration before users access the screens; reversing it deletes plan tables/data.

**Review basis:** code inspection on 20 October 2026 covered checkout `2cbc9b95` and locally available `origin/main` at `cb42fafc`, without fetching updates. `AppSelect` and registration placement exist on that `origin/main`, not the checkout. Proposed plan code is not implemented or runtime-tested. The [older investigation](group-plans-technical-plan-reference-2-people.md) is historical; its combined TK4 release instructions are superseded.


