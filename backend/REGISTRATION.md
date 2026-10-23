# Student registration and late links

The consolidated frontend/backend change on current `main` implements **five student journeys** at
`POST /api/v1/registration` (both slash variants and `registration-intake/`
are aliases). Mentors register at the same endpoint with `journey: "mentor"`
(normalized JSON only, no legacy fallback); see
[Mentor registration](#mentor-registration). It combines the
full `registration` branch and the production changes from frontend #475 and
backend #476. Registration history is retained while its older frontend wiring
is reconciled with current main and the newer intake contract.

| Journey | Students | Authorization and persistence |
| --- | --- | --- |
| `student_individual` | 1 | Public; complete student and guardian details |
| `student_team` | 2-5 | Public; complete creator, pending identity-only peers, real group and shared interests |
| `supervisor_individual` | 1 | Current supervisor session/profile; optional deferred guardian |
| `supervisor_group` | 2-5 | Current supervisor session/profile; real group and shared interests |
| `supervisor_csv` | 1-1000 | Current supervisor session/profile; atomic batch with original CSV row numbers |

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
Only literal boolean `ConfirmSchoolOverride`, `ConfirmNameEmailOverride`,
`ConfirmEmailInvalidOverride` and `ConfirmGuardianEmailInvalidOverride` flags
under `students.N.overrides` are accepted (the last two are described under
[Email check before submission](#email-check-before-submission)); they never
override hard errors. Failures and warnings do not consume links.

Intake and management lock the current registration-year row before the
invitation, recheck idempotency after waiting, and save every student, group, receipt
and consumption in one transaction. A failure on any row or later photo rolls
back the entire batch and removes files already saved. A final conditional update guards
against revocation, expiry or use during processing. Unique constraints
protect email, idempotency key, student receipt and invitation receipt.

## Mentor registration

A mentor applies on the public registration page. `register()` hands
`journey: "mentor"` to `apps/users/mentor_registration.py` before any student
handling. The request needs the same session, `X-CSRFToken` and UUID
`Idempotency-Key` as a student's, and no files.

```json
{
  "journey": "mentor",
  "payload": {
    "mentor": {
      "firstName": "Jordan", "lastName": "Ng", "email": "jordan.ng@example.com",
      "country": "Australia", "state": "NSW",
      "affiliation": "postgraduate", "institution": "University of Sydney",
      "company": "", "universityYear": "2", "fieldOfStudy": "Bioengineering",
      "interests": ["Biomedical Innovations"],
      "capacity": "3", "motivation": "..."
    }
  }
}
```

| Field | Rule |
| --- | --- |
| `firstName`, `lastName` | Required, up to 150 characters |
| `email` | Required email, up to 254 characters; saved in lower case |
| `country` | Required |
| `state` | Required when the country is Australia |
| `affiliation` | `undergraduate`, `postgraduate`, `hdr`, `academic` or `industry` |
| `company` | Required for `industry` |
| `institution`, `fieldOfStudy` | Required unless `industry` |
| `universityYear` | `1` to `4` or `5+`; required for `undergraduate` and `postgraduate` |
| `interests` | At least one, at most 100 |
| `capacity` | `1` to `5`; becomes the mentor's maximum number of groups |
| `motivation` | Required, 150 words at most (split on spaces, as the form counts them) |
| `availability` | Optional weekly slots `{weekday: "0"-"6" (Monday is 0), start, end}` as `HH:MM`; the form no longer sends them, but they're saved when given |

Unknown fields are refused, including `weeklyHours`, `background` and
`mentoringApproach`, which the form no longer asks for. Every rule the form
checks is checked again here, and each error comes back on its own field
(`mentor.<field>`).

A mentor is saved in one transaction:

- an account that is **pending and inactive** (no password), so they can't
  sign in until an admin activates them on Admin > Mentors;
- the `mentor` role from now, with **no end date**;
- a mentor profile with every field above (the motivation is
  `mentor_reason`);
- their interests (a name not already listed is added) and any weekly slots.

The answer is the usual receipt with **`student_count: 0`**:
`{reference_code, journey: "mentor", student_count: 0, created_at}`, HTTP 201,
or HTTP 200 with the same receipt for an unchanged retry. A changed request
with a used key returns HTTP 409, and the per-IP limit returns HTTP 429, as for
students. A retry still gets its receipt when the limit is reached.

Mentors follow the student registration dates: when registration is closed the
answer is "Registration is closed". Late links are for `student_individual`
only, so a mentor request carrying one is refused, and the supervisor
exception after close doesn't apply. An email that already has an account
(student, supervisor or anyone else) is refused on `mentor.email`.

Once the save commits, the mentor gets the **Registration confirmation (to
mentor)** email (the `registration_mentor` template, System Emails > Registration).

Mentors aren't covered by the name/email typo warning, or by the
[email check before submission](#email-check-before-submission).

## Email check before submission

Before a registration is submitted, the page can check that its students' and
guardians' email addresses exist (QuickEmailVerification), so the person
registering can correct one while they're still on the form. It is off unless
`EMAIL_PRECHECK_ENABLED` is true, and it never holds a registration up: any
time it can't run, the page submits as it would without it.

### How it works

1. The page sends the registration to `POST /api/v1/registration/email-check/`.
2. The backend starts a job checking every address without a recent answer on
   file, and the page polls `GET /api/v1/registration/email-check/<jobId>/`
   about once a second, showing its progress.
3. When the job is done, the page submits the registration as usual.
   `register()` then warns about any address QuickEmailVerification answered as
   not existing (see [The two warnings](#the-two-warnings)), and the person
   corrects it or confirms it.
4. Every submit runs the check again, so a corrected address is checked before
   it's resubmitted. Addresses already answered come back at once.

### Starting a check

`POST /api/v1/registration/email-check/` takes the same normalized
`{journey, payload}` as the intake endpoint, with the same session and CSRF
token, and an `X-Registration-Invitation` header for a late link (checking does
not use the link up). Photos are not sent. Mentor registrations aren't checked:
the page skips the check for them, and this endpoint refuses `journey: "mentor"`.

| Response | Meaning |
| --- | --- |
| `202 {"status": "started", "jobId", "total", "done"}` | A job is checking `total` addresses; `done` already have an answer on file or were skipped. |
| `202 {"status": "done", "jobId", "total", "done"}` | Nothing needed checking (all answered already, or all over the budget). |
| `200 {"status": "disabled"}` | `EMAIL_PRECHECK_ENABLED` is off. |
| `200 {"status": "closed"}` | Registration isn't open: no open window, no valid late link, and not a supervisor allowed to register after close. |
| `200 {"status": "too_many"}` | More addresses than one request may carry (see [Limits](#limits)). |
| `400` field errors | The registration itself is invalid (submitting it would be refused too). |
| `403` | A supervisor journey without a current supervisor session. |

Every address is lower-cased and checked once, students' and guardians' alike.

### Polling a check

`GET /api/v1/registration/email-check/<jobId>/` returns

```json
{"status": "running", "total": 260, "done": 112, "invalid": 3, "errors": 0,
 "skipped": 0, "estimatedSecondsRemaining": 47}
```

| `status` | Meaning |
| --- | --- |
| `queued` | Waiting for earlier checks before its first address starts. `estimatedSecondsRemaining` is `null`. |
| `running` | Checking. `estimatedSecondsRemaining` is the time left (below). |
| `done` | Finished; `estimatedSecondsRemaining` is `0`. |
| `failed` | The job couldn't be handed to the workers. |
| `stalled` | A running job that hasn't moved for `EMAIL_PRECHECK_STALL_SECONDS`, or a queued one that hasn't started within `EMAIL_PRECHECK_QUEUED_STALL_SECONDS` (a restart loses a job). `estimatedSecondsRemaining` is `null`. |

`invalid` counts addresses answered as not existing, `errors` addresses that
couldn't be checked (they pass), and `skipped` addresses left unchecked because
they were over the hourly budget (they pass too). An unknown job is
`404 {"status": "not_found"}`; with the switch off, `200 {"status": "disabled"}`.

`estimatedSecondsRemaining` is the addresses still to check, times the job's
average seconds per lookup so far (an assumed 2 seconds before its first
lookup), divided among the workers, rounded up. When fewer addresses are left
than there are workers, they run side by side, so it's divided by those left.

A job keeps counts only, never the addresses, and is deleted a day after it
starts. Each answer is kept as an `EmailVerification`, which is what
`register()` reads.

### Limits

- **Open registration only.** The same gate as submitting: an open window, a
  valid late link, or a supervisor allowed to register after close.
- **Addresses per request.** At most `EMAIL_PRECHECK_MAX_ADDRESSES` (2000)
  when signed in, and `EMAIL_PRECHECK_ANONYMOUS_MAX_ADDRESSES` (20) when not.
  Over the limit, the answer is `too_many` and nothing is checked.
- **Hourly lookups per IP address.** Anyone not registering as a supervisor
  may cause at most `EMAIL_PRECHECK_IP_HOURLY_LOOKUPS` (200) new lookups an
  hour from one IP address; addresses over that are left unchecked
  (`skipped`). Supervisor journeys (a signed-in supervisor or admin) aren't
  held to it. Answers already on file cost nothing and don't count.
- **No address is paid for twice.** An answer younger than
  `QEV_RESULT_MAX_AGE_DAYS` is reused, and an address another job is already
  checking is waited for rather than looked up again.
- **Workers.** Addresses are checked one per lookup (the free key can't use
  QuickEmailVerification's bulk API) on a pool of threads sized by
  `QEV_PRECHECK_WORKERS`. When QuickEmailVerification answers 429 (too many
  requests), every worker pauses, for 1, 2, 4, 8 then 16 seconds, after which
  the address counts as not checked. Jobs are taken in the order they arrive,
  so a job behind a large one may show as `queued` for a while.

The per-IP budget, the "already checking" guard and the 429 pause are kept in
the Django cache, so they are shared between server processes only when
`REDIS_URL` is set.

### The two warnings

With `EMAIL_PRECHECK_ENABLED` on, `register()` looks up every student's and
guardian's stored answer in one query per submission. An address whose answer
is "invalid" and younger than `QEV_RESULT_MAX_AGE_DAYS` gets a soft warning,
shaped like the others:

| `code` | `field` | `override_field` |
| --- | --- | --- |
| `email_invalid` | `students.N.email` | `students.N.overrides.ConfirmEmailInvalidOverride` |
| `guardian_email_invalid` | `students.N.guardian.email` | `students.N.overrides.ConfirmGuardianEmailInvalidOverride` |

The message reads "This email address doesn't appear to exist." (or "The
guardian's email address…"), adding "Did you mean ‹address›?" when
QuickEmailVerification suggested one. A valid, unknown, missing or older
answer gives no warning: an address that couldn't be checked is never
blocked. Confirming the warning (the override set to `true`) lets it through
and leaves nothing behind for staff. Legacy `{body: ...}` callers can send the
same two flags. With the switch off there are no email warnings, even for
answers on file.

### What the page does

The page runs the check before every submit, through the production gateway
only (`configuredRegistrationGateway`, which derives the check's address from
the registration endpoint). While it runs, the form shows "Waiting for earlier
checks to finish…" with an indeterminate bar while the job is `queued`, then
"12 of 260 checked · About 1 min 15 s left" with a bar while it's `running`.

The page skips the check and submits exactly as it would without it whenever:
the answer has no `jobId` (`disabled`, `closed`, `too_many`); the start request
fails (any other status, or an unreadable answer); the job becomes `failed`,
`stalled` or `not_found`; a poll fails or can't be read; the network is down;
or a secure session can't be set up. After a `disabled` answer the page doesn't
ask again until it's reloaded. The warning box shows the new warnings like the
others, labelled "Student email" or "Guardian email".

### Turning it on

1. Apply the migrations through `users.0034_email_check_job` (`0026`, `0027`
   and `0032`-`0034` add the email verification answers, credit balance and
   check jobs).
2. Set at least one QuickEmailVerification key in the deployment's
   environment (never in the repository): `QEV_API_KEY` (the free key, tried
   first) and/or `QEV_PAID_API_KEY` (used when the free key is out of credit).
3. Set `REDIS_URL`, so the limits and the guard are shared between processes.
4. Deploy the frontend with the email check (the page and its gateway).
5. Set `EMAIL_PRECHECK_ENABLED=true`. Until it is, the endpoints answer
   `disabled`, `register()` gives no email warnings, and the page submits
   without checking.

To try it without spending credits, set `QEV_USE_SANDBOX=true`: lookups go to
QuickEmailVerification's free sandbox, which answers by the test address used
(for example `rejected-email@example.com` is invalid).

### Settings

| Setting | Default | What it does |
| --- | --- | --- |
| `EMAIL_PRECHECK_ENABLED` | `false` | Turns the check and its warnings on. |
| `EMAIL_PRECHECK_MAX_ADDRESSES` | 2000 | Addresses one signed-in request may carry. |
| `EMAIL_PRECHECK_ANONYMOUS_MAX_ADDRESSES` | 20 | Addresses one request may carry when not signed in. |
| `EMAIL_PRECHECK_IP_HOURLY_LOOKUPS` | 200 | New lookups one IP address may cause an hour (not for supervisor journeys). |
| `EMAIL_PRECHECK_STALL_SECONDS` | 60 | A running job that hasn't moved this long is `stalled`. |
| `EMAIL_PRECHECK_QUEUED_STALL_SECONDS` | 300 | A queued job not started this long is `stalled`. |
| `QEV_PRECHECK_WORKERS` | set in `config/settings.py` | Threads checking addresses, one each. |
| `QEV_API_KEY`, `QEV_PAID_API_KEY` | blank | The free and paid keys; with neither set, nothing is looked up. |
| `QEV_EXHAUSTED_RETRY_MINUTES` | 60 | A key out of credit is tried again after this, or at the next UTC midnight. |
| `QEV_RESULT_MAX_AGE_DAYS` | 180 | How long an answer is reused and can give a warning. |
| `QEV_DAILY_LOOKUP_CAP` | 0 | Lookups a UTC day; 0 means no limit. |
| `QEV_TIMEOUT_SECONDS` | 5 | How long one lookup may take. |
| `QEV_USE_SANDBOX` | `false` | Use QuickEmailVerification's free test endpoint. |
| `QEV_ALERT_EMAIL` | `info@biotechfutures.org` | Where low-credit alerts go (the paid key's balance, below 500 then 100). |

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
   legacy open default, except in a year Start new year began (Management >
   New Year), which stays closed until its opening date is set;
   task/challenge deadlines do not close registration.
3. Keep a stable production `SECRET_KEY`, correctly configured session/CSRF
   origins, frontend base URL and shared throttle cache. The gateway's two
   custom headers are included in the CORS allowlist.
4. For photos, provision the private Azure `AZURE_PROFILE_IMAGE_CONTAINER`
   (default `profile-images`) and its normal managed-storage credentials.
5. Deploy all five student journeys and the mentor journey with this adapter.
   Mentor registration needs `users.0032_mentor_registration` and
   `users.0033_mentor_weekly_hours` (joined to the email check migrations by
   `users.0035`).

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

No supervisor late grants, management UI, fixture
datasets, demonstration server, or unrelated dashboard/deadline work is included.
