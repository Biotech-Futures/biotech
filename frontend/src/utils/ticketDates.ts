/**
 * The ticket pages' own date formats, as the client and the designer asked
 * for them: "24 Sept 2026" in lists and the ticket header, "24 September
 * 2026, 3:37 pm" on a message, "24 Sept 2026, 3:37 pm" where there is less
 * room (client items C-05, C-06; DEC-050), read in the reader's own time
 * zone.
 *
 * They lived in utils/date.ts until main's date work of 12 October 2026
 * (0ebdedc2), which moved the platform onto shared styles in the Profile
 * timezone and removed these helpers. The ticket pages keep the formats the
 * design was checked against until the owner decides whether they follow
 * the shared styles too, so the helpers moved here rather than back into
 * that file.
 */

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
  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) return ''

  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/**
 * Format a date value into a long Australian date string.
 *
 * This helper can optionally include the weekday in the output.
 * It is useful for detailed views such as event pages, dashboards, or schedules.

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
  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) return ''

  return date.toLocaleDateString('en-AU', {
    weekday: withWeekday ? 'long' : undefined,
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

/**
 * Format a date value into a long Australian date followed by the time of day.
 *
 * Both halves are read in the reader's own time zone, the one the browser is
 * set to, so a message reads at the hour it arrived for whoever is looking.
 * Deliberately not utils/date.ts's DEFAULT_TIME_ZONE: that is UTC, and a
 * student in Sydney would see every reply stamped ten or eleven hours early.
 *
 * Example output:
 * 24 September 2026, 3:37 pm
 *
 * @param value The source date value as a string or Date object.
 * @returns The long date and the time, or an empty string if invalid.
 */
export function formatLongDateTimeAU(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) return ''

  // Joined here rather than asked of the locale in one call. Asked in one
  // call, en-AU puts " at " between them (measured on ICU 78), which is not
  // the shape the client asked for, and that joiner is locale data each
  // browser ships at its own version.
  const time = date.toLocaleTimeString('en-AU', {
    hour: 'numeric',
    minute: '2-digit',
  })
  return `${formatLongDateAU(date)}, ${time}`
}

/**
 * Format a date value into a short Australian date followed by the time of
 * day: the month abbreviated, as formatDateAU writes it.
 *
 * The same reader's-own-zone rule as formatLongDateTimeAU, for places that
 * have less room than a conversation line, such as the ticket page's header
 * pills.
 *
 * Example output:
 * 24 Sept 2026, 3:37 pm
 *
 * @param value The source date value as a string or Date object.
 * @returns The short date and the time, or an empty string if invalid.
 */
export function formatDateTimeAU(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) return ''

  const time = date.toLocaleTimeString('en-AU', {
    hour: 'numeric',
    minute: '2-digit',
  })
  return `${formatDateAU(date)}, ${time}`
}
