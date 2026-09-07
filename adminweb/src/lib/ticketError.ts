import { isAxiosError } from "axios";

/** Codes marking a refusal somebody on this project wrote for a person.
 *
 *  config/exception_handler.py copies the code off whichever exception was
 *  raised. `invalid` is a ValidationError, which is how the attachment rules
 *  and both admin serializers refuse. `permission_denied` is the sentence in
 *  the ticket permission classes: "You do not have support privileges.",
 *  "You do not have admin privileges."
 *
 *  Every other code on this path carries DRF's own default English, written
 *  for whoever wrote the request rather than for an agent. A rejected
 *  assignee comes back as `Invalid pk "18" - object does not exist.`, a
 *  rejected enum as `"nope" is not a valid choice.`, an unhandled fault as
 *  "Internal server error". None of those tell an agent anything they can do,
 *  and the standing sentence at each call site below does.
 *
 *  Add a code here when the backend starts answering it with a sentence
 *  meant to be read.
 */
const WRITTEN_FOR_A_PERSON = ["invalid", "permission_denied"];

/** The server's own reason for refusing a ticket write, when it gave one.
 *
 *  Two error envelopes are in play. Anything raised under /admin/tickets/
 *  goes through config/exception_handler.py and comes back as
 *  `{error, code, request_id}`, which is what this reads.
 *
 *  The 404s never raise. views_admin.py:258 answers `{msg, data}` directly,
 *  the older admin shape queryError.ts reads, and its "Ticket not found" is
 *  deliberately not picked up here. That 404 is the commonest failure on
 *  this path, because it is what a colleague deleting the ticket looks like,
 *  and every caller below already answers it with a longer sentence that
 *  says what to do next.
 *
 *  Worth reading, because the commonest refusals that do raise are ones the
 *  agent can act on: "Attachment exceeds the maximum allowed size of 10 MB.",
 *  "Attach at most 5 files to one message." Answering those with "try again"
 *  sends the agent round a loop that ends the same way every time.
 */
export function ticketRefusalReason(error: unknown): string | undefined {
  if (!isAxiosError(error)) return undefined;
  const data = error.response?.data as
    | { error?: unknown; code?: unknown }
    | undefined;
  if (typeof data?.code !== "string") return undefined;
  if (!WRITTEN_FOR_A_PERSON.includes(data.code)) return undefined;
  const reason = typeof data.error === "string" ? data.error.trim() : "";
  // A stale CSRF token arrives as permission_denied as well, worded
  // "CSRF Failed: CSRF cookie not set." That is DRF talking about the
  // request machinery, not about this person's access. myFetch.ts retries
  // that once with a fresh token, so anything reaching here has already
  // failed twice and the words help nobody.
  if (reason === "" || /^csrf/i.test(reason)) return undefined;
  return reason;
}
