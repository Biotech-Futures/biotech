# Student registration and late links

The consolidated frontend/backend change on current `main` implements **five student journeys** at
`POST /api/v1/registration` (both slash variants and `registration-intake/`
are aliases). Mentor intake remains explicitly unsupported, without a legacy
fallback. It combines the
full `registration` branch and the production changes from frontend #475 and
backend #476. Registration history is retained while its older frontend wiring
is reconciled with current main and the newer intake contract.

| Journey | Students | Authorization and persistence |
| --- | --- | --- |
| `student_individual` | 1 | Public; complete student and guardian details |
| `student_team` | 2-5 | Public; complete creator, pending identity-only peers, real group and shared interests |
| `supervisor_individual` | 1 | Current supervisor session/profile; optional deferred guardian |
| `supervisor_group` | 2-5 | Current supervisor session/profile; real group and shared interests |
| `supervisor_csv` | 1-500 | Current supervisor session/profile; atomic batch with original CSV row numbers |

Supervisor identity is resolved from the session and its existing profile,
never from a payload claim. A current supervisor role (or staff/admin authority)
and an existing supervisor profile are required. Anonymous, suspended/deactivated
or unauthorized users cannot use supervisor journeys.
Registration never creates a supervisor or grants a public caller that role.

Group creators provide guardian contact. Represented students may defer it.
Identity-only teammates retain blank school/year and null geography until the
existing protected profile workflow completes them; no placeholder details are
invented. All new accounts remain pending, with no usable password or consent.
Groups use main's auto-naming, student memberships, shared interests and
supervisor-membership synchronization. Group interests are not copied into
members' personal interests. Supervisor registrations retain main's detail lock.

## Session-protected management

`/api/v1/registration-management/` requires a Django session belonging to
staff, a superuser or a scoped admin, plus CSRF for every POST. Students and
supervisors cannot manage links. Suspended/deactivated managers are rejected.
Responses use `Cache-Control: no-store`.

| Request | Result |
| --- | --- |
| `GET` (optional `?page=2`) | Current year's window, count and up to 100 invitations, each with status, original token and copyable URL |
| `POST {"action":"invite","expires_at":"2026-10-16T04:30:00.123456Z"}` | HTTP 201, id, signed token, URL, expiry and status |
| `POST {"action":"revoke_invite","id":123}` | Revoked link; repeating is idempotent, a used link returns HTTP 409 |
| `POST {"action":"window","opens_at":null,"closes_at":"2026-10-01T00:00:00Z"}` | Updated current-year registration window |

Compute presets as **now + 24h / 47h / 7d / 14d** on the client and send the
absolute `expires_at`. There is no rounding to dates, whole days or hours.
Custom future timestamps preserve microseconds. Expiry is exclusive: a token
is invalid at `now == expires_at`.

Only a nonce and SHA-256 token digest are stored, not a bearer secret. The
signed payload binds the nonce, registration window and individual journey.
The same token is reconstructed for authorized management retrieval using
Django's stable production `SECRET_KEY`. Rotation invalidates old links;
management reports `signing_key_changed` with no token/URL. Revoke/reissue
those links. Do not log invitation headers, URLs or request bodies.

## Redemption contract

For normalized JSON, send session credentials, `X-CSRFToken`, a UUID
`Idempotency-Key`, and, when using a late link, `X-Registration-Invitation`.
Obtain a CSRF cookie/token from `GET /api/v1/services/csrf/`, including for
anonymous student intake.
Late links still authorize only one `student_individual` submission; they do
not bypass the window for a team or supervisor batch.

```json
{
  "journey": "student_individual",
  "payload": {
    "students": [{
      "firstName": "Jordan", "lastName": "Lee",
      "email": "jordan.lee@example.com",
      "school": "Example High", "yearLevel": "10",
      "country": "Australia", "state": "NSW",
      "interests": ["Biotechnology"],
      "guardianDeferred": false,
      "guardian": {
        "firstName": "Taylor", "lastName": "Lee",
        "email": "guardian@example.com", "relationship": "Parent"
      },
      "overrides": {}
    }],
    "source": {"method": "student_individual"},
    "supervisorMode": "school",
    "supervisor": {
      "firstName": "Sam", "lastName": "Teacher",
      "email": "teacher@example.com", "school": "Example High"
    }
  }
}
```

The nominated supervisor is required for public individual/team intake; mode defaults to
`school`. `parent` mode permits a blank supervisor school, but the supervisor
must match the named guardian. Guardian contact is always required for
self-registration and for a team's creator. Supervisor journeys omit the
supervisor object; each complete student may set `guardianDeferred:true`.
Teams/groups supply `group:{"interests":[...]}` and empty personal-interest
arrays. CSV source metadata supplies `fileName` and one unique, ordered
`rowNumbers` entry for each included student. Optional guardian phone/relationship
details, pronouns, grouping preference and personal interests are retained per student.

If supplying a photo, use multipart `request` containing the same JSON and
actual files in indexed fields `students.N`, at most one per student.
Metadata alone is rejected. Main's shared
profile-image validator additionally checks PNG/JPEG/WebP MIME, signatures and
decoded content, with a 5 MB limit and decompression-bomb protection. Files
use the existing managed local/Azure storage abstraction and are deleted on
failed persistence.

A new normalized registration returns **HTTP 201** and a saved receipt:
`{reference_code,journey,student_count,created_at}` matching the saved batch size. An unchanged retry
returns **HTTP 200** with exactly the same receipt, even after expiry or use.
Keys bind the request, actor, invitation digest and actual photo bytes.
Changed data/actor/token with an existing key returns HTTP 409. A different
key cannot reuse a link.

Validation reuses the role/email, guardian, known-university and name/email
checks from `registration-validation-v2` (`34a0d177`). Both legacy validation
and the adapter use one shared soft-warning helper. Hard errors return field
paths without warnings. Soft HTTP 400 responses include all unacknowledged
`warnings:[{code,field,override_field,message}]`, using the original `students.N.*`
indices. All students' hard checks run before any soft warnings are returned.
Only literal boolean `ConfirmSchoolOverride` and
`ConfirmNameEmailOverride` flags under `students.N.overrides` are accepted;
they never override hard errors. Failures and warnings do not consume links.

Intake and management lock the current registration-year row before the
invitation, recheck idempotency after waiting, and save every student, group, receipt
and consumption in one transaction. A failure on any row or later photo rolls
back the entire batch and removes files already saved. A final conditional update guards
against revocation, expiry or use during processing. Unique constraints
protect email, idempotency key, student receipt and invitation receipt.

## Compatibility and deployment

Existing `{body: ...}` student callers keep the same endpoint and HTTP 200
body echo on first success. They now receive real validation and the same
registration-window/invitation gate. Anonymous legacy submissions retain
their historical CSRF behavior; authenticated legacy writes still require
session CSRF. Optional idempotency keys return a receipt on unchanged retry.
`RegisteredBy` cannot make a public self-registration skip guardian contact.
Normalized individual students and team creators are recorded as `self`, represented
teammates as `peer`, and authenticated supervised intake as `supervisor`. Legacy provenance
labels retain main's existing detail-lock semantics; they are not an
authorization mechanism and do not change validation or grant any role.

Registration creates only a **pending student** with an unusable password,
the target's existing six-week student assignment, and **no guardian consent**.
It never activates an account or creates a supervisor/admin role. Supervisor
contacts are retained on the receipt for the existing staff invitation
workflow; an existing supervisor profile may be linked without modifying
that person's name, school, geography or role. Unlike the unsafe legacy
side effect, an unknown supervisor nomination does not create an account.
Registration does not send approval/invitation email or simulate those flows.
Staff must provision unknown supervisors through the existing protected
workflow, and guardian permission remains the real existing consent process.

Before deployment:

1. Install `backend/requirements.txt` and apply through `users.0025_registration_multi_student`
   with the normal `manage.py migrate` deployment step.
2. Configure the **registration** year's opening/closing timestamps via the
   management endpoint. Unconfigured/null boundaries deliberately retain the
   legacy open default; task/challenge deadlines do not close registration.
3. Keep a stable production `SECRET_KEY`, correctly configured session/CSRF
   origins, frontend base URL and shared throttle cache. The gateway's two
   custom headers are included in the CORS allowlist.
4. For photos, provision the private Azure `AZURE_PROFILE_IMAGE_CONTAINER`
   (default `profile-images`) and its normal managed-storage credentials.
5. Deploy all five student journeys with this adapter. Mentor applications
   still require a separate backend implementation; do not advertise that flow as operational.

### Migration compatibility with main

`0024_registration_latelink` depends on main's `0023_load_areas_of_interest`
leaf and adds `User.pronouns` and the three registration models. Main already owns
`KnownUniversity` (`0019_known_university`), the private profile-image columns
(`0012_user_profile_image`, lengths/defaults unchanged), and all later guardian,
consent and supervisor migrations. Their data and history are preserved.

`0025_registration_multi_student` follows `0024` and main's groups leaf. It adds
ordered registration participants, saved batch size and the optional real group.
Existing single-student receipts are backfilled with one participant, retaining
their original receipt, metadata and retry digest. The legacy primary-student
relation remains compatible. Only represented peers may have blank school/year;
only represented peers/supervised students without a guardian-on-file flag may
have blank guardian names. Self-registration remains strict, and the database's
consent-requires-guardian constraint is unchanged. Main migrations are not rewritten.

Do **not** also copy/apply the source PR's old `0012_registration_latelink`:
that parallel branch would duplicate main's university table and photo fields.
No existing main migration is rewritten, no fake migration is required, and
there is one users leaf. A deployment already running the separate source
branch needs a reviewed migration reconciliation plan before switching; do not
mark unapplied schema changes as applied.

Verify both a fresh disposable database and an upgrade from the complete
pre-`0024` users/dependency graph using real migrations (the standard test settings disable
migrations, so unit tests alone do not prove this). Check preserved users,
profile-image keys/content types, university aliases and guardian/consent state.
Rollback removes intake history and pronouns, not main's photo/university schema.
Before rolling back `0025`, reconcile/export multi-student receipts and complete
any partial profiles: older constraints cannot represent those new records.

An unrestricted fresh migration of this main baseline also encounters an
unrelated existing blocker in `submissions.0013_submission_cohort`: its callable
default queries the current deadline model before `set_by_id` is added by
`submissions.0016`. The fresh users/dependency graph and its `0023 -> 0024`
upgrade through `0025` can be verified independently; this change does not rewrite that
submission migration or fake its application. A completely empty deployment
needs that baseline issue resolved separately.

Focused checks use the isolated repository test settings:

```powershell
.\.venv\Scripts\python.exe backend\manage.py test tests.apps.users.test_registration_latelink tests.apps.users.test_registration_multi_student tests.apps.users.test_users --settings=config.settings_test
```

The suite covers real saved redemption, CSRF, manager permissions, exact
expiry/window boundaries, revocation/reuse/wrong journeys, hard/soft failures,
idempotency, photo bytes/storage rollback and database uniqueness. The
`PostgreSQLRaceTests` use two independent connections and actual concurrent
requests; they require an **isolated PostgreSQL test database** and are
explicitly skipped on SQLite (which cannot exercise row locks). Never run
these checks against a shared demo or production database.

No supervisor late grants, management UI, mentor adapter, fixture
datasets, demonstration server, or unrelated dashboard/deadline work is included.
