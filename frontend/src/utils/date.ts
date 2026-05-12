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
 * Format a date value for announcement display.
 *
 * This function is similar to the short Australian date formatter,
 * but it provides a friendly fallback message when the date is invalid.
 *
 * Example output:
 * 5 Apr 2026
 *
 * Fallback output:
 * Recently posted
 *
 * @param value The source date value as a string or Date object.
 * @returns A short formatted date string for announcements, or a fallback message if invalid.
 */
export function formatAnnouncementDateAU(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value)

  if (Number.isNaN(date.getTime())) return 'Recently posted'

  return date.toLocaleDateString('en-AU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

const EVENT_TIME_ZONE = 'UTC'

const toValidDate = (value: string | Date | null | undefined): Date | null => {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatEventDateUTC(value: string | Date | null | undefined): string {
  const date = toValidDate(value)
  if (!date) return ''

  return date.toLocaleDateString('en-AU', {
    timeZone: EVENT_TIME_ZONE,
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

export function formatEventTimeRangeUTC(
  startValue: string | Date | null | undefined,
  endValue?: string | Date | null,
): string {
  const start = toValidDate(startValue)
  if (!start) return ''

  const options: Intl.DateTimeFormatOptions = {
    timeZone: EVENT_TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }
  const formatter = new Intl.DateTimeFormat('en-AU', options)
  const startText = formatter.format(start)
  const end = toValidDate(endValue)

  if (!end) return `${startText} UTC`
  return `${startText} - ${formatter.format(end)} UTC`
}

export function toUTCDateKey(value: string | Date | null | undefined): string {
  const date = toValidDate(value)
  if (!date) return ''

  const year = date.getUTCFullYear()
  const month = String(date.getUTCMonth() + 1).padStart(2, '0')
  const day = String(date.getUTCDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}
