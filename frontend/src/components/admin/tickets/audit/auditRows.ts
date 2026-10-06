/**
 * How one audit row reads on the ticket audit page. Ported from
 * adminweb/src/components/tickets/TicketAuditPage.tsx, where these were
 * private functions of the page; they live here so the page and the table can
 * share them and the rule order below can be tested without a DOM.
 */
import {
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  categoryLabel,
  type AssigneeOption,
  type TicketAuditRow
} from '@/utils/ticketAgentSchema'

// The people on this screen, which is a wider set than the assignee roster:
// a requester who reopens their own ticket appears here and never there.
export type AuditActor = NonNullable<TicketAuditRow['actor']>

export function when(value: string): string {
  return new Date(value).toLocaleString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    // Rendered in whatever zone the reader's machine is in, so the zone has
    // to be on screen. Same rule as the queue's last activity column: the
    // same row reads 03:37 pm in Sydney and 02:37 am in Sao Paulo, and this
    // is the screen people quote timestamps off when they compare notes.
    timeZoneName: 'short'
  })
}

/** A stored value as the rest of the product writes it.
 *
 *  The audit page is the one screen whose entire job is being read, so it
 *  cannot be the one screen that prints database values. Every other place a
 *  status appears (the queue badge, the dashboard axis, all three emails)
 *  says "In progress", not "in_progress". */
function label(value: unknown, labels: Record<string, string>, missing = '—'): string {
  if (typeof value !== 'string' || value === '') return missing
  return labels[value] ?? value
}

/** A screening verdict's category as words.
 *
 *  The categories are decided by a module that is not in this repository, so
 *  there is no list here to look them up in. Underscores out and one capital
 *  is as far as this page can honestly go, and it beats printing self_harm at
 *  a reader. */
function humanise(value: string): string {
  const words = value.replace(/_/g, ' ')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

/** Which ticket the row is about.
 *
 *  The id every time, deletions included, so that one ticket wears one name
 *  on the screen. Only a creation and a deletion carry the number in their
 *  snapshot, and naming those two by number printed the same ticket as
 *  SUP-2026-00250 on one row and #250 on the next.
 *
 *  An id is not a ticket number, and the two stop looking alike soon.
 *  numbering.py opens a fresh counter every year, while the ids carry on, so
 *  the first ticket of 2027 is SUP-2027-00001 on an id that follows the last
 *  one of 2026. Today's pairs line up only because the platform is in its
 *  first year of numbering.
 *
 *  The number is not lost. A deletion still prints it in What changed, that
 *  being the one row whose ticket cannot be opened to read it off. */
export function ticketName(row: TicketAuditRow): string {
  return `#${row.ticketId}`
}

/** What changed, in one line.
 *
 *  A deletion is the case this screen exists for, and it is also the only row
 *  whose ticket cannot be opened to read its number off. So the number goes
 *  here, out of the snapshot the delete wrote.
 *
 *  The rules run in a fixed order and the first one that recognises the row
 *  answers: delete, create, status, owner, priority, category. The order is
 *  load-bearing and the backend relies on it. lifecycle.py writes only the
 *  owner on an assign row "because the audit page summarises a row by the
 *  first field it recognises, so a status key on an assign row would print the
 *  status change and hide the change of owner the row exists for". A reopen
 *  row carries both status and assignee_id, and reads as the status change; a
 *  delete row carries status too, and reads as the deletion. */
export function summarise(row: TicketAuditRow, people: AssigneeOption[]): string {
  const before = row.beforeState ?? {}
  const after = row.afterState ?? {}

  if (row.action === 'delete') {
    // Whatever the snapshot holds, in the order a person reads it. A delete
    // records both parts, so a row with only one of them is an old row or a
    // snapshot that half wrote, and half of it still beats none of it.
    const named = [before.ticket_number, before.subject].filter(
      (part) => typeof part === 'string' && part !== ''
    )
    return named.length > 0 ? named.join(' · ') : 'Ticket removed from the queue'
  }
  if (row.action === 'create') {
    // Nothing changed: the ticket came into being. What is worth reading is
    // why the screener raised it, and this snapshot is the only place that
    // says so.
    const flagged = after.screening_category
    return typeof flagged === 'string' && flagged !== ''
      ? `Flagged as ${humanise(flagged)}`
      : 'Ticket opened'
  }
  if (typeof before.status === 'string' || typeof after.status === 'string') {
    return `${label(before.status, TICKET_STATUS_LABELS)} → ${label(after.status, TICKET_STATUS_LABELS)}`
  }
  if ('assignee_id' in before || 'assignee_id' in after) {
    if (after.assignee_id === null) return 'Handed back to the pool'
    // A name, not "#11". The Who column beside this one already prints
    // names, so an id here reads as a different kind of thing entirely.
    // Falls back to the id when the roster has not loaded or the person has
    // since been deleted: an id is poor, but blank would be worse.
    const owner = people.find((person) => person.id === after.assignee_id)
    return owner ? `Owner set to ${owner.name}` : `Owner set to #${String(after.assignee_id)}`
  }
  // The before side only, for this rule and the next. A screening create row
  // carries priority in its after side, and must never reach here as a change.
  if (typeof before.priority === 'string') {
    return `${label(before.priority, TICKET_PRIORITY_LABELS)} → ${label(after.priority, TICKET_PRIORITY_LABELS)}`
  }
  // Re-filing, which support gained when the client replaced the three
  // categories with eight. Without this branch the row fell through to "—",
  // so the one screen whose job is being read said a change had happened and
  // refused to say what it was.
  if (typeof before.category === 'string') {
    const next = typeof after.category === 'string' ? after.category : ''
    return `${categoryLabel(before.category)} → ${categoryLabel(next)}`
  }
  return '—'
}

/** Everybody the Who filter offers, sorted by name.
 *
 *  Who did this is not the question the roster answers. The roster is who
 *  can be handed a ticket; a requester who reopens their own is on this
 *  screen and never on that list, so the rows themselves have to supply the
 *  people it leaves out. */
export function actorOptions(
  people: AssigneeOption[],
  rows: TicketAuditRow[],
  picked: AuditActor | null
): AuditActor[] {
  const byId = new Map<number, string>()
  for (const person of people) byId.set(person.id, person.name)
  for (const row of rows) {
    if (row.actor) byId.set(row.actor.id, row.actor.name)
  }
  // Picking somebody leaves only their own rows on screen. Without this the
  // option just picked drops out of the list it was picked from as soon as
  // the two filters together match nothing.
  if (picked) byId.set(picked.id, picked.name)
  // Only the page in front of the reader. Somebody whose rows all sit on
  // another page is still not selectable from here, and the list changes as
  // the reader pages through. A complete one needs the server to name the
  // actors of the whole filtered log, which it does not do yet.
  return Array.from(byId, ([id, name]) => ({ id, name })).sort((a, b) =>
    a.name.localeCompare(b.name)
  )
}
