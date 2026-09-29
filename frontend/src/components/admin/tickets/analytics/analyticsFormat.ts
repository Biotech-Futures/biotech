/**
 * The wording and number formatting behind the ticket analytics page, ported
 * from adminweb/src/components/tickets/TicketAnalyticsPage.tsx. Kept out of
 * the component so each rule can be tested on its own.
 */
import { ApiError } from '@/utils/apiError'
import { ticketRefusalReason } from '@/utils/ticketAgentAPI'
import {
  TICKET_PRIORITY_LABELS,
  TICKET_STATUS_LABELS,
  categoryLabel,
  type AssigneeOption,
  type TicketPriority,
  type TicketStatus
} from '@/utils/ticketAgentSchema'

/** The dimension's name as a person would write it.
 *
 *  Derived rather than looked up. The table this replaced named six of the
 *  backend's seven dimensions, so the seventh reached the dropdown as its own
 *  database key, lower case beside six English labels. A table falls behind
 *  the next dimension the same way. Splitting the key apart does not, for
 *  either of the two shapes a key is written in here: camelCase and
 *  snake_case both come out as words.
 *
 *  One shape it still reads wrong is a run of capitals. "SLABreach" comes out
 *  "Slabreach", because the split looks for a lower case letter in front of a
 *  capital and there is none. No dimension is written that way today, and the
 *  answer for one that is would be a short table of exceptions over this, not
 *  a return to naming every dimension by hand.
 */
export function dimensionLabel(dimension: string): string {
  const words = dimension
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .trim()
    .toLowerCase()
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export const CHANNEL_LABELS: Record<string, string> = {
  portal: 'Portal',
  email: 'Email',
  ai_screening: 'Raised by screening'
}

export function channelLabel(value: string): string {
  return CHANNEL_LABELS[value] ?? value
}

/** The bar label for one bucket of the chosen dimension.
 *
 *  Anything whose stored value is not the word a person would use needs a
 *  branch here. Without one the chart prints the database value, which is how
 *  the assignee breakdown came to label its bars with user ids.
 */
export function segmentLabel(dimension: string, value: string, people: AssigneeOption[]): string {
  // Category goes through categoryLabel even when empty. In React this
  // function answered "" with "Not recorded" before looking at the dimension,
  // so the same empty bucket read "Not categorised" in Demand's "By category"
  // chart and "Not recorded" in "Broken down by category" on the same screen
  // (U4 AN-27). The port picks the category wording for both.
  if (dimension === 'category') return categoryLabel(value)
  if (value === '') return 'Not recorded'
  switch (dimension) {
    case 'status':
      return TICKET_STATUS_LABELS[value as TicketStatus] ?? value
    case 'channel':
      return channelLabel(value)
    case 'priority':
      return TICKET_PRIORITY_LABELS[value as TicketPriority] ?? value
    case 'assignee': {
      // A name, not "#11", the same rule the audit log follows. The id is the
      // fallback for a roster that has not loaded and for somebody whose
      // account has since gone. Poor, but better than blank.
      const owner = people.find((person) => String(person.id) === value)
      if (!owner) return `#${value}`
      // Two agents can carry the same display name, and then the name on its
      // own names neither of them. It also draws two bars captioned alike.
      // The id comes back as a suffix for those two only.
      const shared = people.some((person) => person.name === owner.name && person.id !== owner.id)
      return shared ? `${owner.name} #${owner.id}` : owner.name
    }
    // region and userType hold words already: country names, and the role
    // names the platform stores.
    default:
      return value
  }
}

/** What the server said was wrong with the window, when it was the window.
 *
 *  The ticket endpoints raise DRF validation errors that
 *  config/exception_handler.py reshapes into `{error, code, fields}`; every
 *  400 this endpoint can give is one of those, with code `invalid`
 *  ("from must be earlier than to.", "to is outside the range of dates a
 *  report can cover.", ...). ticketRefusalReason already reads exactly that
 *  shape and nothing else. React read `error` directly; here apiError.ts has
 *  already filled `error` with a fallback sentence when the body carried
 *  none, so the code is what tells the server's own sentence from ours.
 *
 *  Restricted to 400 on purpose: the same envelope carries "Internal server
 *  error" for a 500, and repeating that tells the reader nothing they can act
 *  on, where "from must be earlier than to." is a two-second fix.
 */
export function windowProblem(error: unknown): string | undefined {
  if (!(error instanceof ApiError) || error.status !== 400) return undefined
  return ticketRefusalReason(error)
}

/** Seconds as something a person reads at a glance.
 *
 *  Deliberately coarse: "2h 45m" is the answer to "are we quick?", and a
 *  seconds-precise duration invites reading precision into an average of a
 *  handful of tickets.
 *
 *  Rounded to whole minutes FIRST and split into hours after. The React
 *  version split first and rounded the leftover minutes, so a remainder of
 *  59.5 minutes or more printed as "60m" instead of carrying into the hour:
 *  3,599 s read "60m", 7,199 s read "1h 60m", 172,799 s read "47h 60m"
 *  (U4 AN-24). */
export function duration(seconds: number | null): string {
  if (seconds === null) return '—'
  const totalMinutes = Math.round(seconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) return `${minutes}m`
  if (hours < 48) return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`
  return `${Math.round(hours / 24)}d`
}

/** "26 Aug 2026", never "26/08" or "08/26". */
export function namedDay(value: string): string {
  const [year, month, day] = value.split('-').map(Number)
  if (!year || !month || !day) return value
  // setUTCFullYear rather than Date.UTC(year, ...): Date.UTC reads a year
  // from 0 to 99 as 1900 plus that year. A native date input reports every
  // intermediate year while somebody types one ("0002", "0020", "0202",
  // "2026"), and the React echo briefly said 1902 and 1920 for those.
  const date = new Date(Date.UTC(2000, month - 1, day))
  date.setUTCFullYear(year)
  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC'
  })
}

export function describeWindow(from: string, to: string): string {
  if (from && to) {
    return `Covering ${namedDay(from)} to ${namedDay(to)} inclusive, in UTC.`
  }
  if (from) return `Covering ${namedDay(from)} onwards, in UTC.`
  return `Covering everything up to and including ${namedDay(to)}, in UTC.`
}

/** The value axis: a whole-number step and the top of the scale.
 *
 *  Whole numbers only (recharts' allowDecimals={false} in React): every value
 *  on this page is a count of tickets or a whole number of seconds, and a
 *  tick at 2.5 tickets is a quantity nobody can have. About four steps, each
 *  1, 2 or 5 times a power of ten, so the ticks land on round numbers. */
export function niceScale(max: number, target = 4): { top: number; ticks: number[] } {
  if (!(max > 0)) return { top: 1, ticks: [0] }
  const rough = max / target
  const magnitude = 10 ** Math.floor(Math.log10(rough))
  const residual = rough / magnitude
  const nice = residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10
  const step = Math.max(1, Math.round(nice * magnitude))
  const top = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let tick = 0; tick <= top; tick += step) ticks.push(tick)
  return { top, ticks }
}
