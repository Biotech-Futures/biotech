/**
 * The ticket pages' own date formats, as the client and the designer asked
 * for them: "24 Sept 2026" in lists and the ticket header, "24 September
 * 2026, 3:37 pm" on a message, "24 Sept 2026, 3:37 pm" where there is less
 * room (client items C-05, C-06; DEC-050).
 *
 * They lived in utils/date.ts until main's date work of 12 October 2026
 * (0ebdedc2), which moved the platform onto shared styles in the Profile
 * timezone and removed these helpers. The ticket pages keep the formats the
 * design was checked against, so the helpers moved here rather than back
 * into that file.
 *
 * The zone is the platform's: the "set time" of utils/date.ts, which is the
 * Profile timezone, or the computer's when the profile names none. That was
 * the reader's browser zone until 18 October 2026, when the owner chose to
 * follow the rest of the platform.
 */
import { getSetTimeZone } from '@/utils/date'

const toDate = (value: string | Date): Date | null => {
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const shortDate = (date: Date, timeZone: string) =>
  date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone,
  })

const longDate = (date: Date, timeZone: string, withWeekday = false) =>
  date.toLocaleDateString('en-AU', {
    weekday: withWeekday ? 'long' : undefined,
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    timeZone,
  })

// Asked for apart from the date rather than in one call. Asked in one call,
// en-AU puts " at " between them (measured on ICU 78), which is not the shape
// the client asked for, and that joiner is locale data each browser ships at
// its own version.
const timeOfDay = (date: Date, timeZone: string) =>
  date.toLocaleTimeString('en-AU', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone,
  })

/**
 * Format a date value into a short Australian date.
 *
 * Example output:
 * 24 Sept 2026
 *
 * @param value The source date value as a string or Date object.
 * @returns The short date, or an empty string if invalid.
 */
export function formatDateAU(value: string | Date): string {
  const date = toDate(value)
  return date ? shortDate(date, getSetTimeZone()) : ''
}

/**
 * Format a date value into a long Australian date string.
 *
 * This helper can optionally include the weekday in the output.
 *
 * Example output without weekday:
 * 5 April 2026
 *
 * Example output with weekday:
 * Saturday, 5 April 2026
 *
 * @param value The source date value as a string or Date object.
 * @param withWeekday Whether to include the weekday in the formatted result.
 * @returns A long formatted Australian date string, or an empty string if invalid.
 */
export function formatLongDateAU(value: string | Date, withWeekday = false): string {
  const date = toDate(value)
  return date ? longDate(date, getSetTimeZone(), withWeekday) : ''
}

/**
 * Format a date value into a long Australian date followed by the time of day.
 *
 * The date and the time are read in one zone, so a message sent late in the
 * evening somewhere cannot land on the wrong day next to the right hour.
 *
 * Example output:
 * 24 September 2026, 3:37 pm
 *
 * @param value The source date value as a string or Date object.
 * @returns The long date and the time, or an empty string if invalid.
 */
export function formatLongDateTimeAU(value: string | Date): string {
  const date = toDate(value)
  if (!date) return ''
  const timeZone = getSetTimeZone()
  return `${longDate(date, timeZone)}, ${timeOfDay(date, timeZone)}`
}

/**
 * Format a date value into a short Australian date followed by the time of
 * day: the month abbreviated, as formatDateAU writes it.
 *
 * For places that have less room than a conversation line, such as the
 * ticket page's header pills.
 *
 * Example output:
 * 24 Sept 2026, 3:37 pm
 *
 * @param value The source date value as a string or Date object.
 * @returns The short date and the time, or an empty string if invalid.
 */
export function formatDateTimeAU(value: string | Date): string {
  const date = toDate(value)
  if (!date) return ''
  const timeZone = getSetTimeZone()
  return `${shortDate(date, timeZone)}, ${timeOfDay(date, timeZone)}`
}
