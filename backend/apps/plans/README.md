# Group Plans foundation (GP1)

This app stores one shared stage/task definition and each group's completion
records. It does not depend on TK4. GP2 implements admin mutations; GP3 implements
member permissions/endpoints. No member routes are implemented in this handover.

## Using the foundation

```python
from apps.plans.models import PlanStage, PlanTask, PlanTaskCompletion
from apps.plans.visibility import current_plan_groups, active_audience_memberships
from apps.submissions.services import current_cohort

year = current_cohort()  # Read once per request.
groups = current_plan_groups(year)
tasks = PlanTask.objects.active().select_related("stage")
memberships = active_audience_memberships(groups.values_list("id", flat=True))
```

- Stage/task ordering follows numeric position, then ID (stage first).
- `PlanTask.objects.active()` excludes both deleted tasks and deleted stages.
- Audience values: `student`, `mentor`, `supervisor`; modes: `per_person` (default),
  `per_group`. A nullable `DateField` stores date-only due dates.
- Individual records use `(task, group, user)`; shared records use a null user and
  unique `(task, group)`. These are database-enforced conditional constraints.
- Services must choose the correct record type for the task mode, enforce
  audience/mode locks and resource validation, and audit changes. The database
  cannot enforce rules spanning the task and completion tables.
- Counts use active group memberships, including suspended/deactivated accounts.
  This helper does not grant anyone permission to tick a task.
- Moving a task retains its ID and ticks; a replacement task inherits none.
- Django admin is read-only. Admin services must enforce empty-stage deletion
  and the stage/task row-lock protocol in the implementation reference.

The existing `seed_dummy_data` command now adds three demo stages and six tasks
covering all audience/mode pairs. Use an isolated local database; its active cohort
must match the seed groups' year. Wipe removes seed tasks before protected stages
and refuses to delete a seed stage containing non-seed tasks.

Run foundation tests from `backend/`:

```text
python manage.py test tests.apps.plans --settings=config.settings_test
```

Apply `plans/0001_initial` with migrations enabled on a local development database.
Normal test settings disable migrations. See the repository's `docs/` technical
plan for the full contract and the outstanding client student-ticking decision.
