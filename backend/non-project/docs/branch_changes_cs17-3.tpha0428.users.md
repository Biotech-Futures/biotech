# Branch Change Summary: `cs17-3.tpha0428.users`

This document records the main backend changes made on branch `cs17-3.tpha0428.users`, with a focus on:

- what changed
- why the change was made
- what effect the change has on the active runtime

It describes the current branch delta in the working tree and added migration files.

## 1. User Schema Realignment

### What changed

The active `users` domain was updated to match the newer proposed schema decisions more closely:

- removed legacy `users.status`
- removed legacy `users.state`
- removed `student_profile.interest`
- removed mentor `background`
- removed mentor `max_grp_cnt`
- introduced `mentor_profile.max_group_count`
- introduced `users.account_status`
- introduced `users.invited_at`
- introduced `users.activated_at`
- introduced `mentor_interest`
- introduced `mentor_availability`
- introduced `admin_scope`
- removed `relationship_type`
- removed `student_supervisor.relationship_type`

Main code location:

- [models.py](/Users/tuankiet.pham_/biotech/backend/apps/users/models.py)

Migration chain added:

- [0004_adminscope_mentoravailability_mentorinterest_and_more.py](/Users/tuankiet.pham_/biotech/backend/apps/users/migrations/0004_adminscope_mentoravailability_mentorinterest_and_more.py)
- [0005_remove_mentorprofile_background_and_more.py](/Users/tuankiet.pham_/biotech/backend/apps/users/migrations/0005_remove_mentorprofile_background_and_more.py)
- [0006_alter_mentorprofile_max_group_count_and_more.py](/Users/tuankiet.pham_/biotech/backend/apps/users/migrations/0006_alter_mentorprofile_max_group_count_and_more.py)
- [0007_remove_studentsupervisor_relationship_type_and_more.py](/Users/tuankiet.pham_/biotech/backend/apps/users/migrations/0007_remove_studentsupervisor_relationship_type_and_more.py)

### Why it changed

These fields and tables represented legacy schema decisions that no longer matched the target direction for the platform:

- `status` duplicated Django’s built-in activation model and was replaced by `is_active` plus `account_status`
- `state` duplicated geography already implied by `track`
- `student_profile.interest` duplicated the normalized `student_interest` table
- `background` no longer belongs in the proposed mentor model
- `max_grp_cnt` was a legacy field name and was replaced with `max_group_count`
- `relationship_type` was no longer part of the proposed schema and was not needed for active workflows

The new schema is intended to make the model:

- more normalized
- easier to reason about
- better aligned with onboarding and admin workflows
- more compatible with future matching logic

## 2. Account Lifecycle and Auth Model Cleanup

### What changed

The custom user model and manager were updated so activation state and lifecycle state are handled together:

- `create_user()` now derives lifecycle defaults from whether a password is supplied
- `User.save()` now keeps `is_active` and `account_status` in sync
- the active boolean for user access is now `is_active`

Main code location:

- [models.py](/Users/tuankiet.pham_/biotech/backend/apps/users/models.py)

### Why it changed

Previously the project carried both:

- Django’s `is_active`
- a second custom `status` field

That made activation logic ambiguous and error-prone. The change was made so:

- the backend uses Django’s standard active/inactive flag
- onboarding and activation still have richer lifecycle tracking through `account_status`
- future auth and admin workflows have a single consistent source of truth for account enablement

## 3. User API Cutover

### What changed

The users views, serializers, templates, and tests were updated to stop depending on removed fields:

- list and detail responses now use `is_active` instead of `status`
- user endpoints no longer rely on `state`
- mentor output no longer references `background`
- mentor output now includes `max_group_count`
- registration flow no longer writes `user.state`
- registration flow no longer writes `student_profile.interest`
- registration flow no longer creates `RelationshipType`
- registration flow no longer writes `student_supervisor.relationship_type`

Main code locations:

- [views.py](/Users/tuankiet.pham_/biotech/backend/apps/users/views.py)
- [serializers.py](/Users/tuankiet.pham_/biotech/backend/apps/users/serializers.py)
- [list.html](/Users/tuankiet.pham_/biotech/backend/apps/users/templates/users/list.html)
- [details.html](/Users/tuankiet.pham_/biotech/backend/apps/users/templates/users/details.html)
- [tests.py](/Users/tuankiet.pham_/biotech/backend/apps/users/tests.py)

### Why it changed

Once the legacy columns were removed from the schema, the API layer had to be cut over as well. Without that cutover:

- serializers would crash on removed fields
- registration would try to write to deleted columns
- templates and tests would continue asserting old behavior

This change makes the active users API reflect the real schema instead of a mixed old/new state.

## 4. Mentor Interest and Availability Support

### What changed

Canonical mentor interest and availability models were added to the active users domain:

- `MentorInterest`
- `MentorAvailability`

The admin registration was also updated to expose these models:

- [admin.py](/Users/tuankiet.pham_/biotech/backend/apps/users/admin.py)

### Why it changed

The proposed schema moved mentor matching inputs into the main user/profile domain:

- mentors now share the same interest catalog as students
- mentor timetable availability is stored in the active runtime instead of only existing in legacy matching code

This supports future matching work without requiring the legacy matching schema to stay authoritative.

## 5. Admin Scope Support

### What changed

A new `AdminScope` model was added:

- scoped admin records can now represent track-specific admin scope
- global admins can be represented explicitly using `is_global`

Main code location:

- [models.py](/Users/tuankiet.pham_/biotech/backend/apps/users/models.py)

### Why it changed

The previous schema did not support a clean local-admin/global-admin distinction. Adding `AdminScope` provides the database structure needed for scoped RBAC rather than treating all admins as equivalent.

## 6. Schema Generation and API Documentation Fixes

### What changed

Several APIView-based endpoints were annotated for drf-spectacular so schema generation no longer fails with “unable to guess serializer” errors.

Updated endpoints:

- [events/views.py](/Users/tuankiet.pham_/biotech/backend/apps/events/views.py)
- [services/views.py](/Users/tuankiet.pham_/biotech/backend/apps/services/views.py)
- [tasks/views.py](/Users/tuankiet.pham_/biotech/backend/apps/tasks/views.py)
- [users/views.py](/Users/tuankiet.pham_/biotech/backend/apps/users/views.py)

Additional schema cleanup:

- serializer method fields in [users/serializers.py](/Users/tuankiet.pham_/biotech/backend/apps/users/serializers.py) now use explicit `@extend_schema_field(...)`
- resource serializers in [resources/serializers.py](/Users/tuankiet.pham_/biotech/backend/apps/resources/serializers.py) were updated to avoid duplicate `User` component names and unresolved method-field warnings
- [resources/views.py](/Users/tuankiet.pham_/biotech/backend/apps/resources/views.py) now declares a base queryset so the schema generator can infer the detail path parameter type

### Why it changed

Before this cleanup:

- `/api/schema/` failed or emitted many avoidable errors
- APIView endpoints had no declared request/response schema
- drf-spectacular had to guess method-field types
- the OpenAPI output was noisy and unreliable

These changes were made so the API documentation reflects the live backend more accurately and remains usable by frontend or integration work.

### Implementation note: `extend_schema` and `extend_schema_field`

Two drf-spectacular decorators were used repeatedly in this branch:

- `@extend_schema(...)`
- `@extend_schema_field(...)`

Their roles are different.

`@extend_schema(...)` is applied at the view-method level. It is used when drf-spectacular cannot infer the request body, response body, or path/query parameters automatically from the view class.

That situation happens often with `APIView`, because `APIView` does not inherently tell the schema generator:

- which serializer represents the request body
- which serializer represents the response body
- what the path parameters mean

For example, an endpoint like `SendLoginCodeView.post()` accepts JSON and returns a structured response, but without a declared serializer drf-spectacular only sees arbitrary request handling code. In that case, `@extend_schema(...)` was added so the schema generator knows exactly:

- which serializer is expected as input
- which serializer is returned on success
- which serializer is returned on common error responses

This is why endpoints in:

- [services/views.py](/Users/tuankiet.pham_/biotech/backend/apps/services/views.py)
- [events/views.py](/Users/tuankiet.pham_/biotech/backend/apps/events/views.py)
- [tasks/views.py](/Users/tuankiet.pham_/biotech/backend/apps/tasks/views.py)
- [users/views.py](/Users/tuankiet.pham_/biotech/backend/apps/users/views.py)

were annotated explicitly. The purpose was not to change runtime behavior; it was to make `/api/schema/` and generated API docs accurate and stable.

`@extend_schema_field(...)` is narrower. It is applied to serializer methods, usually methods behind `SerializerMethodField`.

drf-spectacular can usually infer field types from normal serializer fields such as:

- `serializers.CharField`
- `serializers.IntegerField`
- `serializers.BooleanField`

But it cannot reliably infer the output type of methods like:

- `get_current_role_id`
- `get_join_perm`
- `get_ment_max_groups`

without extra help. When left unannotated, the schema generator falls back to guessing, which led to warnings such as:

- “unable to resolve type hint for function ...”

In this branch, `@extend_schema_field(...)` was added to those methods so the schema explicitly records whether the computed value is:

- an integer
- a boolean
- a string
- nullable
- a list of nested serializer values

That was used in:

- [users/serializers.py](/Users/tuankiet.pham_/biotech/backend/apps/users/serializers.py)
- [resources/serializers.py](/Users/tuankiet.pham_/biotech/backend/apps/resources/serializers.py)

In short:

- `extend_schema` documents an endpoint contract
- `extend_schema_field` documents a computed serializer field type

Both were necessary because this branch not only changed the schema, but also changed what the API returns. The annotations ensured the OpenAPI layer was updated to match the new runtime instead of lagging behind or guessing incorrectly.

## 7. Test and Fixture Alignment

### What changed

Tests that still created users with deleted fields were updated:

- removed `state=` from users created in resource tests
- updated users tests to use `is_active`
- updated user test URLs to use named routes instead of stale hardcoded paths

Main code locations:

- [resources/tests.py](/Users/tuankiet.pham_/biotech/backend/apps/resources/tests.py)
- [resources/tests_permissions.py](/Users/tuankiet.pham_/biotech/backend/apps/resources/tests_permissions.py)
- [users/tests.py](/Users/tuankiet.pham_/biotech/backend/apps/users/tests.py)

### Why it changed

Once `users.state` and `users.status` were removed, fixtures and assertions depending on them were invalid. These test updates were required so the branch remains runnable and the tests reflect the current schema.

### Implementation note: `django.urls.reverse`

This branch also switched the users tests away from hardcoded paths and toward Django’s named-route lookup using `reverse`.

The relevant import is:

- `from django.urls import reverse`

and the main example is in:

- [users/tests.py](/Users/tuankiet.pham_/biotech/backend/apps/users/tests.py)

`reverse(...)` takes a route name from the URL configuration and returns the actual URL path string at runtime.

Instead of writing:

```python
self.client.get("/users/api/v1/users/")
```

the test now does:

```python
self.client.get(reverse("UserListHTMLView"))
```

This matters because hardcoded URLs had already drifted away from the real routing in [urls.py](/Users/tuankiet.pham_/biotech/backend/apps/users/urls.py). Once that drift happens, tests start failing for the wrong reason:

- not because the endpoint is broken
- but because the test is pointing at an outdated path

Using `reverse(...)` solves that by coupling tests to the named route rather than to a copied string literal. The benefits are:

- tests stay correct when the path changes but the route name stays the same
- URL intent is clearer in the test
- there is less duplication of URL strings across the codebase
- the test suite is less brittle during refactors

In this branch, `reverse(...)` was part of the broader effort to align tests with the active runtime instead of leaving them pinned to stale API paths.

## 8. Local Development Configuration

### What changed

Local Postgres defaults were added in:

- [settings_local.py](/Users/tuankiet.pham_/biotech/backend/config/settings_local.py)

Defaults now fall back to:

- database: `biotech_dev`
- user: `biotech`
- password: `biotech`
- host: `127.0.0.1`
- port: `5432`

### Why it changed

Previously local settings depended entirely on exported environment variables. That made the local boot path fragile and caused avoidable failures in checks and tests when the variables were missing. The defaults make development more reproducible while still allowing overrides through env vars.

## 9. Current Schema Notes Update

### What changed

The current schema note in:

- [schema.md](/Users/tuankiet.pham_/biotech/backend/non-project/docs/schema.md)

was updated to remove the old `relationship_type` table and FK reference from the example SQL.

### Why it changed

This keeps the current-state documentation consistent with the live branch schema after the `RelationshipType` removal.

## 10. Validation Completed

The branch changes were verified with the following checks during implementation:

- `python manage.py check --settings=config.settings_local`
- `python manage.py migrate --settings=config.settings_local`
- `python manage.py makemigrations users --check --dry-run --settings=config.settings_local`
- `python manage.py spectacular --file /tmp/biotech-schema.yaml --validate --settings=config.settings_local`
- `python manage.py test apps.users.tests --settings=config.settings_local`

Observed outcome:

- migration drift in `users` was resolved
- the OpenAPI schema no longer fails on serializer inference for the affected endpoints
- the active users test slice passes

## 11. Summary

In practical terms, this branch moves the backend away from a mixed legacy/current users schema and toward a cleaner canonical runtime:

- fewer duplicated fields
- clearer account lifecycle handling
- cleaner mentor matching inputs
- less schema/documentation drift
- better OpenAPI generation
- safer local development defaults

The branch is primarily a users-domain schema cleanup and API alignment branch, with secondary OpenAPI and local-dev stabilization work.
