/**
 * The queue's filters as the 2026-10-22 client meeting asked for them.
 *
 * C-27: "for all of these, actually, can you make those check boxes so that
 * it can be, like, multiple select instead of just single select?" So each of
 * the five lists holds several values. Several of one kind are any of them;
 * different kinds narrow each other (services/queue.py apply_filters).
 *
 * C-28: "by default, when someone opens this page, it shows all statuses
 * except for resolved. So resolved essentially to be hidden by default." The
 * queue opens on that view, and Clear filters comes back to it.
 */
import { TICKET_STATUS_LABELS, type TicketFilters, type TicketStatus } from '@/utils/ticketAgentSchema'

/** Every status but Resolved, in the order the status list shows them. */
export const RESTING_STATUSES = (Object.keys(TICKET_STATUS_LABELS) as TicketStatus[]).filter(
  (status) => status !== 'resolved'
)

/** What the queue shows when it opens. A new object each time: the queue
 *  replaces its filters wholesale, and two holders of one array would move
 *  together. */
export function restingFilters(): TicketFilters {
  return { status: [...RESTING_STATUSES] }
}

const LIST_KEYS = ['region', 'status', 'category', 'assignee', 'priority'] as const

/** Whether these filters are the view the queue opens on: every status but
 *  Resolved, and nothing else. Order does not matter. */
export function isRestingView(filters: TicketFilters): boolean {
  if (filters.search) return false
  for (const key of LIST_KEYS) {
    const values = filters[key] ?? []
    if (key === 'status') {
      if (values.length !== RESTING_STATUSES.length) return false
      if (!RESTING_STATUSES.every((status) => values.includes(status))) return false
    } else if (values.length) {
      return false
    }
  }
  return true
}

export type FilterOption = {
  value: string
  label: string
  /** Not one of the kind but a way in beside them: Overdue in the status
   *  list, a condition on the clock rather than a status a ticket is saved
   *  with. Left out when the box works out "every one" or "all except". */
  extra?: boolean
}

/** The words on a filter's box for what is ticked.
 *
 *  Nothing ticked, or every one of the kind, is no narrowing at all, so it
 *  reads as the list's "Any …". All but one of three or more reads "Not …",
 *  which is how the queue's resting view reads: "Not Resolved". ("All except
 *  Resolved", the client's own words, was cut to "All except Re…" in the
 *  status box at 1440px, the one place everybody looks first.) Otherwise the
 *  ticked labels in list order, which the box cuts
 *  short with an ellipsis when they do not fit; the list itself shows them
 *  all once opened. A value the list does not have (yet: regions and people
 *  arrive from the server) shows as stored rather than vanishing from the
 *  count. */
export function filterSummary(selected: readonly string[], options: readonly FilterOption[], anyLabel: string): string {
  const chosen = new Set(selected)
  const kind = options.filter((option) => !option.extra)
  const extras = options.filter((option) => option.extra && chosen.has(option.value))
  const ofKind = kind.filter((option) => chosen.has(option.value))
  const unknown = selected.filter((value) => !options.some((option) => option.value === value))

  if (!extras.length && !unknown.length) {
    if (ofKind.length === 0 || ofKind.length === kind.length) return anyLabel
    if (kind.length >= 3 && ofKind.length === kind.length - 1) {
      const missing = kind.find((option) => !chosen.has(option.value))!
      return `Not ${missing.label}`
    }
  }
  // Every one of the kind already takes in every ticket an extra could add.
  if (kind.length && ofKind.length === kind.length && !unknown.length) return anyLabel
  return [...ofKind.map((option) => option.label), ...extras.map((option) => option.label), ...unknown].join(', ')
}
