/**
 * The pure arithmetic behind the ticket queue's footer and deep link, kept
 * apart from the components so each rule has one copy and can be read on its
 * own. Ported from adminweb: TicketQueuePage.tsx (page count),
 * ui/pagination-nav.tsx (numbered buttons), user/PageSizeSelect.tsx (custom
 * size) and routes/_auth/tickets/index.tsx (the ?ticket= guard).
 */

/** The page sizes the rows-per-page control offers.
 *
 *  Capped at the server's own limit rather than copying React's 25/50/100/200
 *  and a custom box reaching 500. The admin queue endpoint clamps `limit` to
 *  100 and answers with what it served (backend/apps/tickets/views.py,
 *  MAX_PAGE_SIZE), so at 200 the React control stood there claiming a page
 *  size the server was not honouring (U2 GAP-10). React could not fix that
 *  half: its Select would not fire for a value equal to the current one, so a
 *  control fed the served size could not be set back to 100. A native select
 *  has no such trap, and not offering a size the server refuses is the
 *  cleaner of the two fixes U2 names. The page count still divides by the
 *  size the server served (servedPageCount below), so it stays right if the
 *  server's cap ever drops under what this control offers. */
export const PAGE_SIZE_PRESETS = [25, 50, 100] as const
export const MIN_PAGE_SIZE = 1
export const MAX_PAGE_SIZE = 100

/** Where the queue opens: the server's own default (views.py). Not a preset,
 *  so the control opens as the number box, as it did in React. */
export const DEFAULT_PAGE_SIZE = 10

/** The most ticket ids backend/apps/tickets/serializers_admin.py accepts in
 *  one bulk assign (`ticketIds` max_length). Written out rather than fetched:
 *  it is a fixed rule of the write path. */
export const BULK_ASSIGN_LIMIT = 200

export function isPresetPageSize(value: number): boolean {
  return (PAGE_SIZE_PRESETS as readonly number[]).includes(value)
}

/** A typed page size, floored and held inside 1..MAX_PAGE_SIZE. Anything that
 *  is not a number falls back to the first preset. */
export function clampPageSize(value: number): number {
  if (!Number.isFinite(value)) return PAGE_SIZE_PRESETS[0]
  return Math.min(MAX_PAGE_SIZE, Math.max(MIN_PAGE_SIZE, Math.floor(value)))
}

/**
 * How many pages the footer offers.
 *
 * `served` is the page size the server actually used, which is not always the
 * one asked for. views.py clamps limit to MAX_PAGE_SIZE, 100, and answers with
 * what it served. Dividing the total by the asked-for size called 450 rows
 * three pages of 200 while the server was sending five pages of 100, and the
 * pinned last-page button went to row 201 of 450 instead of the end.
 *
 * hasMore is the floor, not the total. `total` counts the walk's frozen set,
 * and a ticket somebody works mid-walk leaves it, so the count can fall below
 * the page being read, and Next would go dead with rows still ahead.
 *
 * With no response yet (a page is loading) this is the page being read, so the
 * footer says "Page N of N" and Next waits for the answer.
 */
export function servedPageCount(
  page: number,
  asked: number,
  data: { total: number; limit: number; hasMore: boolean } | null
): number {
  const served = data?.limit ?? asked
  return Math.max(1, Math.ceil((data?.total ?? 0) / served), data?.hasMore ? page + 1 : page)
}

export type PageItem = number | 'ellipsis'

/** Sliding window of page numbers with the first and last page always pinned.
 *  A single otherwise-hidden page is shown inline instead of behind an
 *  ellipsis. */
export function pageItems(current: number, total: number): PageItem[] {
  const maxButtons = 7
  if (total <= maxButtons) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }

  const windowSize = maxButtons - 4 // slots between the pinned first/last + 2 ellipses
  let start = Math.max(2, current - Math.floor(windowSize / 2))
  let end = start + windowSize - 1
  if (end > total - 1) {
    end = total - 1
    start = end - windowSize + 1
  }

  const items: PageItem[] = [1]
  if (start > 3) items.push('ellipsis')
  else for (let p = 2; p < start; p++) items.push(p)
  for (let p = start; p <= end; p++) items.push(p)
  if (end < total - 2) items.push('ellipsis')
  else for (let p = end + 1; p < total; p++) items.push(p)
  items.push(total)
  return items
}

/**
 * The ticket a `?ticket=` query names, or null.
 *
 * Deep link. A ticket the platform raised itself carries a link of this shape
 * in its first message (backend/apps/tickets/services/handoff.py), so support
 * can go straight from the notification to the ticket. Without this the panel
 * has no way to open.
 *
 * Guarded rather than coerced. `Number("abc")` is NaN, which is neither null
 * nor undefined, so the panel opens on a ticket that cannot exist and sits on
 * "Loading..." forever. React's router had already parsed numeric params, so a
 * type check did the work there; a Vue query value is always a string (or an
 * array of them, for a repeated key), so the string itself has to be a plain
 * positive integer: no sign, no leading zero, no decimal point, no exponent,
 * no spaces.
 */
export function ticketIdFromQuery(value: unknown): number | null {
  if (typeof value !== 'string' || !/^[1-9]\d*$/.test(value)) return null
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : null
}
