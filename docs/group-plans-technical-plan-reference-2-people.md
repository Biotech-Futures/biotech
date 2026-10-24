# Goal
Let admins define one shared plan of tasks that every current-year group sees on its group page. The feature is modelled on Chronus connection plans and built as an extension of TK4's role-based tasks.

Each plan task has two settings:
- an **audience**: the students, the mentor or the supervisors of a group
- a **completion mode**: per-person (each person in the audience ticks their own copy) or per-group (one tick completes it for the whole group, given by the group's mentor, a supervisor of a member, or an admin)

Admins see progress as completed/total per task per group.

Most of the plumbing already exists. TK4 already proves the "one definition row, read live, completion rows created lazily" pattern; the group page already has a route-driven section switcher that a Plan section can join; and "this year's teams" is already a single, well-used query. The work is therefore one small new backend app, a TK4 merge with two fixes as pre-work, and copies of TK4's admin and completion patterns, not a new subsystem. `adminweb/` is untouched.

Names of new files, models, endpoints and components in this plan are proposals. Existing names have been checked against `origin/main` at `cb42fafc` and `feat/tk4-role-based-tasks` at `1a0e0ca7` on 20 October 2026.

**Terms used throughout:**
- **Current-year group**: a group that is not soft-deleted and whose `Groups.year` equals `current_cohort()`. Only these groups see the plan
- **Tick right**: being allowed to tick per-group tasks in a group (an admin, the group's active mentor, or a supervisor of a member)
- **Viewer facts**: the three facts about the person making a request (`is_admin`, `membership_role`, `holds_tick_right`), computed once per request and used by every permission check

# Open items
This section records the defaults the plan is built on, the edge cases and limits of the design, and the risks to watch. None of it blocks the work.

- **Defaults the plan is built on.**
  - **Ticking per-group tasks.** Students do not tick per-group tasks. A student ticks only their own per-person rows; per-group tasks are ticked by the group's mentor, a supervisor of a member, or an admin. Should students later be permitted to tick per-group tasks, the change is confined to `can_tick_plan_task` (GP3, `apps/plans/permissions.py`), which would additionally accept an active student member of the group. `_can_toggle`, `CanToggleTask` and `GroupTaskToggleTests` remain unchanged in either case, and the Vue side requires no change because the list endpoint already returns `can_toggle` per item. A per-group tick would then be shared among several students, so one student could reverse another's. The toggle's audit entry already records who ticked; a who-ticked user column and a tick time may be added to `PlanTaskCompletion` later as an additive migration should the group page need to display them
  - **Registration Waiting Area.** Groups in the registration Waiting Area see the plan. The rule, and the single filter that would exclude these groups, are set out in "Who sees the plan, and the current year"
  - **TK4 role tasks.** The platform-wide TK4 role tasks ship alongside plans, so GP0 is required. Were they withdrawn, GP0 would be dropped and `feat/group-plans` would be created from `main` without merging TK4
- **"Current year" follows the submission deadline.** The plan reads the year through `current_cohort()` (`apps/submissions/services.py`), so these edge cases come with it. None is specific to plans; submissions, grading and system emails behave the same way today:
  - Moving the active deadline into January (for example to 15 January 2027) makes `current_cohort()` return 2027, and every 2026 group loses the plan at that moment
  - Setting next year's deadline early (in November 2026 for 2027) rolls the plan over when it is saved: `set_submission_deadline` (`apps/management/services/deadline.py`) always inserts a new active row, `active_deadline` takes the newest, and nothing checks its year
  - With no active deadline, `current_cohort()` falls back to today's UTC year, so the plan rolls over at midnight UTC on 1 January (11am in Sydney)
  - `current_cohort()` reads the year in UTC (`TIME_ZONE = "UTC"`): a deadline at 09:00 Sydney time on 1 January is still 31 December in UTC and counts as the earlier year
  - `Groups.year` and `current_cohort()` are two different clocks. `year` is set once from `default_group_year()` (the UTC calendar year at creation) and never written again, so a group created in December for next year's challenge gets this year's `year` and never sees next year's plan
  - Restoring a deleted group keeps its old `year`, so a restored 2025 group does not get the 2026 plan
- **Limits of this version.**
  - **Plan edits are not versioned across years.** There is one shared template. If it is reused next year, editing, adding or soft-deleting tasks for 2027 also changes what 2026's kept completion rows appear to belong to (2026 rows would show 2027's names and dates if anyone looked them up). Nothing in this plan shows previous years, so this stays invisible until someone wants history. Because the lock rule only counts current-year groups, last year's rows also stop protecting a task's audience and mode once the year rolls over
  - **Active member means an active membership** (`left_at` null), whatever the person's login status. Filtering out suspended or deactivated accounts from progress totals is a possible later refinement
  - **Mentors and supervisors don't see students' per-person progress on the group page**, only their own tasks and per-group tasks. The admin progress view covers the client's ask; a read-only "4/5 students done" line on the group page is a possible follow-up (the GP5 queries already produce it)
  - **No restore for soft-deleted plan tasks**, the same as TK4's role tasks. The Django admin registration (GP1) lets a developer clear `deleted_at` if needed
  - **Relative due dates are out of scope.** If they come back, `ChallengeStart` (`apps/management/models.py`, a per-year `starts_on`, read through `ChallengeStart.for_year(current_cohort())`) is the natural anchor
- **Outside-team conflict risk.** `origin/feature/group-meetings-frontend` (not merged, last commit `2e310374`) changes `frontend/src/router/routes.ts` (it adds `/groups/:id/meetings` routes in the same block as `/groups/:id/plan`), `frontend/src/views/GroupDetailPage.vue`, `frontend/src/App.vue`, `frontend/src/views/DashboardPage.vue`, `frontend/src/utils/adminAPI.ts`, `frontend/src/stores/auth.ts`, `backend/apps/admin/views.py`, `backend/config/settings.py` and `backend/config/urls.py`. It also adds two new apps, `meetings` and `tickets`, to the same `INSTALLED_APPS` and URL lists the plan edits. `DashboardPage.vue` also overlaps GP0. Whoever merges second resolves; the plan's edits to each of these files are a few lines
- **Assumptions to state at the client demo:**
  - The plan appears as its own Plan section on the group page; the dashboard, including TK4's "My Role Tasks" section and its reminder banner, is unchanged and does not count plan tasks
  - "Current year" means the year of the active submission deadline, so the plan follows the deadline (edge cases above)
  - Students tick only their own per-person tasks; per-group tasks are ticked by the group's mentor, a supervisor of a member, or an admin
  - Progress counts only active members holding the task's audience role; leavers' ticks are kept but not counted; a new mentor starts unticked
  - Changing a task's audience or completion mode is blocked once anyone in a current-year group has acted on it; delete it and create a new one instead
  - Groups in the registration Waiting Area see the plan

# What currently exists
There are four kinds of task in the codebase today (one of them only on an unmerged branch), and the plan adds a fifth. They look alike in the UI but store completion in completely different ways, and that difference drives the design.

| Kind | Defined as | Who it applies to | Completion stored as | Who can tick | Created via | Shown via |
|---|---|---|---|---|---|---|
| Group task | `Task` with `task_type="group"` (`apps/tasks/models.py`) | One group (`Task.group`) | `Task.completed`, one shared flag for the whole group | Admin, the group's active mentor, a supervisor of any member (`_can_toggle` in `apps/tasks/permissions.py`). Students get 403 (`GroupTaskToggleTests.test_student_cannot_toggle_group_task`, `tests/apps/tasks/test_task_api.py`) | `TaskListCreateView` (`apps/tasks/views.py`), admin `create_admin_task` (`apps/admin/services/task.py`) | `GroupDetailPage.vue` `loadTasks` |
| Individual task | `Task` with `task_type="individual"` | One user (`Task.assigned_user`); the `task_type_target_consistency` check constraint forces `group` to be null | `Task.completed` | The assignee, plus mentor/supervisor/admin rules by `creator_role` (`_can_toggle`) | Same as above | Same as above |
| Old fanned-out individual task | Ordinary individual `Task` rows, one per role holder | Whoever held the role on the day | `Task.completed` per row | As individual tasks | `_create_role_fanout_tasks` (`apps/admin/services/task.py`), still on `main`; TK4 removes it | As individual tasks. Left untouched by this plan |
| TK4 role task | `RoleTask` + `RoleTaskCompletion` (`apps/tasks/models.py`, **only on `feat/tk4-role-based-tasks`**) | Every current and future holder of a platform role, by a live join on `active_role_ids` (`apps/common/rbac.py`, reading `RoleAssignmentHistory`) | One `RoleTaskCompletion` per (role task, user), created lazily on first tick | The holder, their own row only (`RoleTaskToggleView`) | `create_admin_role_task` (`apps/admin/services/role_task.py`) | Dashboard "My Role Tasks" (`DashboardPage.vue` `loadRoleTasks`) |
| Plan task (new) | `PlanTask` + `PlanTaskCompletion` (`apps/plans/models.py`) | Every current-year group, by a live rule (`Groups.year == current_cohort()`), filtered by `audience_role` matched on `GroupMembership.membership_role` | Per-person: one row per (task, group, user). Per-group: one row per (task, group) | Per-person: the person, own row only. Per-group: the group's mentor, a supervisor of a member, an admin | `create_admin_plan_task` (`apps/admin/services/plan_task.py`) | `GroupPlanSection.vue` on the group page |

The rest of this section covers what the plan builds on, area by area. Each paragraph ends with what it means for the plan.

**TK4 is not merged.** `feat/tk4-role-based-tasks` (last commit `1a0e0ca7`) is 647 commits behind `origin/main` at `cb42fafc` and is not an ancestor of it. A dry merge (`git merge-tree --write-tree origin/main origin/feat/tk4-role-based-tasks`) conflicts in five files:
- `frontend/src/App.vue`: `main` builds the admin sidebar from a `links` array inside the `sidebarSections` computed, so TK4's hand-written `<li class="sidebar-subitem">` for Role Tasks has to become a `{ label: 'Role Tasks', to: '/admin/role-tasks', ... }` entry in that array
- `frontend/src/components/admin/tasks/AdminTaskFormSheet.vue`: TK4 deletes the role fan-out picker, and `main` (commit `82304793`) replaced that same `<select>` with `AppSelect` (`frontend/src/components/AppSelect.vue`)
- `frontend/src/router/routes.ts`, `frontend/src/views/admin/AdminTasksPage.vue` and `frontend/src/views/admin/__tests__/AdminTasksPage.spec.ts`

Everything else auto-merges, including `apps/admin/services/task.py` (where `main` added a `search` parameter to `list_admin_tasks`) and `DashboardPage.vue`. Auto-merged is not the same as working, though. `main` removed `formatDateAU` (commit `9fb56d23`) and `formatAnnouncementDateAU` (commit `0ebdedc2`) from `frontend/src/utils/date.ts`, yet in the dry-merged tree TK4's `AdminRoleTasksPage.vue` still imports `formatDateAU` (for its `formatDueDate`), and TK4's "My Role Tasks" block in `DashboardPage.vue` still calls `formatAnnouncementDateAU` while the merged file imports `formatDayMonth`. Git reports no conflict, but the merged frontend will not type-check until both are switched to a current `utils/date.ts` helper (`formatShortDate` for the admin table, `formatDayMonth` for the dashboard). The migration side is clean: TK4's `tasks/0012_roletask_roletaskcompletion_and_more` still applies, because `tasks` on `main` ends at `0011_remove_task_track` and its other dependency, `resources/0010_remove_resourceaudience_resource_audience_requires_role_or_track_and_more`, exists. For the plan: GP0 resolves the five conflicts and the two silent breaks before plan work fills the shared branch.

**Audit logging.** The member-facing Task views (`TaskListCreateView.create`, `TaskRetrieveUpdateDestroyView.update`/`destroy`, `TaskRestoreView.post`, `TaskToggleView.post`, `TaskBulkToggleView.post`, `TaskStatusUpdateView.post`) all call `log_audit_event` from `apps/audit/services.py`. The admin Task service (`create_admin_task`, `update_admin_task`, `delete_admin_task`) does not log. For the plan: the admin-side precedent to follow is `apps/admin/services/group.py`, where `update_group` and `delete_group` call `log_audit_event` inside the service.

**Groups and the year.** Groups are created in eight places:
- `GroupViewSet.perform_create` and `GroupViewSet.bulk_create` (`apps/groups/views.py`)
- `create_group` (`apps/admin/services/group.py`)
- `confirm_student_assignments` (`apps/admin/services/match.py`)
- `_apply_co_registration` (`apps/admin/services/user.py`)
- `save_group` (`apps/users/registration_intake.py`), which calls `Groups.create_with_code` or `Groups.create_auto_named` and then `Groups.mark_formed`
- `SupervisedGroupsView.post` (`apps/users/supervisor_group_views.py`)
- `_create_groups` (`seed_dummy_data.py`)

None of the eight passes `year`, so every group gets `default_group_year()`, and nothing writes `year` afterwards (it is read-only in `GroupSerializer`). `Groups` itself is changing actively: `code` arrived in `0014_group_codes`, `formed_by`/`created_by` in `0015_groups_formed_by` and `placed_at` in `0016_groups_placed_at`, all in October 2026. "Current year" also already has one established meaning: `_this_years_teams` in `apps/admin/services/system_email_recipients.py` is `Groups.objects.filter(deleted_at__isnull=True, year=_this_year())`, where `_this_year()` returns `current_cohort()`, and `current_cohort()` is called 51 times across 30 files under `backend/apps`. For the plan: every creation path already produces a group the year rule can see, so there is no creation hook and no new column on `Groups`, and the plan's helper is exactly the `_this_years_teams` query.

**Group membership.** `GroupMembership` (`apps/groups/models/group_members.py`) holds `membership_role` (`mentor`, `student`, `supervisor`), `joined_at` and `left_at`. The `unique_active_group_membership` constraint allows one active row per (group, user), so a person has exactly one role in a given group at a time.

Membership rows are not a reliable history. `confirm_student_assignments` deletes every membership (in every group) of the students it reassigns, and admin `remove_group_member` calls `membership.delete()`. Admin `delete_group` hard-deletes the group itself (cascading), while `GroupViewSet.destroy` soft-deletes. Mentor replacement (`assign_mentor_to_group(..., replace_existing=True)` in `apps/groups/services.py`, also the mentor-match and supervisor flows) sets `left_at` on the old row and creates a new one. Supervisor rows are maintained by `sync_supervisor_memberships`, but a supervisor's task rights come from `StudentProfile.supervisor_id`, not from that row (`_supervises_any_in_group` in `apps/tasks/permissions.py`). For the plan: completion rows key on (task, group, user) and never on a membership row, and progress joins to active memberships at read time.

**Task completion and permissions.** `Task.completed` is one shared boolean, and `task_type_target_consistency` forbids putting a user on a group task, so per-person completion on a group-scoped task cannot be stored in `Task` at all.

`CanToggleTask` (wrapping `_can_toggle`) gates not only `TaskToggleView` but also `TaskStatusUpdateView` and, per row, `TaskBulkToggleView`, so widening it for plan purposes would widen all three for every ordinary group task. The plan instead reuses the two checks `_can_toggle` is built from, `_is_active_group_mentor(user, group_id)` and `_supervises_any_in_group(user, group_id)`, without touching `_can_toggle` itself. Both are module-private (leading underscore) in `apps/tasks/permissions.py`; importing them from `apps/plans` is acceptable but should be noted in a comment, and must not change their behaviour.

Existing responses to someone who may not act are mixed: task detail is filtered through `visible_tasks` and so returns 404, `TaskToggleView` uses an unfiltered queryset and returns 403, and `GroupViewSet` lets any logged-in user retrieve any active group. For the plan: completion lives in new tables, ticks go through a new endpoint, and the 404 choice in "Who sees the plan" is made explicitly rather than inherited.

**The group page.** `GroupDetailPage.vue` is 10,644 lines. It wraps its body in `GroupSubmissionSection` (`frontend/src/components/submission/GroupSubmissionSection.vue`, 209 lines), a route-driven section switcher. "Tasks and Chat" is the default slot; Submission, Finalist and Results are separate routes (`group-submission`, `group-finalist`, `group-results` in `routes.ts`, all pointing at `GroupDetailPage.vue`) with their own pills. The Finalist pill is the exact precedent for Plan: a `watch` on `groupId` calls `fetchFinalist`, and the pill shows only when the server answers. The whole switcher sits behind `canSeeSubmission`, which checks the viewer's platform role (`auth.isStudent || auth.isMentor || auth.isSupervisor || auth.isAdmin`, resolved from `current_role_name` in `frontend/src/stores/auth.ts`), not their membership in the group. `GroupDetailPage.vue`'s only involvement is its `SECTION_ROUTES` list, which switches the page into whole-page scrolling for a section. For the plan: the Plan section touches `GroupDetailPage.vue` by one array entry and lives in its own component.

**Dates.** `Task.due_date` and TK4's `RoleTask.due_date` are `DateTimeField`s with `USE_TZ = True` and `TIME_ZONE = "UTC"`. The admin forms send midnight UTC (`toDueDatePayload` in TK4's `AdminRoleTaskFormSheet.vue` and in `AdminTaskFormSheet.vue` builds `${value}T00:00:00Z`), while the group page sends the browser's local time converted to UTC (`fromDateTimeLocal` in `GroupDetailPage.vue`). For the plan: plan tasks avoid all of this with a `DateField`, and the API sends and receives `"YYYY-MM-DD"`. TK4's dates are not changed. On the frontend a date-only string must be formatted with `formatShortDate(value, 'UTC')` (`frontend/src/utils/date.ts`), because `new Date('2027-03-05')` is UTC midnight and formatting it in a negative-offset zone would show the day before; "today" for overdue comparison is `toTimeZoneDateKey(new Date(), getSetTimeZone())`.

**CI and migrations.**
- **Where tests live:** backend tests run as `coverage run manage.py test tests --settings=config.settings_test` (`.github/workflows/main_biotechbe.yml`), so new tests must live under `backend/tests/apps/...`; coverage must stay at 60% or more
- **Shifted clock:** the same suite runs twice more with `tests.clock.ShiftedClockRunner` (`TEST_CLOCK_SHIFT_DAYS: '400'`, and `TEST_CLOCK_AT: new-year`, which is 00:30 UTC on the next 1 January). The runner patches only `django.utils.timezone.datetime`, so `timezone.now()` and `timezone.localdate()` move while `datetime.date.today()` and `datetime.datetime.now()` do not. Tests must use `timezone.localdate()` and `timezone.now()`, never `date.today()`, and never hard-code a year
- **Migrations:** `config/settings_test.py` disables migrations (`_DisableMigrations`), CI has no `makemigrations --check`, and nothing in the repo runs `migrate` in production; it is run by hand
- **When CI runs:** both CI workflows that run tests (`main_biotechbe.yml` and `frontend-typecheck.yml`) run them only for pull requests into `main` and pushes to `main`. `frontend-static-web-app.yml` also builds and uploads an Azure Static Web Apps preview for every pull request into `main` that touches `frontend/**`, draft or not, with `VITE_API_BASE_URL: https://api.biotechfutures.org`, so a preview of unmerged frontend code talks to the production API

For the plan: the local checks and the early draft PR in "Branching and deployment" exist because of these gaps.

## What needs adding/changing

**Story index**: the detailed, file-by-file breakdown below is the actual build spec; this table is just orientation. SP are rough relative sizes. GP0 is pre-work and is not counted in the 21 SP total of GP1 to GP5. Locations are given by file, function, class or component name rather than line number, since line numbers drift as the code changes; search for the name before editing.

| Story | SP | In plain terms |
|---|---|---|
| GP0 | 5 (pre-work) | Bring TK4 up to date with `main` (five conflicted files, one of them restructured onto `AppSelect`, plus two removed date helpers that break the build without a conflict), fix the role-task tick so it sets `status` as well as `completed`, add audit logging to role-task create/update/delete/tick, and merge it into `feat/group-plans`. |
| GP1 | 3 | A new `plans` app with two tables (plan tasks, and completion rows keyed on task + group + user), one helper that decides which groups see the plan (`Groups.year == current_cohort()`), and demo seed data. No change to `Groups` or `Task`. |
| GP2 | 5 | The admin plan builder: list, create, edit and soft-delete plan tasks, each with a name, description, date-only due date, audience and completion mode. Audience and mode lock once anyone in a current-year group has acted on the task. Backend service and endpoints plus a new admin page, copied from TK4's Role Tasks page. |
| GP3 | 5 | The member API: list a group's plan tasks with the viewer's own tick (or the group's tick) and a server-computed `can_toggle`, and one tick endpoint enforcing who may tick what. This is where all the permission rules live. |
| GP4 | 3 | A Plan section on the group page: a new pill next to Submission, a new route, and a component listing the plan with checkboxes where the viewer may tick. Built after GP3 against the real endpoints, or against the contract's mocks if anything is pending. |
| GP5 | 5 | The admin progress view: completed/total per task per group for current-year groups, computed with a fixed number of queries, on a new admin page. |

**New backend files:**
- `backend/apps/plans/__init__.py` and `backend/apps/plans/apps.py` (GP1): a new app with `PlansConfig` (`name = "apps.plans"`). It is a separate app rather than more models in `apps/tasks` for two reasons: its first migration does not depend on TK4's `tasks/0012`, so GP1 can be built and tested before GP0 lands; and plan work never edits `apps/tasks/models.py`, `apps/tasks/urls.py` or `apps/tasks/serializers.py`, which GP0 is editing. No app, module, table, route or file name in this plan exists on `main` or any remote branch
- `backend/apps/plans/models.py` (GP1):
  - `PlanTask`: `name` (`CharField(255)`), `description` (`TextField(blank=True)`), `due_date` (`DateField(null=True, blank=True)`), `audience_role` (`CharField`, choices reusing `GroupMembership.MembershipRoleChoices`: `student`, `mentor`, `supervisor`), `completion_mode` (`CharField`, a new `CompletionMode` `TextChoices` with `per_person` and `per_group`, default `per_person`), `created_by` (FK to user, `SET_NULL`), `deleted_at`, `created_at`, `updated_at`. `db_table = "plan_task"`, with an index on `deleted_at`. A `PlanTaskQuerySet.active()` like `RoleTaskQuerySet.active()`, and `soft_delete()` like `RoleTask.soft_delete()`. No field default may call `current_cohort()`: a callable default that queries another model runs inside migrations and breaks them
  - `PlanTaskCompletion` fields: `task` (FK to `PlanTask`, `CASCADE`, `related_name="completions"`), `group` (FK to `groups.Groups`, `CASCADE`), `user` (FK to user, `CASCADE`, **nullable**: null means the per-group row), `completed` (`BooleanField(default=False)`), `updated_at` (`auto_now`). `db_table = "plan_task_completion"`, with indexes on (`task`, `group`) and `user`. There is no `status` field (plan tasks are done or not done, unlike TK4's `RoleTaskCompletion.status`), and who ticked is recorded by the toggle's audit entry, not on the row
  - `PlanTaskCompletion` constraints: two conditional unique constraints, `unique_plan_person_completion` on (`task`, `group`, `user`) where `user` is not null, and `unique_plan_group_completion` on (`task`, `group`) where `user` is null. Both become partial unique indexes (`CREATE UNIQUE INDEX ... WHERE "user_id" IS [NOT] NULL`) on SQLite and on PostgreSQL 16, and a duplicate raises `django.db.utils.IntegrityError` on both (wrapping `sqlite3.IntegrityError` or `psycopg.errors.UniqueViolation`); only the message text differs, so code and tests must not match on it. The database cannot check that `user` is null exactly when the task is per-group (that rule spans two tables); the service enforces it and the lock rule (GP2) keeps it true for current-year groups
  - `CASCADE` on `group` is deliberate: admin `delete_group` hard-deletes, and a gone group's ticks have nowhere to show. Soft-deleted groups keep their rows
- `backend/apps/plans/migrations/0001_initial.py` (GP1): creates both tables; depends only on `groups` and the user model, not on `tasks`
- `backend/apps/plans/admin.py` (GP1): registers both models in the Django admin, which is also the way to restore a soft-deleted plan task
- `backend/apps/plans/visibility.py` (GP1), the one place the "who sees the plan" rule lives:
  - `current_plan_groups(year)`: returns `Groups.objects.filter(deleted_at__isnull=True, year=year)`, the same query as `_this_years_teams`. Callers compute `year = current_cohort()` once per request and pass it in, so the deadline is read once. Everything else is built on this function
  - `group_sees_plan(group, year)`: `current_plan_groups(year).filter(pk=group.pk).exists()`, so the rule is written once
  - `active_audience_memberships(group_ids)`: active `GroupMembership` rows (`left_at` null) in those groups with `membership_role` in the three audience roles, whatever the account's login status. Used by GP3 (who is in the audience) and GP5 (totals)
- `backend/apps/plans/permissions.py` (GP3):
  - `viewer_facts(user, group)`: the viewer facts, computed once per request and passed to the serializer in its context. `is_admin` comes from `is_admin(user)`. `membership_role` is the viewer's active `membership_role` in this group, `""` for an active row with a blank role, or `None` with no active row, read through `group_participant_qs(user, group.id)` from `apps/common/rbac.py`. `holds_tick_right` is `is_admin`, or `_is_active_group_mentor(user, group.id)`, or `_supervises_any_in_group(user, group.id)`: the same three checks `_can_toggle` uses for group tasks, imported from `apps/tasks/permissions.py` and not modified
  - `can_view_group_plan(facts)`: `is_admin`, or an active membership (`membership_role is not None`), or `holds_tick_right` (which covers a supervisor linked to a member only through `StudentProfile`, with no membership row of their own). It does not check the year; the view does
  - `visible_plan_tasks(facts)`: active `PlanTask`s, all of them for an admin; otherwise tasks whose `audience_role` equals `membership_role`, plus per-group tasks of any audience when `holds_tick_right` is true (see "Audience, completion modes and who can tick"). Ordered `F("due_date").asc(nulls_last=True)`, then `id`, the rule TK4 settled on in commit `08341087`
  - `can_tick_plan_task(task, facts)`: a pure function, no queries. Per-person: `facts["membership_role"] == task.audience_role` (own row only; admins who are not in the audience cannot tick on someone's behalf). Per-group: `facts["holds_tick_right"]`; students never, even when the task's audience is students
- `backend/apps/plans/serializers.py` (GP3): `GroupPlanTaskSerializer`, a read-only `ModelSerializer` over `PlanTask` adding `completed` and `can_toggle` as `SerializerMethodField`s. `completed` reads the completion rows the view attaches (no query per row), following `RoleTaskMineSerializer`'s `_my_completion`; `can_toggle` calls `can_tick_plan_task(obj, self.context["facts"])`. For a per-person task where the viewer is not in the audience (an admin, or a tick-right holder seeing a per-group list), `completed` is `null`, so the UI shows "each person ticks their own" instead of an unticked box. The toggle body reuses `TaskToggleSerializer` (`apps/tasks/serializers.py`: `completed` optional; omitted means flip)
- `backend/apps/plans/views.py` (GP3):
  - `GroupPlanTaskListView` (`GET`) answers in this order: 404 when the group does not exist, is soft-deleted, or `can_view_group_plan(facts)` is false; then 200 with `{"year": year, "items": []}` when `group.year != year`; otherwise 200 with `visible_plan_tasks(facts)` and two `Prefetch`es on `completions` (the viewer's per-person rows for this group, and this group's per-group row), following TK4's `_with_my_completion`. The query count stays the same however many tasks there are
  - `GroupPlanTaskToggleView` (`POST`): 404 unless the group exists, is not soft-deleted, passes `can_view_group_plan`, is a current-year group, and the task is active and in `visible_plan_tasks(facts)`; 403 when `can_tick_plan_task(task, facts)` is false. Otherwise, inside `transaction.atomic()`, it finds the right row (per-person: `user=request.user`; per-group: `user=None`). An untick (`{"completed": false}`) on a task with no row returns the item unchanged and creates no row and no audit entry. Any other request uses `get_or_create`, sets `completed`, and calls `log_audit_event(actor=request.user, entity_type="plan_task", entity_id=task.id, action="toggle", before_state={"completed", "group_id", "completion_mode"}, after_state={"completed", "group_id", "completion_mode"})`, which is the record of who ticked. It returns the single item in the list shape
- `backend/apps/plans/urls.py` (GP1 creates it empty and wires it into `config/urls.py`; GP3 adds the two routes)
- `backend/apps/admin/services/plan_task.py` (GP2), modelled on TK4's `apps/admin/services/role_task.py`:
  - `list_admin_plan_tasks(requesting_user, page, limit, sort_by, sort_order)`: sort keys `name`, `audience`, `mode`, `due` (with `nulls_last`), `createdAt`. Each item carries `has_completions`, an `Exists` annotation over `PlanTaskCompletion` rows for that task whose group is in `current_plan_groups(year)`, so the form can lock fields without a query per row
  - `get_admin_plan_task_by_id`, `create_admin_plan_task`, `update_admin_plan_task`, `delete_admin_plan_task` (soft delete): all return TK4's `{"msg", "data"}` dicts, and each calls `log_audit_event` with `entity_type="plan_task"` and before/after state, following `update_group`/`delete_group` in `apps/admin/services/group.py`
  - `_validate_plan_task_input(input_data, existing=None)`: name required and at most 255 characters; `due_date` either null or a valid `"YYYY-MM-DD"` (a datetime string is rejected rather than truncated; optionally parsed with DRF's `serializers.DateField().run_validation(value)`, as `ChallengeStartView.put` in `apps/management/views/challenge_start.py` does); `audience_role` one of the three roles; `completion_mode` one of the two (default `per_person`). On update, it rejects a change to `audience_role` or `completion_mode` when the same current-year `Exists` check is true, with "This task has been ticked. Delete it and create a new one to change who it is for or how it is completed."
  - `_serialize_plan_task(plan_task)` (reads the annotated `has_completions`)
- `backend/apps/admin/services/plan_progress.py` (GP5): `get_plan_progress(requesting_user)`, described in "Progress, leavers and mentor changes"
- New backend tests (GP1, GP2, GP3, GP5):
  - `backend/tests/apps/plans/__init__.py` (GP1)
  - `backend/tests/apps/plans/test_plan_models.py` (GP1): both unique constraints (a second per-person row for the same task, group and user fails; a second per-group row fails; per-person rows for the same user in two groups both succeed; a per-person and a per-group row for the same task and group coexist; two users in the same group succeed). Each expected failure goes inside its own `transaction.atomic()`, because Postgres rejects every later statement in a transaction that has raised. Also `PlanTask.objects.active()`, and ordering with null due dates last
  - `backend/tests/apps/plans/test_plan_visibility.py` (GP1): `current_plan_groups(year)` includes this year's live groups and excludes soft-deleted and previous-year ones; with no `Deadline` the year is today's; with an active `Deadline` whose `closes_at` is next year, this year's groups drop out; `active_audience_memberships` skips left members and keeps every active one, including suspended accounts. Years come from `timezone.now()` and `current_cohort()`, never hard-coded, because of the shifted-clock runs
  - `backend/tests/apps/plans/test_plan_permissions.py` (GP3): `viewer_facts` for each viewer (student, mentor, supervisor via membership, supervisor via `StudentProfile` only, admin, non-member), then `can_view_group_plan`, `visible_plan_tasks` and `can_tick_plan_task` for each by task (per-person and per-group, each audience); students cannot tick per-group tasks; admins cannot tick someone's per-person row; a `StudentProfile`-only supervisor sees and ticks per-group tasks but not supervisor-audience per-person tasks
  - `backend/tests/apps/plans/test_plan_member_api.py` (GP3): list and toggle status codes in the documented order; a previous-year group returns 200 with an empty list and 404 on toggle; own-row-only (a student's tick never changes another student's row); a replaced mentor's tick does not show for the new mentor; a late joiner sees past-due tasks; a student moved by `confirm_student_assignments` starts unticked in the new group; ticks survive the membership being hard-deleted; an untick with no row creates no row; a tick writes an audit row naming the actor; soft-deleted tasks disappear from the list; `assertNumQueries` shows the list query count is the same for 2 tasks and for 10
  - `backend/tests/apps/admin/test_plan_task_service.py` (GP2): create/update/delete, validation messages, the lock rule (blocked after any completion row exists in a current-year group, even an unticked one; not blocked by rows only in previous-year groups; name/description/due date still editable), `has_completions` matches the lock, soft delete keeps completion rows, audit rows written
  - `backend/tests/apps/admin/test_plan_task_api.py` (GP2): the views' status codes, `IsAdminScoped` (non-admin gets 403), and that `plan-task/progress/` is not swallowed by the `<int:plan_task_id>` route (the same trap TK4 notes for `role-task/role-recipients/`)
  - `backend/tests/apps/admin/test_plan_progress.py` (GP5): per-person totals count only active audience members (suspended accounts included); a leaver's tick is excluded but its row still exists; per-group cells are `1/1` or `0/1`; a group with no member in the audience shows `0/0`; previous-year and soft-deleted groups are excluded; tasks are ordered by `due_date` (nulls last) then `id`; `assertNumQueries` shows the same number of queries (about six) for 2 groups and for 20

**Backend files getting modified:**
- On `feat/tk4-role-based-tasks`, before it is merged into `feat/group-plans` (GP0):
  - `backend/apps/tasks/role_task_views.py`, `RoleTaskToggleView.post` (GP0): set `completion.status = TaskStatus.DONE` when the new value is completed and `TaskStatus.TODO` otherwise (the reverse of `TaskStatusUpdateView`'s "done means completed" rule), and save `update_fields=["completed", "status", "updated_at"]`. Then call `log_audit_event(actor=request.user, entity_type="role_task", entity_id=role_task.id, action="toggle", before_state={"completed", "status"}, after_state={"completed", "status"})`, outside the atomic block as `TaskToggleView.post` does
  - `backend/apps/admin/services/role_task.py` (GP0): `create_admin_role_task`, `update_admin_role_task` (before/after state of `name`, `description`, `due_date`) and `delete_admin_role_task` each call `log_audit_event` with `entity_type="role_task"`, following `apps/admin/services/group.py`
  - Conflict resolution (GP0):
    - `frontend/src/App.vue`: the Role Tasks link becomes an entry in the admin section's `links` array in `sidebarSections`, after `Tasks`
    - `frontend/src/components/admin/tasks/AdminTaskFormSheet.vue`: delete the role fan-out picker, including the `AppSelect` `main` put there
    - `frontend/src/router/routes.ts`: keep both sides; TK4's `/admin/role-tasks` route next to `main`'s `/admin/tasks`
    - `frontend/src/views/admin/AdminTasksPage.vue`: reapply TK4's removal of the role fan-out UI onto `main`'s version, which has 306 changed lines since TK4 branched but no changes to the fan-out parts
    - `frontend/src/views/admin/__tests__/AdminTasksPage.spec.ts`: keep `main`'s updated tests, drop the fan-out ones as TK4 does
  - Breaks the merge does not flag (GP0): replace `formatDateAU` in `AdminRoleTasksPage.vue` (`formatDueDate`) and `formatAnnouncementDateAU` in `DashboardPage.vue`'s role-task block, both removed from `utils/date.ts` on `main`
  - Tests (GP0): `backend/tests/apps/tasks/test_role_task_api.py` `RoleTaskToggleTests` gains assertions that `status` follows `completed` both ways and that an `AuditLog` row is written; `backend/tests/apps/admin/test_role_task_service.py` `AdminRoleTaskServiceTests` gains audit assertions for create, update and delete. After the merge, run the full local checks listed under "Branching and deployment", including `frontend/src/views/admin/__tests__/AdminTasksPage.spec.ts`, `frontend/src/views/admin/__tests__/AdminRoleTasksPage.spec.ts` and `frontend/src/utils/__tests__/adminAPI.spec.ts`
- `backend/config/settings.py` (GP1): add `'apps.plans'` to `INSTALLED_APPS` after `'apps.tasks'`
- `backend/config/urls.py` (GP1): add `path("plans/", include("apps.plans.urls"))` to the `/api/v1/`-only list next to `path("tasks/", include("apps.tasks.urls"))`
- `backend/apps/admin/urls.py` (GP2, GP5):
  - `plan-task/` (list, create) and `plan-task/<int:plan_task_id>/` (get, patch, delete) (GP2)
  - `plan-task/progress/`, placed **before** `plan-task/<int:plan_task_id>/` with the same comment TK4 uses for `role-task/role-recipients/` (GP5)
- `backend/apps/admin/views.py` (GP2, GP5):
  - `AdminPlanTaskListCreateView` and `AdminPlanTaskDetailView` (GP2), copying `AdminRoleTaskListCreateView` and `AdminRoleTaskDetailView` (`permission_classes = [IsAuthenticated, IsAdminScoped]`), except that `patch` returns 400 when the service reports a validation error (TK4's `patch` returns 200 for anything other than "not found")
  - `AdminPlanProgressView` (GP5)
  - This file is under heavy development (705 changed lines on `main` since TK4 branched, and the meetings branch changes it too). Locate classes by name and keep the new ones in their own `# PLAN TASK ENDPOINTS` block after TK4's `# ROLE TASK ENDPOINTS` block (GP2, GP5)
- `backend/apps/admin/management/commands/seed_dummy_data.py` (GP1):
  - A new `_create_plan_tasks` step called after `_create_groups` creates about six plan tasks (each audience and both modes, with past, future and no due dates), every one named with `f"{SEED_PREFIX} ..."`, plus some completion rows, so the demo shows partial progress. Seed groups get `default_group_year()` and the seed creates no `Deadline`, so they are current-year groups unless the database already has an active deadline in another year
  - `_wipe` deletes `PlanTask.objects.filter(name__startswith=SEED_PREFIX)` next to its two `Task` deletes, before `seed_groups.delete()` and `seed_users.delete()`. `PlanTask` has no group and its `created_by` is `SET_NULL`, so after the seed users go it could no longer be found any other way. Completion rows cascade from the deleted tasks, groups and users
- Existing backend tests that need setup changes (GP1 to GP5): none, since the plan adds a new app and changes no existing behaviour. GP0's are listed above

**New frontend files:**
- `frontend/src/utils/plansAPI.ts` (GP4): the `requestJson` helper copied from `tasksAPI.ts` (as TK4's `roleTasksAPI.ts` does), the `GroupPlanTask` and `GroupPlanList` types from the day-one contract, `listGroupPlanTasks(groupId)` and `toggleGroupPlanTask(groupId, taskId, completed?)`
- `frontend/src/components/plans/GroupPlanSection.vue` (GP4): props `groupId` and `initialItems`. It renders the list in server order, with a checkbox per item enabled only when `can_toggle`; for `completed === null` it shows "Each person ticks their own" instead of a checkbox, and per-group items show a "Whole group" tag. The due date is shown with `formatShortDate(due_date, 'UTC')`, with an "Overdue" tag when not completed and `due_date < toTimeZoneDateKey(new Date(), getSetTimeZone())`. It replaces the item with the toggle response, and shows the error text from `apiErrorFromResponse` on 403/404
- `frontend/src/components/plans/__tests__/GroupPlanSection.spec.ts` (GP4): checkbox enabled/disabled by `can_toggle`, the `null` state, the "Whole group" tag, overdue only when incomplete, date shown without a day shift, toggle updates the row
- `frontend/src/views/admin/AdminPlanTasksPage.vue` and `frontend/src/components/admin/plans/AdminPlanTaskFormSheet.vue` (GP2): copies of TK4's `AdminRoleTasksPage.vue` and `AdminRoleTaskFormSheet.vue` (list in `AdminDataTable`, side-sheet form on `FormSheet`, bulk delete through `BulkActionsBar` and `ConfirmDialog`). The form's role picker and recipient count are replaced by:
  - an Audience `AppSelect` (Students, Mentor, Supervisors), following `main`'s rule that `AppSelect` replaces every `<select>` outside analytics
  - a Completion radio (Each person ticks their own / One tick for the whole group, default the first)

  Both are disabled with a hint when the item's `has_completions` is true. The due date `<input type="date">` value is sent as-is (`"YYYY-MM-DD"` or `null`), not through TK4's `toDueDatePayload`. A "View progress" button links to `/admin/plan/progress`
- `frontend/src/views/admin/__tests__/AdminPlanTasksPage.spec.ts` (GP2): create sends the date-only string, the Audience `AppSelect` options, the lock hint and disabled fields when `has_completions`, delete confirms first
- `frontend/src/views/admin/AdminPlanProgressPage.vue` (GP5): a matrix with one row per current-year group and one column per plan task (in the server's order), built from `AppDataTable` with columns generated from the response's `tasks` (`DataTableColumn`). Each cell shows `completed/total`, or `1/1` or `0/1` for per-group columns. The page has a filter by group name and shows the year in its header
- `frontend/src/views/admin/__tests__/AdminPlanProgressPage.spec.ts` (GP5): columns follow the task list, per-group cells show `1/1` / `0/1`, a `0/0` cell renders as `0/0` with no `NaN` and no percentage, the group filter works

**Existing files getting modified (frontend):**
- `frontend/src/App.vue` (GP0, GP2), the admin section's `links` array in `sidebarSections`: `Role Tasks` (GP0, via the merge) and `Plan` (`to: '/admin/plan'`, active for `path.startsWith('/admin/plan')`, so the progress page highlights it too) (GP2)
- `frontend/src/router/routes.ts` (GP0, GP2, GP4, GP5): `/admin/role-tasks` (GP0, via the merge); `/admin/plan` → `AdminPlanTasksPage.vue` (GP2) and `/admin/plan/progress` → `AdminPlanProgressPage.vue` (GP5), both with `meta: { requiresAdmin: true }` like `/admin/tasks`; `{ path: '/groups/:id/plan', name: 'group-plan', component: () => import('@/views/GroupDetailPage.vue') }` next to `group-results` (GP4). No existing route pattern captures these paths
- `frontend/src/utils/adminAPI.ts` (GP0, GP2, GP5): TK4's role-task types and functions (GP0, via the merge); `AdminPlanTask`, `AdminPlanTaskListData`, `CreateAdminPlanTaskPayload`, `UpdateAdminPlanTaskPayload`, `fetchAdminPlanTasks`, `createAdminPlanTask`, `updateAdminPlanTask`, `deleteAdminPlanTask` built on the existing `adminRequest` (GP2); `AdminPlanProgress`, `fetchAdminPlanProgress` (GP5)
- `frontend/src/components/submission/GroupSubmissionSection.vue` (GP4):
  - a `PLAN_ROUTE = 'group-plan'` constant next to `SUBMISSION_ROUTE`
  - a `planItems` ref filled by a `watch` on `groupId` calling `listGroupPlanTasks`, copying the `fetchFinalist` watch (cleared first, only when `canSeeSubmission`, errors swallowed); `hasPlan = planItems.length > 0`
  - a "Plan" pill after "Tasks and Chat", shown when `hasPlan`; the `section` computed returns `'plan'` for `PLAN_ROUTE` when `hasPlan`
  - a `<section v-show="section === 'plan'">` mounting an async `GroupPlanSection` with `:group-id` and `:initial-items="planItems"` on first open (like `hasOpenedFinalist`); `goToSection`'s union and name map gain `plan`
  - the doc comment at the top of the script gains "Plan for a current-year group"

  Because `canSeeSubmission` checks the platform role, a group member whose platform role is none of student, mentor, supervisor or admin sees no Plan pill
- `frontend/src/views/GroupDetailPage.vue` (GP4): add `'group-plan'` to `SECTION_ROUTES`. Nothing else in this file changes
- `frontend/src/components/submission/__tests__/groupSubmissionSection.spec.ts` (GP4):
  - Setup changes: add `{ path: '/groups/:id/plan', name: 'group-plan', component: Host }` to the spec's own `ROUTES` array, and add `vi.mock('@/utils/plansAPI', ...)` next to the existing `managementAPI` and `finalistAPI` mocks with `listGroupPlanTasks` resolving to `{ year, items: [] }` by default, because three existing tests assert the exact pill list with `toEqual(['Tasks and Chat', ...])`
  - New tests: the Plan pill is hidden when the list is empty and shown when not, `/groups/:id/plan` opens the section, and it falls back to tasks on the plan route when there is no plan. The existing "gives every named route a distinct name" test covers the new route name automatically, since it reads `routes.ts` as text
- `frontend/src/views/__tests__/GroupDetailPage.spec.ts` (GP4): no change expected (it stubs `GroupSubmissionSection`); run it after GP4

## Who sees the plan, and the current year

A group sees the plan if and only if it is in `current_plan_groups(year)` with `year = current_cohort()`: not soft-deleted, and `Groups.year == year`. This is decided in that one function and nowhere else; `group_sees_plan`, the member endpoints, the lock check and the progress view all call it. There is no stored link between a group and the plan, no hook at group creation, and no backfill. All eight creation paths give a new group `default_group_year()`, so a group created this year is in the plan from its first request, whichever path made it.

Rollover needs no job and no migration. When `current_cohort()` moves on (a new active deadline in another year, or 1 January UTC with no deadline), last year's groups stop matching: their Plan pill disappears because the list returns no items, toggles return 404, and the progress view stops listing them. Their completion rows stay in `plan_task_completion` untouched. The edge cases are listed under Open items; none of them is specific to plans, since every `current_cohort()` caller already behaves this way.

Inside a group, a person may look at the plan when `can_view_group_plan(facts)` is true: an admin, anyone with an active membership in the group, or anyone holding the tick right (which includes a supervisor of a member). Viewers who fail it get 404. That is a choice for this API, not an existing convention: `TaskToggleView` answers 403 for a task the caller may not toggle, and `GroupViewSet` lets any logged-in user retrieve any active group, so the 404 does not hide whether a group exists. Which tasks a viewer sees is covered in the next section.

**The registration Waiting Area.** A group is in My Groups' Waiting Area when a `RegistrationSubmission` (`apps/users/models/registration.py`) points at it through its `group` foreign key and its `placed_at` is null. That foreign key has no `related_name`, so the reverse query name is `registrationsubmission`. The rest of the code agrees on this definition: `_registered_by` in `apps/users/supervisor_group_views.py` returns `""` for a group with no submission, and `SupervisorGroupsPage.vue` shows a group in the Waiting Area when `registeredBy && !placed`. `placed_at` is set only by `SupervisedGroupsPlaceView.post` (a supervisor's "Create all groups"), only for a group with students in it, and it is never cleared. Filtering on `placed_at` alone would therefore hide almost every group, since it is null for every group not made through registration.

By default, waiting groups see the plan, and `current_plan_groups` is exactly the query above. Should waiting groups need to be excluded, `current_plan_groups` gains one filter, which adds no query (the `Exists` becomes a subquery in the same statement):

```python
in_registration = RegistrationSubmission.objects.filter(group=OuterRef("pk"))
qs = qs.alias(from_registration=Exists(in_registration)).filter(
    Q(placed_at__isnull=False) | Q(from_registration=False)
)
```

That change would come with tests for a registration group not yet placed (excluded), the same group after `SupervisedGroupsPlaceView` (included), and a group made any other way (included). Under that filter, a registration group only gets the plan after a supervisor places it; admins cannot place it, and a registration group with no students never gets it.

## Audience, completion modes and who can tick

Every plan task has an `audience_role` (`student`, `mentor` or `supervisor`), matched against the viewer's `membership_role` in this group, never against platform roles in `RoleAssignmentHistory`. The two can disagree (an admin role change in `update_user` never touches memberships, and `add_members` defaults anyone to `student`), and "the mentor of BTF1" is a group fact. Each task also has a `completion_mode`, set per task by the admin and defaulting to `per_person`.

**Who sees a task.** A viewer sees a task when its audience is their membership role in the group, and also sees every per-group task when they hold the tick right. Without the second half, a student-audience per-group task could never be ticked by anyone who can see it, since students may not tick per-group tasks. An "everyone" audience is not added: it would be a fourth audience value, would need its own total in progress (every active member), and would still not solve the case above. Admins see every task on every current-year group's page. A supervisor linked to a member only through `StudentProfile`, with no membership row in the group, sees and ticks per-group tasks but does not see supervisor-audience per-person tasks (their `membership_role` is `None`) and is not counted in progress totals.

**Who ticks.**

| Mode | Row ticked | Who may tick | Who may not |
|---|---|---|---|
| `per_person` | `(task, group, viewer)` | The viewer, when their membership role in this group equals the audience | Anyone else, including admins and the mentor, on someone else's behalf |
| `per_group` | `(task, group, user=null)` | Admin, the group's active mentor (`_is_active_group_mentor`), a supervisor of any member (`_supervises_any_in_group`) | Students, whatever the audience |

The list endpoint computes `can_toggle` per item with `can_tick_plan_task(task, facts)`, a pure function over the viewer facts, so the Vue side never repeats these rules and the list does no query per item. A per-person task shown to a non-audience viewer returns `completed: null`, not `false`, so an admin looking at a group does not see a misleading empty box. Plan ticks go through `GroupPlanTaskToggleView` only; `_can_toggle`, `CanToggleTask`, `TaskStatusUpdateView`, `TaskBulkToggleView` and `GroupTaskToggleTests` are not touched.

**Locking.** `audience_role` and `completion_mode` cannot change once a `PlanTaskCompletion` row exists for the task in a current-year group, even an unticked one, because a row records that someone acted on it. `name`, `description` and `due_date` stay editable, and the admin's way out is to soft-delete the task and create a new one.

The lock exists because changing either setting would corrupt progress: changing the mode would leave per-person rows that count for nothing, or a per-group row nobody can see, and changing the audience would silently drop ticks out of progress. The database cannot enforce "user is null exactly when the task is per-group", because that spans two tables; the service sets `user` from the task's mode, and the lock keeps the mode fixed while current-year rows exist.

Two details define exactly when the lock applies:
- Rows in previous-year groups do not lock, so a task reused next year can be changed once the year rolls over. Those old rows may then disagree with the task's new mode, which is acceptable because previous-year rows are never read
- An untick request for a task nobody has ticked creates no row; a tick followed by an untick leaves its row, so the task stays locked

`has_completions` in the admin list is the same current-year `Exists` check, so the form and the service always agree.

**Soft delete.** Deleting a plan task sets `deleted_at`; completion rows survive. A deleted task disappears from every group's list and from progress at once.

## Progress, leavers and mentor changes

A person's tick belongs to (task, group, user), so it follows them, not their membership row. That one decision produces every membership rule the client asked for, with no extra code:
- **A new mentor starts unticked**: they are a different user, so no row exists for them until they tick. The replaced mentor's row stays and stops counting. If the old mentor is later put back on the same group, their old tick reappears (an edge case to mention, not to fix)
- **A late joiner sees every task, including past-due ones**: the list does not filter by `joined_at` or by date
- **A leaver's completions are kept but not counted**: their rows remain (also when the membership row was hard-deleted by `confirm_student_assignments` or `remove_group_member`), and progress only counts users with an active membership now
- **A student moved to another group starts unticked there**, because the group is part of the key. A supervisor or mentor in several groups ticks once per group

`get_plan_progress` (GP5) returns completed/total per task per current-year group with a fixed number of queries, whatever the number of groups or tasks. There are about six: the admin check, `current_cohort()` called once, the task list, the group list, and these two grouped queries:
1. **Completed counts:** `PlanTaskCompletion` filtered to active tasks, `current_plan_groups(year)` and `completed=True`. It keeps per-group rows (`user` null) and per-person rows whose user has an active membership in that group with `membership_role` equal to the task's `audience_role` (an `Exists` subquery on `GroupMembership` with `OuterRef("group_id")`, `OuterRef("user_id")` and `OuterRef("task__audience_role")`), then `.values("task_id", "group_id").annotate(done=Count("id"))`
2. **Audience sizes:** `active_audience_memberships(current group ids).values("group_id", "membership_role").annotate(n=Count("user_id", distinct=True))`

A per-person cell is `done / n[(group, audience_role)]`; a per-group cell is `1/1` or `0/1`. A group with nobody in the audience shows `0/0` (two seed groups are deliberately empty, so the demo will show this), and the page never divides by it. Tasks are ordered like the member list (`due_date` with nulls last, then `id`); groups are ordered with `group_name_sort_key()`. The same two grouped queries, restricted to one group, are what a future "4/5 students done" line on the group page would use.

## Dates and live edits

`PlanTask.due_date` is a `DateField`: no time and no timezone. The API sends and accepts `"YYYY-MM-DD"` or `null`; anything else is a 400. Lists order by `F("due_date").asc(nulls_last=True)`, then `id`, so tasks without a date sort last on both SQLite (tests) and Postgres (production), the problem TK4 fixed in commit `08341087`. TK4's `RoleTask.due_date` stays a `DateTimeField` and is not touched. Overdue is decided on the frontend ("not completed, and the due date is before today in the viewer's time zone"), not stored. Server-side tests that need "today" use `timezone.localdate()`.

Because there is one template and every read is live, editing a due date (or name or description) changes it for every current-year group at once with no extra mechanism, the same way `update_admin_role_task` works for TK4. Adding a task makes it appear in every current-year group, including groups created later and members who join later; soft-deleting it removes it everywhere. Nothing caches task, group or plan reads on the server, and there is no live push for tasks, so a group page that is already open shows the change after a reload. There are no per-group dates and no extensions (`GroupExtension` is not involved).

## API layer

**Admin API**, under `/api/v1/admin/`, all behind `[IsAuthenticated, IsAdminScoped]`, returning TK4's `{"msg", "data"}` envelope:
- GET `/plan-task/?page=&limit=&sortBy=&sortOrder=`: 200, `data = {items, total, page, limit, has_more}`; each item `{id, name, description, due_date, audience_role, completion_mode, has_completions, created_by: {id, name} | null, created_at, updated_at}`, where `has_completions` means "has a completion row in a current-year group" (GP2)
- POST `/plan-task/`: body `{name, description?, due_date: "YYYY-MM-DD" | null, audience_role, completion_mode?}`; 201 with the item; 400 with `msg` on invalid input (GP2)
- GET `/plan-task/<id>/`: 200; 404 if missing or soft-deleted (GP2)
- PATCH `/plan-task/<id>/`: any of `name`, `description`, `due_date`, `audience_role`, `completion_mode`; 200 with the item; 400 when invalid or when `audience_role`/`completion_mode` change while `has_completions` is true; 404 if missing (GP2)
- DELETE `/plan-task/<id>/`: soft delete; 204; 404 if missing (GP2)
- GET `/plan-task/progress/`: 200, `data = {year, tasks: [{id, name, audience_role, completion_mode, due_date}], groups: [{id, name, cells: {"<task_id>": {completed, total}}}]}`; tasks ordered by `due_date` (nulls last) then `id`; groups are `current_plan_groups(year)` ordered with `group_name_sort_key()` (so BTF10 sorts after BTF9). Must be routed before `<int:plan_task_id>` (GP5)

**Member API**, under `/api/v1/plans/` (the `/api/v1/`-only list in `backend/config/urls.py`), behind `IsAuthenticated`, returning plain JSON like TK4's member endpoints:
- GET `/groups/<group_id>/tasks/`: 404 when the group does not exist, is soft-deleted, or the viewer fails `can_view_group_plan`; otherwise 200 `{year, items: [...]}`, with `items` empty for a previous-year group. Each item `{id, name, description, due_date, audience_role, completion_mode, completed: true | false | null, can_toggle}` (GP3)
- POST `/groups/<group_id>/tasks/<task_id>/check/`: body `{}` (flip) or `{"completed": true | false}`; 200 with the updated item (unchanged, with no row created, for an untick with no row); 400 when `completed` is not a boolean; 403 when the task is visible but `can_toggle` is false; 404 when the group or task is not visible, the task is soft-deleted, or the group is not a current-year group (GP3)

**TK4 endpoints** keep their paths and change behaviour only: POST `/api/v1/tasks/role-tasks/<id>/check/` also sets `status`, and it and the `/api/v1/admin/role-task/` mutations write audit rows (GP0).

## Work Breakdown

Two people, each owning a whole side of the feature end to end (backend and frontend). The split totals 21 SP; GP0 is pre-work outside the totals.

| Person | Side | Stories | SP |
|---|---|---|---|
| Person A | The member side | GP1, GP3, GP4 | 11 |
| Person B | TK4 and the admin side | GP0 (pre-work), GP2, GP5 | 10 (plus 5 for GP0) |

- **Why this split:** the work is split by feature so each person owns a whole side, and 11 and 10 SP is the most even split that stories of 3, 3, 5, 5 and 5 SP allow. Person B owns GP0 because it touches the same frontend files GP2 edits next
- **What the two sides share:** one file, `routes.ts`, and one real hand-off: GP1's models, which Person B needs for the admin backend while building the admin pages against mocks
- **Longest chain:** Person A's GP1 then GP3 then GP4, about 11 SP
- **Why not three:** the three-person split of the same stories is 5, 8 and 8 SP with a longest chain of about 8. That saves about 3 SP of elapsed work, but adds four more shared files (`adminAPI.ts`, `apps/admin/urls.py`, `apps/admin/views.py` and `apps/plans/urls.py`) and more hand-offs, and leaves one person with a 5 SP stream
- **Why not one:** all 21 SP plus GP0 would run in sequence, about 26 SP of elapsed work against about 16 (GP0, then Person A's 11)
- **Where it breaks:** if GP0 is still running when Person A starts GP1, Person B's stream is GP0, GP2 and GP5, about 15 SP, and becomes the longest. Either finish GP0 first, or swap GP4 and GP5 (Person A takes GP1, GP3 and GP5; Person B takes GP0, GP2 and GP4: 13 and 13 SP including GP0), which splits both the admin and the member feature across the two people
- **No spare capacity:** the backlog update, the integration pass and demo preparation come out of the same two people's time

### Person A: The member side (GP1 → GP3 → GP4, 11 SP)
- **GP1**: the `apps/plans` app (`PlansConfig`, `models.py`, `0001_initial`, `admin.py`), `visibility.py` (`current_plan_groups`, `group_sees_plan`, `active_audience_memberships`), the `INSTALLED_APPS` and `config/urls.py` lines, an empty `apps/plans/urls.py`, and `_create_plan_tasks` plus the `_wipe` addition in `seed_dummy_data.py`. This is first in the critical path, so it starts on day one and is pushed as soon as the models and helper pass their tests (seed data can follow)
- **GP3** once GP1 is pushed: `apps/plans/permissions.py` (`viewer_facts`, `can_view_group_plan`, `visible_plan_tasks`, `can_tick_plan_task`), `serializers.py`, `views.py`, the two routes in `apps/plans/urls.py`, the audit call on toggle
- **GP4**: `plansAPI.ts`, `GroupPlanSection.vue`, the Plan pill and section in `GroupSubmissionSection.vue`, the `group-plan` route, `'group-plan'` in `SECTION_ROUTES`. GP4 comes after GP3 and uses the real endpoints; it may start against the contract's mocks if anything is pending
- Tests: `backend/tests/apps/plans/__init__.py`, `test_plan_models.py`, `test_plan_visibility.py`, `test_plan_permissions.py`, `test_plan_member_api.py` (including `assertNumQueries`), `GroupPlanSection.spec.ts`, the `groupSubmissionSection.spec.ts` setup changes and new tests, and rerunning `GroupDetailPage.spec.ts`

### Person B: TK4 pre-work and the admin side (GP0 pre-work, then GP2 → GP5, 10 SP)
- **GP0** (pre-work, 5 SP, not in the totals): merge `origin/main` into `feat/tk4-role-based-tasks` (no rebase, no force push) and resolve the five conflicts (`App.vue`, `AdminTaskFormSheet.vue`, `routes.ts`, `AdminTasksPage.vue`, `AdminTasksPage.spec.ts`); replace `formatDateAU` and `formatAnnouncementDateAU`; the `status` fix and audit logging in `RoleTaskToggleView.post`; audit logging in `create_admin_role_task`/`update_admin_role_task`/`delete_admin_role_task`; push the TK4 branch, create `feat/group-plans` from `main`, merge the TK4 branch into it, and open the draft PR into `main`
- **GP2**: `apps/admin/services/plan_task.py`, `AdminPlanTaskListCreateView`/`AdminPlanTaskDetailView`, the `plan-task/` routes, `AdminPlanTasksPage.vue`, `AdminPlanTaskFormSheet.vue` (Audience as `AppSelect`), the `adminAPI.ts` plan-task types and functions, the `Plan` sidebar link and the `/admin/plan` route. The frontend goes first, against the contract's mocks, while Person A builds GP1; the backend follows once GP1's models are pushed
- **GP5**: `apps/admin/services/plan_progress.py` (`get_plan_progress`), `AdminPlanProgressView`, the `plan-task/progress/` route, `AdminPlanProgressPage.vue`, `fetchAdminPlanProgress` in `adminAPI.ts`, the `/admin/plan/progress` route
- Tests: GP0's additions to `test_role_task_api.py` and `test_role_task_service.py`, and resolving and rerunning `AdminTasksPage.spec.ts`, `AdminRoleTasksPage.spec.ts` and `adminAPI.spec.ts`; `test_plan_task_service.py`, `test_plan_task_api.py`, `test_plan_progress.py` (including `assertNumQueries`), `AdminPlanTasksPage.spec.ts` and `AdminPlanProgressPage.spec.ts`

### Files more than one person touches
- **Shared:** `frontend/src/router/routes.ts` is the only file both people edit: Person B adds the GP0 merge, `/admin/plan` and `/admin/plan/progress`; Person A adds `/groups/:id/plan`. One line each, in different blocks
- **Read across the split:** `backend/apps/plans/models.py` and `visibility.py` are owned by Person A; Person B only reads them. Any field change goes through Person A
- **Single owners:** Person B owns `frontend/src/App.vue`, `frontend/src/utils/adminAPI.ts`, `backend/apps/admin/urls.py` and `backend/apps/admin/views.py`; Person A owns `backend/apps/plans/urls.py`, `frontend/src/components/submission/GroupSubmissionSection.vue`, `frontend/src/views/GroupDetailPage.vue`, `backend/config/settings.py` and `backend/config/urls.py`

### Day-one contract
Agreed on day one by Person A and Person B, so Person B's GP2 and GP5 frontends (and Person A's GP4, if anything is pending) can start against mocks:
- Values: `audience_role` is `"student" | "mentor" | "supervisor"`; `completion_mode` is `"per_person" | "per_group"`; `due_date` is `"YYYY-MM-DD" | null`
- `GroupPlanTask`: `{ id: number, name: string, description: string, due_date: string | null, audience_role, completion_mode, completed: boolean | null, can_toggle: boolean }`
- `GroupPlanList`: `{ year: number, items: GroupPlanTask[] }`
- `AdminPlanTask`: `{ id, name, description, due_date, audience_role, completion_mode, has_completions: boolean, created_by: { id, name } | null, created_at, updated_at }`
- `AdminPlanProgress`: `{ year: number, tasks: { id, name, audience_role, completion_mode, due_date }[], groups: { id: number, name: string, cells: Record<string, { completed: number, total: number }> }[] }`
- Paths: `GET/POST /api/v1/admin/plan-task/`, `GET/PATCH/DELETE /api/v1/admin/plan-task/<id>/`, `GET /api/v1/admin/plan-task/progress/`, `GET /api/v1/plans/groups/<group_id>/tasks/`, `POST /api/v1/plans/groups/<group_id>/tasks/<task_id>/check/`
- Admin responses use the `{msg, data}` envelope; member responses are plain JSON

## Dependencies between people
- **GP1 is the only hard dependency between people.** Person B's GP2 and GP5 backends import `apps/plans/models.py` and `visibility.py`, so Person A pushes GP1's models, migration and helper first, before the seed data
- **Everything else stays inside one person.** GP3 and GP4 are both Person A's, and GP2 and GP5 are both Person B's, so no API contract has to hold between people beyond the data model; the two sides meet in the integration pass. Within Person A's side, GP4 depends on GP3 only for the real endpoints, and the day-one contract lets it start on mocks if needed. Within Person B's side, GP5's tests create completion rows directly, so GP5 does not wait for GP3; for the demo, GP3 must be in so ticks made on the group page show in the progress view
- **GP0 does not block plan work in code.** The plan lives in its own app with its own migration and never imports TK4. GP0 is pre-work because it touches `App.vue`, `routes.ts` and `adminAPI.ts`, which GP2 edits next, and the TK4 merge is easiest before the shared branch fills up. GP2 also copies TK4's admin page and form, which are on the shared branch once GP0 is merged in
- **Outside the team.** `feature/group-meetings-frontend` touches `routes.ts`, `GroupDetailPage.vue`, `App.vue`, `DashboardPage.vue`, `adminAPI.ts`, `stores/auth.ts`, `admin/views.py`, `settings.py` and `config/urls.py`, and adds the `meetings` and `tickets` apps. If it reaches `main` first, the weekly merge of `main` brings those changes in; if GP0 is not finished by then, GP0 also absorbs its `DashboardPage.vue`, `App.vue`, `routes.ts` and `adminAPI.ts` changes

## Completion order
1. Pre-work: Person B does GP0, creates `feat/group-plans` from `main`, merges the TK4 branch into it and opens the draft PR into `main`. Both people agree the day-one contract
2. Day one: Person A starts GP1; Person B starts GP2's frontend against mocks
3. Person A pushes GP1's models, migration and helper, finishes the seed data and starts GP3; Person B starts GP2's backend
4. Person B finishes GP2 and starts GP5; Person A finishes GP3 and starts GP4 against the real endpoints
5. Person A finishes GP4; Person B finishes GP5
6. Integration testing on seeded data: create tasks of every audience and mode, tick them as each role, check the progress view, then move the active deadline into next year to confirm the plan disappears and the rows stay, and move it back
7. The draft PR from `feat/group-plans` into `main` is marked ready and merged; it carries TK4 and the plan together

## Branching and deployment
`feat/` with a short name matches `feat/tk4-role-based-tasks`, which this extends. There is no staging environment for the backend, the same as other epics. Two people share one branch, because the two CI workflows that run tests only run for pull requests into `main`: a sub-branch per person would get no CI at all, while one branch with an early draft PR gets CI on every push.
1. **Update TK4 (GP0, pre-work).** Person B merges `origin/main` into `feat/tk4-role-based-tasks` and pushes it. That branch is already pushed, so it is updated by merging, not rebasing, and never force-pushed. TK4 does not get its own PR into `main`
2. **Create the shared branch and the draft PR.** Person B creates `feat/group-plans` from `main`, merges `feat/tk4-role-based-tasks` into it, pushes it, and opens a draft PR from `feat/group-plans` into `main` straight away, so CI runs on every push. The draft PR also gets an Azure Static Web Apps frontend preview on every push that touches `frontend/**`, built against the production API; the new screens will show errors there until the backend ships, so the preview link should not be shared
3. **Work on the shared branch.** Both people work directly on `feat/group-plans`. Pull before starting a piece of work, give a heads-up before touching `routes.ts` (the only file you share) or a file the other person owns, and merge `main` into `feat/group-plans` once a week
4. **Check before every push.** Run locally: the backend suite (`python manage.py test tests --settings=config.settings_test` in `backend/`), `python manage.py makemigrations --check --dry-run`, `npm run type-check` and `npm run test:unit -- --run` in `frontend/`
5. **Apply new migrations locally.** When a push adds a migration, also apply it to a local development database with `python manage.py migrate`, since the test settings never run migrations. Two local setup notes:
   - With the Docker database from `docker-compose.dev.yml`, set `DB_HOST=127.0.0.1` rather than `localhost`: `localhost` resolves to `::1` first, the container only listens on `127.0.0.1`, and the connection hangs
   - Running the whole migration history on a brand-new SQLite database fails at `submissions/0013_submission_cohort` (its field default calls `current_cohort()` mid-migration), which is unrelated to this work
6. **Ship in one PR.** When all stories are complete and tested together, the draft PR is marked ready, reviewed and merged: one PR into `main` for TK4 and the plan
7. **Run the production migrations by hand**, as today: `tasks/0012_roletask_roletaskcompletion_and_more` and `plans/0001_initial` deploy together with this one release. Both only create tables, so they are safe to run before or after the code is live. Both are reversible, but unapplying either one drops its tables and all their data (every role task and plan task, and every tick)
