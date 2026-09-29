/**
 * The words and times the ticket detail panel prints, in one place so the
 * panel and its three children cannot drift apart. Ported from
 * adminweb/src/components/tickets/TicketDetailPanel.tsx, ReplyBox.tsx and
 * InternalNoteBox.tsx.
 *
 * UI strings carry no em-dash. Three React sentences did; each is split into
 * two sentences here and the words are otherwise unchanged. The "—" that
 * stands in for an empty value is a glyph, not punctuation, and stays (the
 * portal uses it the same way, utils/userFormat.ts).
 */
import { ApiError } from '@/utils/apiError'
import { attachmentErrorMessage, ticketRefusalReason } from '@/utils/ticketAgentAPI'
import type { TicketMessage } from '@/utils/ticketAgentSchema'

/** Date only, for "Member since".
 *
 *  "Member since 26 Aug 2026, 09:14" reads like an event; the field is there
 *  to answer "new account or long-standing participant". */
export function whenDate(value: string): string {
  return new Date(value).toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric'
  })
}

/** Date and time with the zone, for every other time on the panel. */
export function when(value: string): string {
  return new Date(value).toLocaleString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    // Rendered in whatever zone the reader's machine is in, so the zone has
    // to be on screen. Same rule as the queue's last activity column: the
    // same message reads 03:37 pm in Sydney and 02:37 am in Sao Paulo, and
    // agents in two places read this timeline to each other.
    timeZoneName: 'short'
  })
}

/** Who a message is from.
 *
 *  Only a user_message with no author is the requester. Support rows lose
 *  their author when an agent's account is deleted, and calling that
 *  "Requester" attributes an internal note to the student it was written
 *  about.
 *
 *  The label says what is known and no more. A support row with no author has
 *  three possible origins and the payload tells them apart in none of them: an
 *  agent whose account was deleted, screening's evidence note, and the note
 *  recording an email that could not be delivered. The last two were never
 *  written by a person, so naming a removed account states something that
 *  never happened on two rows out of three.
 *
 *  Not the wording the audit page and the History list use, and deliberately
 *  so. Those two read AuditLog rows, where the screening handoff is the only
 *  writer that leaves the actor empty and its rows carry `channel` in their
 *  own snapshot to prove it, so they can name both cases (auditActorName). A
 *  message carries no such evidence, and copying their sentence here would be
 *  this row claiming a certainty it does not have. */
export function authorLabel(message: Pick<TicketMessage, 'author' | 'messageType'>): string {
  if (message.author) return message.author.name
  return message.messageType === 'user_message' ? 'Requester' : 'Support (author not recorded)'
}

// --- Download refusals (scaffold report open question O4) -------------------

/** A 403 carrying `permission_denied` on a download.
 *
 *  A download is a GET, so it carries no CSRF token and cannot be refused for
 *  a stale one. Signed out answers 403 with `not_authenticated`; this code is
 *  IsSupportScoped saying "You do not have support privileges.", which for
 *  somebody who already has this panel open means their queue access was
 *  revoked since they loaded the page. Telling them their session expired
 *  sends them to sign in again, and signing in again gets the same answer. */
export const DOWNLOAD_ACCESS_REVOKED =
  'You no longer have access to the support queue, so this file cannot be opened. Ask an admin if you still need access.'

/** Any 404 on a download.
 *
 *  Two different things answer it, and the answer is the same body for both:
 *  `{msg: "Attachment not found", data: null}`. One is a row that is gone
 *  (its ticket or its message was deleted). The other is a row that is still
 *  there whose file storage has lost: the admin download opens the file
 *  first and answers a lost one with that same 404, on purpose
 *  (views_admin.py TicketAdminAttachmentDownloadView, open_for_download in
 *  services/attachments.py: "both download views answer that exactly as they
 *  answer a row that is not there"; pinned by
 *  tests/apps/tickets/test_attachment_streaming.py NOT_FOUND).
 *
 *  So this page cannot tell the two apart, and the sentence has to be true
 *  for both. The scaffold's sentence for a 404 says the ticket or message
 *  "was deleted", which is false for a lost file: nothing was deleted, and
 *  the queue still shows the ticket when the agent reloads it as told.
 *
 *  Keyed on the status alone, like the scaffold. The body is not read: the
 *  earlier version looked for a `{detail}` body to name the lost file, and
 *  that body never reaches this endpoint (serve_managed_file only answers
 *  `{detail}` when it opens the file itself, and here the view hands it one
 *  already open). If the backend ever gives a lost file its own body or
 *  code, that is the time to give it its own sentence. */
export const DOWNLOAD_NOT_FOUND =
  'This file could not be found. Its ticket or message may have been deleted, or the file is missing from storage. Reload the queue to check.'

/** What to say under a file whose download was refused.
 *
 *  The scaffold's attachmentErrorMessage keys on the status alone, as the
 *  React version did. Two of its sentences are untrue for a case that shares
 *  their status, and each of those gets a sentence here that is true for
 *  every case behind it; everything else is the scaffold's. */
export function downloadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403 && error.code === 'permission_denied') return DOWNLOAD_ACCESS_REVOKED
    if (error.status === 404) return DOWNLOAD_NOT_FOUND
  }
  return attachmentErrorMessage(error)
}

// --- Refused writes -----------------------------------------------------------

/** Said when a triage change is refused and the server gave no reason we
 *  read. A 404 is the ordinary case: somebody else deleting the ticket while
 *  this panel is open produces exactly that, and this sentence says what to
 *  do about it. */
export const CHANGE_NOT_SAVED_FALLBACK =
  'The ticket may have been deleted or changed by someone else. Close the panel and reopen it to see where it stands.'

export function changeNotSavedMessage(error: unknown): string {
  // The server's own words when it refused: a refusal an agent can act on is
  // worth more than a sentence written months ago that guesses at what went
  // wrong.
  return `That change was not saved. ${ticketRefusalReason(error) ?? CHANGE_NOT_SAVED_FALLBACK}`
}

export function deleteRefusedMessage(error: unknown): string {
  // Reached most often by an admin whose admin access was taken away while
  // this panel was open, since canDelete came from the session loaded with
  // the page: the server answers "You do not have admin privileges." and
  // "Nothing has changed" on its own leaves them pressing the button again.
  const reason = ticketRefusalReason(error)
  return reason ? `That did not delete. Nothing has changed. ${reason}` : 'That did not delete. Nothing has changed.'
}

/** What a message box says when the server did not take the message.
 *
 *  Say what the server said. An 11 MB attachment is refused with "Attachment
 *  exceeds the maximum allowed size of 10 MB.", and telling the agent to try
 *  again instead is worse than saying nothing: the same send fails the same
 *  way however many times they click.
 *
 *  ticketRefusalReason answers with nothing for a dropped connection, and also
 *  for the failures whose wording is DRF's rather than ours. The fallback
 *  covers all of those: it keeps the text and asks for another go, which is
 *  right for a fault and no worse than a machine message nobody can act on. */
export function messageRefusedMessage(error: unknown): string {
  const reason = ticketRefusalReason(error)
  return reason
    ? `${reason} Your text is still here.`
    : 'That did not send. Your text is still here. Try again.'
}
