# E2E: the ticket lifecycle

`tickets.spec.ts` drives a student through the Vue portal and a support
agent through the React admin app against one real backend. It covers the
core support chain: raise, internal note, reply, resolve, student reads it
(and cannot read the note), reply again, auto-reopen.

## What must be running first

Playwright starts nothing when `E2E_PORTAL_URL` is set. Start three
servers yourself, all pointed at one database:

```bash
# backend (any port; the two dev servers must point at it)
python manage.py migrate
python manage.py seed_e2e          # the accounts the spec logs in with
python manage.py runserver 8002

# portal
VITE_API_BASE_URL=http://localhost:8002 pnpm --dir frontend exec vite --port 5175 --strictPort

# admin app
VITE_PUBLIC_API_URL=http://localhost:8002 pnpm --dir adminweb exec vite dev --port 3002 --strictPort
```

Then:

```bash
cd frontend
E2E_PORTAL_URL=http://localhost:5175 E2E_ADMIN_URL=http://localhost:3002 \
  pnpm exec playwright test --project=chromium
```

CORS: the backend must allow the two dev-server origins, or every login
fails. In the rehearsal that lives in the out-of-repo settings module.

Without `E2E_PORTAL_URL`, Playwright falls back to the scaffold behaviour:
it starts the portal dev server itself on 5173 and only `vue.spec.ts` can
pass, because nothing started a backend or the admin app.

## Why two browser contexts

Both apps talk to the same backend host, and cookies ignore ports: one
shared context would let the agent's login silently replace the student's
session mid-test. Each persona gets its own context (its own cookie jar).

## The accounts

`seed_e2e` (DEBUG-only, idempotent) creates:

| who | email | password |
|---|---|---|
| student | e2e.student@example.com | E2eStudent1! |
| support agent (not admin) | e2e.agent@example.com | E2eAgent1! |

Every run raises a fresh ticket (subject carries a timestamp), so the suite
does not depend on database cleanup between runs.
