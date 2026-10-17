# frontend

This template should help get you started developing with Vue 3 in Vite.

## Production registration

This merges the full `registration` branch and consolidates frontend #475 and
production backend #476 on current `main`, without replacing the application shell.
The original registration history is retained; its older route, authentication
and gateway code is reconciled with current main and the newer focused changes.
Registration uses the existing session authentication.
Student and mentor forms are public at `/#/register`; the existing supervisor
guard remains in force at `/#/supervisor/registration`. Public registration cannot
grant supervisor access. First-time supervisors are directed to request an invitation.

The HTTP gateway defaults to `/api/v1/registration`, without a trailing slash,
on the current origin or `VITE_API_BASE_URL`. `VITE_REGISTRATION_API_URL` can override
that endpoint. Requests include session credentials, CSRF and a UUID
`Idempotency-Key`; signed late-registration links provide
`X-Registration-Invitation`. Retries reuse the key only for an unchanged payload.
Photos are actual image files in multipart fields `students.N`, alongside a JSON
`request` field. No demo adapter, simulated receipt or legacy submission fallback is used.

The five student journeys send `{ journey, payload: { students, source,
supervisorMode?, supervisor?, group?: { interests } } }`. Mentor applications
send `{ journey: "mentor", payload: { mentor } }`. CSV imports preserve original
line numbers and exclusions. The downloadable template contains headers only;
multiple interests belong in one quoted comma-separated cell, with semicolon and
pipe separators also supported. New forms do not select a school-only or
cross-school preference; legacy CSV values remain readable without assigning a default.

Backend validation is authoritative. Only HTTP 201 and idempotent HTTP 200 with a
correlated receipt (`reference_code`, `journey`, `student_count`, `created_at`)
confirm success. HTTP 400 warnings must contain `code`, `field`, `override_field`
and `message`. Each warning requires explicit acknowledgement; only
`ConfirmSchoolOverride` and `ConfirmNameEmailOverride` are permitted. Editing
registration data clears acknowledgements. Hard field errors are displayed on
the relevant step or original CSV row and cannot be overridden.

The production backend supports all five student journeys. Student-created and
supervisor-created groups contain two to five students and persist real group
memberships and shared group interests. Authenticated supervisors can register
individuals, groups or up to 500 CSV students per request; supervisor identity
comes from the session, not the payload. CSV receipts preserve included rows'
original line numbers and individual grouping preferences.

Team creators provide complete details and guardian contact. Identity-only
teammates remain pending with unknown school/geography left blank, not invented.
Represented students may defer guardian details and complete them through the
existing protected profile/guardian workflows; registration never grants consent.
Every batch, receipt and photo is persisted atomically. Single-use late links
remain limited to `student_individual`; mentor intake still fails explicitly.
There is no fake runtime success or fallback to the legacy body endpoint.
See [backend deployment and migration guidance](../backend/REGISTRATION.md).

### Student adapter and future mentor extension

The individual adapter at `/api/v1/registration` preserves legacy `{body: ...}`
callers. It parses ordinary JSON or multipart `request` JSON and reuses current
main's `UserRegisterBodySerializer`, `KnownUniversity`, private photo storage,
and protected consent/authentication workflows. Supervisor journeys require a
current authorized supervisor account and existing profile. Their names, email
and school are resolved on the server; payload supervisor claims are rejected.

For each complete student, map the intake fields to the existing
`UserRegisterBodySerializer` input:

| Intake field                                                 | Existing validation field                                     |
| ------------------------------------------------------------ | ------------------------------------------------------------- |
| `students.N.email`                                           | `Title`                                                       |
| `students.N.firstName`, `lastName`                           | `FirstName`, `Surname`                                        |
| `students.N.country`, `state`                                | `Country`, `Region`                                           |
| `students.N.school`, `yearLevel`                             | `SchoolName`, `YearLevel`                                     |
| `students.N.interests`                                       | `Areaofinterest` (the adapter retains the full interest list) |
| `students.N.guardian.email`, `firstName`, `lastName`         | `GuardianEmail`, `GuardianName`, `GuardianSurname`            |
| Nominated or authenticated supervisor email, first/last name | `SupervisorEmail`, `SupervisorFirstName`, `SupervisorSurname` |
| Allowlisted `students.N.overrides` flags                     | `ConfirmSchoolOverride`, `ConfirmNameEmailOverride`           |

Normalized individual intake derives `RegisteredBy=Self` on the server. Legacy
provenance labels are retained for existing detail-lock behavior, but cannot
bypass the self-registration guardian checks or grant supervisor privileges.
The server derives `Self` for group creators, `Peer` for represented group
members, and `Supervisor` for supervised intake. Creators must provide guardian
contact. Identity-only peer records use a narrowly scoped partial validation
path and remain pending completion; school, country and interests are not
invented to satisfy the complete-record serializer. Group interests belong to
the group, not the creator's personal interests. Individual-student rules remain
strict. A supervised registration retains main's supervisor-owned detail lock.

The adapter explicitly validates through the shared serializer. School and
name/email checks use one shared helper for legacy and normalized validation.
Do not infer warnings by parsing error-message text, reproduce
edit-distance logic in the frontend, or bypass hard validation. Run hard checks
first, then return all unacknowledged warnings as HTTP 400 with canonical
`students.N.*` fields and the two allowlisted override paths. Return hard errors
without `warnings`; translate legacy fields back to intake field paths so the
frontend can focus the correct step and original CSV row.

The adapter persists the entire intake atomically, along with a real submission
receipt and ordered per-student intake metadata. Idempotency is scoped to the
actor/invitation and a digest of request data plus actual photo bytes:
unchanged retries return the existing receipt
with HTTP 200, changed data using the same key must fail, and new submissions
return HTTP 201. Validate images using the existing backend image validator.
Keep CSV `source.rowNumbers` aligned with the included student array. Mentor
applications need a separate validated, pending-review intake; the student
serializer is not a substitute for mentor validation.

Validate signed invitations, their expiry and permitted journey on the server.
Keep registration-window permissions separate from challenge/task deadlines.
Do not reuse the legacy view's account-creation side effects as validation:
supervisor invitations, role grants, activation and guardian permission remain
server-owned workflows, and registration itself must not confirm consent.
The included `backend/apps/users/registration_intake.py` and its tests define
the five student journeys' shared wire contract. Mentor intake is not implemented.

Late invitations are accepted and restricted to one student. Staff/admin
management is available through the session/CSRF-protected
`/api/v1/registration-management/` API, including exact custom expiry suitable
for 24h, 47h, 7d and 14d links. No management frontend or late-supervisor grants
are included.
Registration-window controls must remain separate from other program deadlines;
current main's dashboard, admin and supervisor screens remain intact.

## Recommended IDE Setup

[VSCode](https://code.visualstudio.com/) + [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Type-Check, Compile and Minify for Production

```sh
npm run build
```

### Run Unit Tests with [Vitest](https://vitest.dev/)

```sh
npm run test:unit
```

### Run End-to-End Tests with [Playwright](https://playwright.dev)

```sh
# Install browsers for the first run
npx playwright install

# When testing on CI, must build the project first
npm run build

# Runs the end-to-end tests
npm run test:e2e
# Runs the tests only on Chromium
npm run test:e2e -- --project=chromium
# Runs the tests of a specific file
npm run test:e2e -- tests/example.spec.ts
# Runs the tests in debug mode
npm run test:e2e -- --debug
```

### Lint with [ESLint](https://eslint.org/)

```sh
npm run lint
```

## Setup with Docker (Optional)

### Build the Docker image

```sh
docker build -t vue-dev .
```

### Run the Docker container

#### Linux / MacOS

```sh
docker run --rm -it -p 5173:5173 -v "$PWD":/app -v /app/node_modules vue-dev
```

#### Windows (PowerShell)

```sh
docker run --rm -it -p 5173:5173 -v ${PWD}:/app -v /app/node_modules vue-dev
```
