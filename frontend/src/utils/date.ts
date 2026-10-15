/**
 * @file date.ts
 * @description date.ts provides reusable date formatting helper utilities for the frontend application. It is responsible for converting raw date values into human-readable Australian date formats for different UI scenarios, such as standard date display, long-form date display, and announcement timestamp display.
 * @author Shiqi Fang
 * @author Jiachen Ding
 * @author Qin Chen
 * @version 1.0.0
 *
 * Project: Group Based 5703 Capstone Project
 * Group: CS17-1
 * Team: CS17-1 Frontend Team
 *
 * Component Type: Frontend Utility Module
 * File Role: Date formatting helper
 * Purpose: Provide reusable helper functions for formatting dates into consistent Australian-style display strings across the frontend application.
 * Scope: Shared by announcements, dashboards, resource pages, event-related components, and any frontend module that needs consistent date presentation.
 *
 * Responsibilities:
 * - Convert string or Date input values into valid JavaScript Date objects
 * - Safely handle invalid date input
 * - Format dates using Australian locale conventions
 * - Support short date display for common UI usage
 * - Support long date display with optional weekday output
 * - Provide fallback text for announcement dates when the input is invalid
 *
 * Dependencies:
 * - JavaScript Date object
 * - Number.isNaN
 * - Browser Intl and toLocaleDateString support
 * - en-AU locale formatting rules
 *
 * Revision Summary:
 * - Major revisions: 1
 * - Minor revisions: 0
 *
 * Last Modified: 2026-04-05
 * Modified By: CS17-1 Frontend Team
 */

/** Sydney's clock on a day ("YYYY-MM-DD"): AEDT in daylight saving
 *  (UTC+11), else AEST (UTC+10). */
export function sydneyClockOn(isoDate: string): { name: 'AEDT' | 'AEST'; daylight: boolean; offset: string } {
  // Midday in Sydney that day, well clear of a clock change in the small hours.
  const at = new Date(`${isoDate}T02:00:00Z`)
  const zone = new Intl.DateTimeFormat('en-AU', { timeZone: 'Australia/Sydney', timeZoneName: 'longOffset' })
    .formatToParts(at)
    .find((part) => part.type === 'timeZoneName')?.value
  const daylight = zone === 'GMT+11:00'
  return daylight
    ? { name: 'AEDT', daylight, offset: 'UTC+11' }
    : { name: 'AEST', daylight, offset: 'UTC+10' }
}

export const DEFAULT_TIME_ZONE = 'UTC'

const toValidDate = (value: string | Date | null | undefined): Date | null => {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

// Intl.DateTimeFormat is expensive to construct (parses locale + tz data).
// Cache per (locale, options) shape so hot render paths don't pay it.
const _formatterCache = new Map<string, Intl.DateTimeFormat>()
const getFormatter = (
  locale: string,
  options: Intl.DateTimeFormatOptions,
): Intl.DateTimeFormat => {
  const key = locale + '|' + JSON.stringify(options)
  let f = _formatterCache.get(key)
  if (!f) {
    f = new Intl.DateTimeFormat(locale, options)
    _formatterCache.set(key, f)
  }
  return f
}

export function isValidTimeZone(value: string | null | undefined): value is string {
  if (!value) return false

  try {
    new Intl.DateTimeFormat('en-AU', { timeZone: value }).format(new Date())
    return true
  } catch {
    return false
  }
}

export function normalizeTimeZone(value: string | null | undefined): string {
  return isValidTimeZone(value) ? value : DEFAULT_TIME_ZONE
}

export function getBrowserTimeZone(): string {
  return normalizeTimeZone(Intl.DateTimeFormat().resolvedOptions().timeZone)
}

export function formatTimeZoneLabel(value: string | null | undefined): string {
  const timeZone = normalizeTimeZone(value)
  return timeZone.replace(/_/g, ' ')
}

/** The browser's timezone with its current offset, e.g. "Australia/Sydney (GMT+10)". */
export function describeBrowserTimeZone(): string {
  const timeZone = getBrowserTimeZone()
  const label = formatTimeZoneLabel(timeZone)
  const offset = getFormatter('en-AU', { timeZone, timeZoneName: 'shortOffset' })
    .formatToParts(new Date())
    .find((part) => part.type === 'timeZoneName')?.value
  return offset ? `${label} (${offset})` : label
}

export function getTimeZoneDateParts(
  value: string | Date | null | undefined,
  timeZone = DEFAULT_TIME_ZONE,
): { year: number; month: number; day: number } | null {
  const date = toValidDate(value)
  if (!date) return null

  const parts = getFormatter('en-AU', {
    timeZone: normalizeTimeZone(timeZone),
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(date)

  const partMap = new Map(parts.map((part) => [part.type, part.value]))
  const year = Number(partMap.get('year'))
  const month = Number(partMap.get('month'))
  const day = Number(partMap.get('day'))

  if (!year || !month || !day) return null
  return { year, month, day }
}

// Spelled out: browsers differ on "Sep" and "Sept".
const SHORT_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function formatEventDate(
  value: string | Date | null | undefined,
  timeZone = DEFAULT_TIME_ZONE,
): string {
  const date = toValidDate(value)
  if (!date) return ''

  return getFormatter('en-AU', {
    timeZone: normalizeTimeZone(timeZone),
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(date)
}

export function formatEventTimeRange(
  startValue: string | Date | null | undefined,
  endValue?: string | Date | null,
  timeZone = DEFAULT_TIME_ZONE,
): string {
  const start = toValidDate(startValue)
  if (!start) return ''

  const formatter = getFormatter('en-AU', {
    timeZone: normalizeTimeZone(timeZone),
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
  const startText = formatter.format(start)
  const end = toValidDate(endValue)
  const label = getEventTimeZoneAbbreviation(start, timeZone)

  if (!end) return `${startText} ${label}`
  return `${startText} - ${formatter.format(end)} ${label}`
}

export function toTimeZoneDateKey(
  value: string | Date | null | undefined,
  timeZone = DEFAULT_TIME_ZONE,
): string {
  const parts = getTimeZoneDateParts(value, timeZone)
  if (!parts) return ''

  const year = parts.year
  const month = String(parts.month).padStart(2, '0')
  const day = String(parts.day).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function getEventTimeZoneAbbreviation(date: Date, timeZone: string): string {
  const normalizedTimeZone = normalizeTimeZone(timeZone)
  const parts = getFormatter('en-AU', {
    timeZone: normalizedTimeZone,
    timeZoneName: 'short',
  }).formatToParts(date)

  return parts.find((part) => part.type === 'timeZoneName')?.value || normalizedTimeZone
}


/* ------------------------------------------------------------------------
   The site's date styles. Each shows the "set time" (the Profile timezone,
   or the computer's when none is set) unless a zone is passed, in which
   case the caller labels it, like "(AEDT)".
   ------------------------------------------------------------------------ */

let readProfileTimeZone: () => string | null | undefined = () => undefined

/** The auth store hands over the signed-in user's Profile timezone. */
export function registerProfileTimeZone(read: () => string | null | undefined): void {
  readProfileTimeZone = read
}

/** The set time: the Profile timezone, or the computer's when none is set. */
export function getSetTimeZone(): string {
  let zone: string | null | undefined
  try {
    zone = readProfileTimeZone()
  } catch {
    zone = undefined
  }
  return isValidTimeZone(zone) ? zone : getBrowserTimeZone()
}

/** A zone's offset from UTC at an instant, in minutes: 660 for Sydney in
 *  daylight saving, -240 for New York in summer, 0 for UTC. */
function zoneOffsetMinutes(at: Date, timeZone: string): number {
  const name =
    getFormatter('en-US', { timeZone: normalizeTimeZone(timeZone), timeZoneName: 'longOffset' })
      .formatToParts(at)
      .find((part) => part.type === 'timeZoneName')?.value ?? 'GMT'
  const match = /GMT([+-])(\d{1,2})(?::(\d{2}))?/.exec(name)
  if (!match) return 0 // plain "GMT": UTC itself
  const minutes = Number(match[2]) * 60 + Number(match[3] ?? 0)
  return match[1] === '-' ? -minutes : minutes
}

const formatOffset = (minutes: number) => {
  const sign = minutes < 0 ? '-' : '+'
  const abs = Math.abs(minutes)
  return `${sign}${String(Math.floor(abs / 60)).padStart(2, '0')}:${String(abs % 60).padStart(2, '0')}`
}

/** The first ("start") or last ("end") millisecond of a calendar day
 *  ("YYYY-MM-DD") in a zone, as an ISO datetime carrying that zone's offset
 *  on that day: "2026-10-15T00:00:00.000+11:00" for the start of 15 October in
 *  Sydney. Each moment gets its own offset, so on a day the clocks change the
 *  start and end differ ("+10:00" and "+11:00" on 4 October 2026 in Sydney).
 *  Null for anything that isn't a real calendar day. */
export function zonedDayBoundary(
  isoDate: string,
  edge: 'start' | 'end',
  timeZone = getSetTimeZone(),
): string | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate)
  if (!match) return null
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])]
  const [hours, minutes, seconds, ms] = edge === 'start' ? [0, 0, 0, 0] : [23, 59, 59, 999]
  // The wall-clock moment as if it were UTC. setUTCFullYear, as Date.UTC
  // reads years 0-99 as 1900-1999.
  const at = new Date(Date.UTC(2000, 0, 1, hours, minutes, seconds, ms))
  at.setUTCFullYear(year, month - 1, day)
  const wall = at.getTime()
  if (at.getUTCFullYear() !== year || at.getUTCDate() !== day) return null // 31 February and the like
  // The zone's offset there, checked again at the real instant it gives, in
  // case a clock change falls between the two.
  let offset = zoneOffsetMinutes(new Date(wall), timeZone)
  const atInstant = zoneOffsetMinutes(new Date(wall - offset * 60_000), timeZone)
  if (atInstant !== offset) offset = atInstant
  const time = edge === 'start' ? '00:00:00.000' : '23:59:59.999'
  return `${isoDate}T${time}${formatOffset(offset)}`
}

const LONG_MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
]

const zonedParts = (value: string | Date | null | undefined, timeZone: string) => {
  const date = toValidDate(value)
  if (!date) return null
  const part = new Map(
    getFormatter('en-GB', {
      timeZone: normalizeTimeZone(timeZone),
      weekday: 'long',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hourCycle: 'h23',
    })
      .formatToParts(date)
      .map((item) => [item.type, item.value]),
  )
  const month = Number(part.get('month'))
  const hour = Number(part.get('hour'))
  if (!month || Number.isNaN(hour)) return null
  return {
    weekday: part.get('weekday') ?? '',
    year: part.get('year') ?? '',
    month,
    day: Number(part.get('day')),
    dd: part.get('day') ?? '',
    mm: part.get('month') ?? '',
    hour,
    HH: String(hour).padStart(2, '0'),
    MM: part.get('minute') ?? '',
    SS: part.get('second') ?? '',
  }
}

/** "9th", "22nd", "13th". */
export function ordinal(day: number): string {
  const teen = day % 100 >= 11 && day % 100 <= 13
  const suffix = teen ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[day % 10] ?? 'th'
  return `${day}${suffix}`
}

/** Admin and Supervisor tables: "09/10/26". */
export function formatShortDate(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${p.dd}/${p.mm}/${p.year.slice(-2)}` : ''
}

/** Admin and Supervisor tables: "09/10/26 16:12". */
export function formatShortDateTime(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${p.dd}/${p.mm}/${p.year.slice(-2)} ${p.HH}:${p.MM}` : ''
}

/** Exact moments: "09/10/26 16:12:01". */
export function formatExactTime(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${p.dd}/${p.mm}/${p.year.slice(-2)} ${p.HH}:${p.MM}:${p.SS}` : ''
}

/** Admin sentences, popups and statements: "09/10/2026 at 16:12". */
export function formatStatementTime(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${p.dd}/${p.mm}/${p.year} at ${p.HH}:${p.MM}` : ''
}

// The year only shows for a date outside this year, in the same zone.
const yearSuffix = (year: string, timeZone: string) =>
  year === zonedParts(new Date(), timeZone)?.year ? '' : ` ${year}`

/** Pages every role uses, a date alone: "9 Oct", or "9 Oct 2025" from another year. */
export function formatDayMonth(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${p.day} ${SHORT_MONTHS[p.month - 1]}${yearSuffix(p.year, timeZone)}` : ''
}

/** Pages every role uses: "9 Oct, 4:12 pm", or "9 Oct 2025, 4:12 pm" from another year. */
export function formatDayMonthTime(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  if (!p) return ''
  const hour12 = p.hour % 12 || 12
  const meridiem = p.hour < 12 ? 'am' : 'pm'
  return `${p.day} ${SHORT_MONTHS[p.month - 1]}${yearSuffix(p.year, timeZone)}, ${hour12}:${p.MM} ${meridiem}`
}

/** A date written out: "9th October 2026". */
export function formatOrdinalDate(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${ordinal(p.day)} ${LONG_MONTHS[p.month - 1]} ${p.year}` : ''
}

/** Set events: "Friday, 9th October 2026". */
export function formatEventDay(value: string | Date | null | undefined, timeZone = getSetTimeZone()): string {
  const p = zonedParts(value, timeZone)
  return p ? `${p.weekday}, ${ordinal(p.day)} ${LONG_MONTHS[p.month - 1]} ${p.year}` : ''
}

/** Set events, for a calendar day ("YYYY-MM-DD") with no time: "Friday, 9th October 2026". */
export function formatEventCalendarDay(isoDate: string | null | undefined): string {
  if (!isoDate || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return ''
  // Midday UTC lands on the same calendar day in UTC.
  return formatEventDay(`${isoDate}T12:00:00Z`, 'UTC')
}

/** A Sydney time slot on a calendar day ("YYYY-MM-DD"), from "9:30" and
 *  "10:00" clock times: "09:30 - 10:00 AEDT", or AEST in winter. */
export function formatSydneySlot(start: string, end: string, isoDate: string | null | undefined): string {
  const pad = (hhmm: string) => {
    const [hours = '', minutes = ''] = hhmm.split(':')
    return `${hours.padStart(2, '0')}:${minutes.slice(0, 2).padStart(2, '0')}`
  }
  const range = `${pad(start)} - ${pad(end)}`
  return isoDate ? `${range} ${sydneyClockOn(isoDate).name}` : range
}
