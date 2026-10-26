import type { AdminMentorAvailability, AdminMentorDetail } from '@/utils/adminAPI'

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/** Whole days since a date, or null when the value is missing/invalid. */
export const daysSince = (dateStr: string | null): number | null => {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  return Math.floor(diff / (1000 * 60 * 60 * 24))
}

/** Default threshold for "has gone quiet", in days. */
export const DEFAULT_IDLE_DAYS = 30

/**
 * Why a mentor needs replacing, or null when they are fine.
 *
 * Two different situations used to share the word "inactive", which is why
 * the Mentors page and Matched Groups disagreed on how many there were:
 *
 *  - `inactive` - the account itself is deactivated; they cannot take part.
 *  - `idle`     - the account is fine, but they have not messaged recently.
 */
export type MentorConcern = 'inactive' | 'idle' | null

export const mentorConcern = (
  mentor: { isActive: boolean; lastMessageAt: string | null; currentAssignedCount?: number },
  idleDays: number = DEFAULT_IDLE_DAYS,
): MentorConcern => {
  if (!mentor.isActive) return 'inactive'
  const days = daysSince(mentor.lastMessageAt)
  if (days !== null) return days >= idleDays ? 'idle' : null
  // Never posted. That only counts against a mentor who had somewhere to post:
  // one with no group cannot message, so their silence says nothing about them
  // and marking them idle would lock them out of ever being assigned one.
  // A caller that does not know the count keeps the old reading.
  return mentor.currentAssignedCount === 0 ? null : 'idle'
}

export const isEffectivelyInactive = (mentor: AdminMentorDetail, inactiveDaysValue: number): boolean =>
  mentorConcern(mentor, inactiveDaysValue) !== null

export const lastMessageDays = (dateStr: string): number => daysSince(dateStr) ?? 0

/** "Today", "1 day ago", "12 days ago", counted like the inactive highlight. */
export const relativeDays = (dateStr: string): string => {
  const days = daysSince(dateStr)
  if (days === null || Number.isNaN(days)) return ''
  if (days <= 0) return 'Today'
  return `${days} ${days === 1 ? 'day' : 'days'} ago`
}

/** A calendar date with no time ("2026-10-09") as "09/10/26", so it never
 *  moves a day with the timezone. */
export const formatCalendarDate = (isoDate: string | null | undefined): string => {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(isoDate ?? '')
  if (!match) return isoDate ?? ''
  const [, year = '', month, day] = match
  return `${day}/${month}/${year.slice(-2)}`
}

export const sortedAvailability = (availability: AdminMentorAvailability[]) =>
  [...availability].sort((a, b) => a.weekday - b.weekday)