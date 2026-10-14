# frontend

This template should help get you started developing with Vue 3 in Vite.

## Production registration

Registration uses the existing application shell and session authentication.
Student and mentor intake is public at `/#/register`; the existing supervisor
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

**Deployment dependency:** both this branch and the latest locally fetched
BioTech `origin/main` (`d83d6a27`) expose a `{ body: ... }` single-student view,
not the approved multi-journey intake. Keep all approved frontend journeys, but
provide a separate backend adapter before deploying them. That adapter must
reuse the latest `UserRegisterBodySerializer` validation in
`backend/apps/users/serializers.py` from `registration-validation-v2`
(`34a0d177`, already merged into `main`; the registration validator is unchanged),
including its school/name-email override
rules and optional guardian rules for represented students, rather than
duplicating or weakening those checks. The approved adapter contract is
demonstrated by local reference commit `62511f7c`; it is not included in this
frontend-only change. The frontend does not fabricate a receipt or downgrade
to the incompatible single-student endpoint.

### Wiring the backend adapter to existing validation

Add an intake adapter at `/api/v1/registration` without replacing existing
single-student callers. Parse ordinary JSON or the multipart `request` JSON
part, then validate the journey, student count, source metadata and files.
Resolve authenticated supervisor identity on the server; never trust a
client-supplied supervisor identity for supervisor journeys.

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

Derive `RegisteredBy` on the server: `Self` for individual students and group
creators, `Peer` for represented group members, and `Supervisor` for supervised
intake. Creators must provide guardian contact. Identity-only peer records may
use a deliberately partial validation path and remain pending completion;
do not invent school, country or interests to satisfy the complete-record
serializer. Group interests belong to the group, not the creator's personal
interests. Add a narrowly scoped group-interest validation context rather than
relaxing the existing individual-student rules.

Explicitly call serializer validation; declaring `serializer_class` alone is
not sufficient. Extract the existing school and name/email warning checks into
one shared backend helper used by both the legacy serializer and the new
adapter. Do not infer warnings by parsing error-message text, reproduce
edit-distance logic in the frontend, or bypass hard validation. Run hard checks
first, then return all unacknowledged warnings as HTTP 400 with canonical
`students.N.*` fields and the two allowlisted override paths. Return hard errors
without `warnings`; translate legacy fields back to intake field paths so the
frontend can focus the correct step and original CSV row.

Persist the entire group or CSV intake atomically, along with a real submission
receipt. Scope idempotency to the actor/invitation and a digest of normalized
data plus actual photo bytes: unchanged retries return the existing receipt
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
Reference `registration_intake.py` and its adapter tests in local commit
`62511f7c` for the wire contract, but port only the required adapter in a
separate backend change rather than merging that branch's unrelated history.

Late invitations are accepted and restricted to one student. Late-registration
management (including custom expiry and 24h, 47h, 7d and 14d create-and-copy links)
is not included: this target has no compatible management route or API.
Registration-window controls must remain separate from other program deadlines;
no dashboard, admin or deadline management screens have been imported.

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
