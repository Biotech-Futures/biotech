# Ticket System (`apps.tickets`)

Support enquiries. Any signed-in user raises a ticket from the portal's Support page and follows it there. Support agents work a shared queue at `/admin/tickets` in the Vue portal. AI message screening (`apps.chat`) also opens tickets here. Built by Team 2 (COMP3888, 2026); merged in PRs #549 and #563.

## Map

| Path | What it holds |
|---|---|
| `models/ticket.py` | `Ticket`, and the `TicketStatus`, `TicketPriority`, `TicketCategory`, `TicketChannel` choices |
| `models/ticket_message.py`, `ticket_attachment.py` | Conversation rows (`user_message`, `support_reply`, `internal_note`, `system`) and their files |
| `models/ticket_counter.py`, `services/numbering.py` | `SUP-<year>-<5 digits>` numbers, one counter row per year, allocated under `select_for_update` |
| `models/support_scope.py` | `SupportScope`: one row = this user may work the queue (admins need no row) |
| `services/lifecycle.py` | **Every** state change: create, claim/assign, replies, notes, resolve, reopen, set status, soft delete |
| `services/queue.py` | Queue filters, the overdue condition, the four counters |
| `services/paging.py` | Snapshot paging (`asOf` + `after`) so rows don't jump between pages |
| `services/emails.py` | The six emails (E1 to E6) and the daily digest |
| `services/handoff.py` | `create_ticket_from_screening`: the interface AI screening calls. Keep its signature stable |
| `services/attachments.py` | Upload limits and storage (chat container, `tickets/` prefix) |
| `services/analytics.py`, `export.py`, `audit_export.py` | Analytics page, xlsx exports |
| `services/system_messages.py` | The grey system lines shown in the conversation |
| `bidi.py` | Strips right-to-left control characters from user text |
| `views.py` + `urls.py` | Requester API, `/api/v1/tickets/` |
| `views_admin.py` + `urls_admin.py` | Agent API, `/api/v1/admin/tickets/` |
| `permissions.py` | `is_support()`, `IsSupportScoped` |
| `templates/emails/` | Email templates; the editable copies live in System Emails |
| `management/commands/seed_e2e.py` | Seeds the scratch database for `frontend/e2e/tickets.spec.ts` |

Frontend: see `frontend/src/components/admin/tickets/AGENTS.md`.

## Rules

1. **Never set `ticket.status`, `assignee` or the clock fields in a view or serializer.** Call the matching function in `services/lifecycle.py`. It writes the audit row, the system message, the clock fields and the emails together. Transitions are labelled T1 to T8 in that file.
2. **Two "updated" times on purpose.** `updated_at` is what the requester sees; `support_updated_at` is the queue's sort key. Internal notes and triage move only `support_updated_at`, so a requester never sees activity they cannot read.
3. **Requesters must never see internal notes.** The requester serializers drop `internal_note` rows. Any new requester-facing field must be checked for leaks; `tests/apps/tickets/test_api_user.py` has the guards.
4. **Another user's ticket answers 404, not 403**, so ticket ids cannot be probed.
5. **Emails go out after commit** (`transaction.on_commit(..., robust=True)`) through `send_system_email`. Sending never raises: a failed send only shows as an `auth_email.send_failed` log line. Do not treat an HTTP 201 as proof that mail was sent.
6. **E4 and E6 never include the message text**: the support inbox is a shared mailbox, and the text may come from a minor.
7. **Region is a snapshot** of the requester's country at creation. It is used for filters and analytics only; nothing routes or assigns by region.
8. **The overdue clock** is computed at read time from `awaiting_support_since` and `TICKET_SLA_*_HOURS` (4/24/72, wall-clock). Support replies stop it; `pending_user` and `resolved` pause it; claim, assign, notes and priority changes do not touch it.
9. **Times:** stored in UTC. The frontend shows them in the viewer's Profile time zone (browser zone if the Profile says UTC) and passes that zone to `analytics/` and the exports.
10. **Support access** is granted by creating a user with role `support`, by changing a role to or from support, or by the admin-only `support-scope/` endpoints. Students cannot be granted it. All of these are audited.

## Changing things safely

- **New status or transition:** add it in `lifecycle.py`, the system message in `system_messages.py`, the frontend labels, and tests in `test_lifecycle.py` and `test_api_admin.py`. Check the overdue pause rules.
- **New email:** register it in `apps/services/email_registry.py` with `default_sender="support"`, add a template here, and add tests in `test_emails.py` or `test_support_inbox_emails.py`. If the System Emails editor must render it, build optional sentences in Python: an `{% if %}` in an edited copy is always true.
- **New migration:** production runs `migrate --noinput` at start-up and a failure takes the site down. Run `makemigrations --check` and a migration from an empty database before merging.
- **Times in tests:** CI reruns the suite with the clock moved 400 days ahead and to New Year (`tests.clock.ShiftedClockRunner` with `TEST_CLOCK_SHIFT_DAYS=400` or `TEST_CLOCK_AT=new-year`). Do not hard-code dates.

## Tests

- Backend: `backend/tests/apps/tickets/` (about 740 tests; the largest is `test_api_admin.py`). Run with `python manage.py test tests.apps.tickets --settings=config.settings_test`; CI also runs them on PostgreSQL.
- Use `encoding="utf-8"` whenever a test reads a file: Windows machines with a non-UTF-8 locale otherwise fail.
- End-to-end: `frontend/e2e/tickets.spec.ts`; see `frontend/e2e/README.md`.

## Scheduled job

The daily digest (E5) is triggered by `.github/workflows/ticket-digest.yml` at 9:00 Australia/Sydney, calling `POST /api/v1/admin/tickets/digest/send/` with header `X-Email-Jobs-Token` (`EMAIL_JOBS_TOKEN`). GitHub does not run schedules on time: in the week to 1 November 2026 the digest went out between 1 h 50 min and 3 h 35 min late every day. The platform's own jobs moved to the in-app scheduler (`apps/management/scheduler.py`) on 22 October; moving the digest there is issue #575.

## Not built, on purpose

- **Inbound email.** `TicketChannel.EMAIL` is reserved. Replies are made in the portal only; the client confirmed this.
- No auto-close, no satisfaction survey, no business-hours SLA, no ticket restore, and no delete button in the UI (the API delete is admin only).
- The old support roster page was removed at the client's request (C-15); the `support-scope/` endpoints remain.

## Known stale comment

`bidi.py:86-90` says `create_ticket_from_screening` has no caller. `apps/chat/services/screening.py` calls it now.
