# E2E: support tickets, both sides

`tickets.spec.ts` drives a student and a pure support agent through the Vue
portal against one real backend. Both sides live in the portal now: the
student in the Support Centre (`/#/support`), the agent in the ticket queue
(`/#/admin/tickets`, where `?ticket=<id>` opens the detail panel). The React
admin app is not involved and does not need to be running.

What it covers:

1. A student raises an enquiry with an attachment, sees it in their list, and
   its page shows the message with date and time and no automatic
   acknowledgement line (client items C-06, C-05).
2. A pure support agent lands on the queue, the sidebar offers the queue and
   none of the member pages, the ticket is in the queue, it opens by click and
   by keyboard, and its attachment downloads as a file.
3. Reply and wait for their reply, the student answers, back in progress,
   resolve, and a student reply reopens it.
4. Export to Excel: a real `.xlsx` of what the current filters match.
5. A student who opens the queue is sent to their own start page.
6. The stale-session guard that predates the port, in a real browser: two
   tabs in one browser, tab B signs out the student and signs in as the
   agent, and tab A's next write is refused with the "signed in as someone
   else" sentence. Two orderings (never reloaded, after a write of its own).
   Each one also checks through the API that nothing was filed under the
   agent. A tab reloaded before the takeover is not refused (T01); the owner
   ruled that out of scope on 2026-09-29, so it is not tested.

## What must be running first

Playwright starts nothing when `E2E_PORTAL_URL` is set. Start two servers
yourself, on a scratch database (never your working one: `seed_e2e`
overwrites passwords with published ones and refuses a database whose name
does not look like a scratch one):

```bash
# backend
cd backend
DB_NAME=biotech_e2e PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py seed_e2e --settings=config.settings_local
DB_NAME=biotech_e2e PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py runserver 8000 --settings=config.settings_local

# portal (its .env points it at http://localhost:8000)
cd frontend
pnpm dev
```

Then:

```bash
cd frontend
E2E_PORTAL_URL=http://localhost:5173 E2E_API_URL=http://localhost:8000 \
  PLAYWRIGHT_HTML_OPEN=never \
  pnpm exec playwright test --project=chromium --reporter=list
```

- Use `localhost`, not `127.0.0.1`: the Vite dev server listens on IPv6 only.
- `E2E_API_URL` must be the backend the portal was built against
  (`VITE_API_BASE_URL`). The specs read it directly to check what was, and
  was not, written.
- CORS: the backend must allow the portal's origin. `settings_local.py`
  allows 5173 and 3000 only; any other port fails every sign-in silently.
- No Chromium of the version this Playwright pins? Point
  `E2E_CHROMIUM_PATH` at any Chrome for Testing binary in
  `~/Library/Caches/ms-playwright/chromium-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`
  instead of running `playwright install`.
- Under the harness the browser is headless; add `--headed` to watch.
- When a test fails, the screenshot, console log and API traffic of every
  page it opened are written next to Playwright's own output
  (`test-results/`, or wherever `--output` points).

Without `E2E_PORTAL_URL`, Playwright falls back to the scaffold behaviour:
it starts the portal dev server itself on 5173 and only `vue.spec.ts` can
pass, because nothing started a backend. `tickets.spec.ts` skips itself.

## Why separate browser contexts, and why not in the stale-session tests

Every persona gets its own context (its own cookie jar). The portal and the
backend are on different ports of one host, and cookies ignore ports, so in
one shared context the agent's sign-in would silently replace the student's
session and every "the student sees X" after it would be testing the agent.

The stale-session tests do exactly that on purpose: two tabs, one context,
which is two people taking turns at one computer.

## The accounts

`seed_e2e` (DEBUG-only, idempotent, reruns heal drift) creates:

| who | email | password |
|---|---|---|
| student | e2e.student@example.com | E2eStudent1! |
| support agent (not admin) | e2e.agent@example.com | E2eAgent1! |

The agent is the account the People page makes for a support agent: queue
access (a SupportScope row) and the role `support`, not staff, not an admin.
The portal decides who an account is by its role, so without the role the
agent would land on the student dashboard.

Every test raises its own tickets with a subject no other run shares, so the
suite does not depend on database cleanup between runs. One full run raises
five. The backend throttles ticket creation to 30 an hour per requester; the
local cache is per process, so restarting the backend clears the count.
