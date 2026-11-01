# Chat app: AI message screening

This file covers only the **AI message screening** part of `apps.chat`, added by Team 2 (COMP3888, 2026) in PR #549. The rest of the chat app (groups, messages, mentions, digest, live sockets) belongs to the original platform.

Group chat messages are checked by OpenAI's moderation model. A flagged message is hidden from everyone except its sender, and a high-priority support ticket is opened so a support agent can approve or delete it.

## Map

| Path | What it holds |
|---|---|
| `services/screening.py` | Queueing, the background worker, the OpenAI call, verdicts, suppression, ticket creation |
| `models/message_screening.py` | `MessageScreening` (table `message_screenings`) and its statuses |
| `models/messages.py` | `is_suppressed`, `suppressed_at`, `suppress()`, `approve_suppressed()` |
| `serializers.py:30-39` | `validate_chat_message_text`: the blocked-word list, checked before saving |
| `views.py` | Create/upload/edit call `schedule_message_screening`; `run-ai-screening/` retry endpoint; suppressed messages hidden from everyone but the sender |
| `rbac.py` | Nobody, not even an admin, can edit or delete a suppressed message directly |
| `management/commands/screen_unscreened_messages.py`, `screen_suspicious_messages.py` | Backfill and manual retry (`--limit`, `--dry-run`) |
| `../tickets/services/handoff.py` | `create_ticket_from_screening`: opens the ticket |
| `../tickets/views_admin.py` (`TicketScreeningReviewView`) | `POST /api/v1/admin/tickets/<id>/screening-review/` with `decision` = `approve` or `delete` |
| `.github/workflows/ai-message-screening.yml` | Retry job, minutes 12 and 42 of every hour |

Frontend: the review section is in `frontend/src/components/admin/tickets/detail/TicketDetailPanel.vue`; hidden-message display is in `frontend/src/views/GroupDetailPage.vue` and `frontend/src/utils/chatModeration.ts`.

## Flow

1. The blocked-word list rejects the message before it is saved (HTTP 400, "This message contains blocked content and was not sent."). `<@id>` mention tokens are not checked. The client asked for "reject", not "mask".
2. After the message commits, `schedule_message_screening` creates a `MessageScreening` row with status `suspicious` and starts the worker. System messages, blank text, deleted messages and already-screened text (same hash) are skipped.
3. The worker (`dispatch_suspicious_message_screening`) is a daemon thread guarded by a per-process lock. `process_suspicious_messages` takes up to `AI_SCREENING_BATCH_LIMIT` rows, oldest first, and checks them one by one.
4. `screen_suspicious_message` calls OpenAI **outside** any transaction, then locks the row, re-checks that it is still `suspicious`, and saves the verdict.
5. If flagged, in **one transaction**: `message.suppress()`, `create_ticket_from_screening` (category `flagged_content`, channel `ai_screening`, priority high, unassigned), link the ticket to the row, and broadcast the suppression on commit. Email E6 goes to the support inbox without the message text.
6. The agent approves (message visible again, status `approved`) or deletes (soft delete, status `rejected`). Both resolve the ticket and write an audit row.

## Rules

1. **Privacy:** only the message text goes to OpenAI, with email addresses and phone numbers replaced (`[EMAIL_ADDRESS]`, `[PHONE_NUMBER]`) and cut to `AI_SCREENING_MAX_INPUT_CHARS`. Never send the sender, group, other messages or attachments. Users are minors.
2. **No duplicate tickets.** This relies on the unique constraint `(message, text_hash)`, the `select_for_update` plus status re-check, and the one-to-one `ticket` link. Keep all three.
3. **Suppression and ticket creation stay in one transaction**, so a hidden message always has a ticket and a ticket always has a hidden message.
4. **Never call OpenAI inside a database transaction** (it can take up to `AI_SCREENING_OPENAI_TIMEOUT_SECONDS`).
5. **`messages.is_suppressed` is NOT NULL with no database default** (migration `0019`). Code older than that migration cannot insert messages. Before rolling back, migrate `chat` to `0018` or add a database default.

## Configuration

`OPENAI_API_KEY` (no key: rows queue but are never checked), `AI_SCREENING_TRIGGER_TOKEN` (retry endpoint, header `X-AI-Screening-Token`; unset gives 503), `AI_SCREENING_OPENAI_MODEL` (`omni-moderation-latest`), `AI_SCREENING_OPENAI_URL`, `AI_SCREENING_OPENAI_TIMEOUT_SECONDS` (15), `AI_SCREENING_MAX_INPUT_CHARS` (4000), `AI_SCREENING_BATCH_LIMIT` (100), `AI_SCREENING_DISPATCH_SYNC` (false; run inline, for tests). See `backend/config/settings.py:733-754`.

## Tests

`backend/tests/apps/chat/` files whose names contain `screen` (63 tests), plus `backend/tests/apps/tickets/test_handoff.py`. Tests never call OpenAI: they patch `apps.chat.services.screening.requests.post`. Locally you can point `AI_SCREENING_OPENAI_URL` at a fake moderation server.

## Known gaps (issues #575, #576, #577)

- Messages are broadcast before the verdict, so other members can see a flagged message for a few seconds, or up to about 30 minutes if OpenAI is down.
- Messages sent from the admin console (`apps/admin/services/group.py`) are not screened.
- Failed checks retry forever: no attempt cap, the `failed` status is never written, and HTTP 429 has no back-off.
- The lock is per process, so two workers can call OpenAI for the same row (only one ticket results).
- If a message is edited while queued, the old text's verdict is applied to the edited message.
- `handoff.py` mentions a "rule" layer that does not exist; every verdict has `layer="llm"`.
- The retry job still runs on GitHub Actions, not in the in-app scheduler (`apps/management/scheduler.py`).
