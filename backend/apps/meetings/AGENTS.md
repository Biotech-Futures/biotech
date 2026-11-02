# Group Meeting Workspace (`apps.meetings`)

A group's mentor schedules online meetings for the group. Members see them, edit one shared note together in real time, and read the mentor's summary. Built by Team 2 (COMP3888, 2026); merged in PR #549, permissions changed in PR #562.

## Map

| Path | What it holds |
|---|---|
| `models/group_meetings.py` | `GroupMeeting`: one-to-one with an `events.Events` row, plus `group`, `organiser`, `agenda` |
| `models/meeting_note.py` | `MeetingNote`: `ydoc_state` (CRDT bytes), `body` (plain-text snapshot), `revision` |
| `models/meeting_summary.py` | `MeetingSummary`: `body`, `author`, `published_at` (null = draft) |
| `permissions.py` | Who can manage and who can read |
| `services.py` | Create/update/cancel (writes the Event, target group and RSVPs), note merge and load |
| `views.py`, `serializers.py`, `urls.py` | REST at `/api/v1/meetings/meetings/` |
| `consumers.py`, `routing.py` | WebSocket `ws/meetings/<id>/note/` for the shared note |
| `utils.py` | `detect_provider`: Zoom, Google Meet, Teams or other, from the link's host |

Frontend: `frontend/src/views/GroupMeetingsPage.vue`, `frontend/src/views/GroupMeetingDetailPage.vue`, `frontend/src/utils/meetingsAPI.ts`, logos in `frontend/src/assets/meeting-providers/`.

## Who can do what (`permissions.py:32-40`)

| Role | Manage (create, edit, cancel, summary) | Read, edit the shared note |
|---|---|---|
| Admin | Yes | Yes |
| Mentor **of this group** (`GroupMembership.membership_role`) | Yes | Yes |
| The meeting's organiser | Yes, even after they stop being a mentor | Yes |
| Other group members, including supervisors | No | Yes; summary only once published |
| Anyone else | No (REST 404) | No (WebSocket closed with 4403) |

The role is **per group**, not the user's global role. Supervisors became read-only in PR #562; the comments at `permissions.py:33` and `views.py:83` that still say "mentor or supervisor" are stale.

## Design

- **Time and place live on the Event.** `services.py` writes `start_datetime`, `ends_datetime`, `event_timezone`, `location_link` and `event_type="group_meeting"`. Datetimes are UTC; the IANA zone name is a string on the event. The frontend shows times in the browser's zone.
- **Cancel = soft delete** of the Event (`deleted_at`). There is no "completed" status: `?when=past` means the end time has passed.
- **Validation:** no start in the past; length 5 to 480 minutes (`ends_datetime` or `duration_minutes`); start and end must be updated together.
- **Reminders:** scheduling creates one `EventRsvp` per member, so the platform's event reminders apply (24 hours: accepted and pending; 1 hour: accepted only). They run in the in-app scheduler (`apps/management/scheduler.py`), which needs `SCHEDULER_ENABLED=true`. The comment at `services.py:8` about a cron is stale.

## Shared note

- **Browser:** Yjs `Y.Doc`, text root `note`, bound to CodeMirror 6 with `yCollab` (`y-codemirror.next`). The socket code is hand-written (no `WebsocketProvider`). Local updates are batched every 200 ms; offline edits are queued and the full state is sent on reconnect (2 s retry; no retry after 4400 or 4403).
- **Server:** `pycrdt`. `apply_note_update` (`services.py:239-258`) takes a `select_for_update` lock, merges the update, and saves `ydoc_state`, `body` and `revision + 1`. Simultaneous edits are all kept.
- **Frames:** JSON with base64 payloads (`update`, `awareness`, `presence` in; `note.sync`, `note.update`, `note.awareness`, `note.peer_joined`, `note.presence` out). Limits: update 200,000 characters, awareness 10,000, presence once per second.
- **Cursors and presence** are relayed, never stored.
- **Infrastructure:** Django Channels on ASGI (`config/asgi.py`). Set `REDIS_URL` in production; without it the in-memory channel layer only works with one worker.
- `apps.live` is a separate, generic co-editing app used by submissions. Meetings does not use it yet (issue #539).

## Scheduled jobs

Meetings has no timed job of its own. Meeting reminders are the platform's RSVP reminders, which run hourly in the in-app scheduler (`apps/management/scheduler.py`, job `rsvp_reminders`) since 22 October 2026. GitHub's `rsvp-reminders.yml` is now manual-only; its last scheduled run was on 24 October.

So meetings is **not** affected by issue #575. That issue is about the ticket digest and the AI screening catch-up, which still run on GitHub Actions schedules and ran hours late in the week to 1 November 2026. It does depend on the in-app scheduler being on: if `SCHEDULER_ENABLED` is not `true` (with Always On) in production, no meeting reminders are sent at all. If reminders stop, check that first.

## Rules

1. Check the role **in this group** for every write. Do not use the user's global role.
2. Keep the note merge under the row lock; never write `ydoc_state` without merging.
3. Never trust a client's `body`: the plain-text snapshot is derived on the server from the merged document.
4. A draft summary must not reach non-managers (`views.py:182-191`, `serializers.py:83-94`).

## Tests

`backend/tests/apps/meetings/` (67 tests; fixtures in `support.py`: mentor, supervisor, two students, outsider, admin). `test_note_concurrency.py` only runs on PostgreSQL (`--settings=config.settings_test_postgres`). The WebSocket tests replace `channels.db.close_old_connections` in `setUp`; without that they fail on PostgreSQL with "the connection is closed". The meeting pages have no frontend unit tests.

## Known gaps

- `GroupMeetingsPage.vue:22,31` shows "Schedule meeting" by the **global** mentor role. Admins never see it; a global mentor who is not this group's mentor sees it and gets 403. Use the server's permission instead.
- The summary autosaves one second after typing starts and always publishes (`GroupMeetingDetailPage.vue:571`); leaving within that second drops the last edits.
- Reloading while offline loses unsent note edits (the document is only in memory).
- Note access is checked only on connect; a removed member can keep editing until they reconnect.
- Every update loads, merges and saves the whole document.
