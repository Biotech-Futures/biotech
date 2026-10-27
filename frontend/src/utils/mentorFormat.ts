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

/**
 * Why a mentor needs attention, or null if they do not.
 *
 * "inactive" and "idle" are different facts, not degrees of one. Inactive is
 * an account an admin disabled. Idle is an enabled account that has gone
 * quiet, so a mentor with a working login is never reported inactive.
 *
 * The quiet test mirrors `_idle_mentor_ids` on the backend exactly, down to
 * the threshold, because the two are read side by side: the matcher scores a
 * mentor while this badges the row next to that score. Three things excuse
 * silence, and any one is enough:
 *
 * - they spoke inside the window;
 * - they joined inside it, so there has not been time to judge them;
 * - they have no group, so there is nowhere to speak. Holding that against
 *   them would be a deadlock - passed over for never posting, and unable to
 *   post without a group.
 *
 * `dateJoined` and `currentAssignedCount` are optional: a caller that cannot
 * supply one simply does not get that excuse, which is the stricter reading.
 */
export const mentorConcern = (
  mentor: {
    isActive: boolean
    lastMessageAt: string | null
    dateJoined?: string | null
    currentAssignedCount?: number
  },
  idleDays: number = DEFAULT_IDLE_DAYS,
): MentorConcern => {
  if (!mentor.isActive) return 'inactive'

  const sinceMessage = daysSince(mentor.lastMessageAt)
  const sinceJoining = daysSince(mentor.dateJoined ?? null)

  const spokeRecently = sinceMessage !== null && sinceMessage < idleDays
  const joinedRecently = sinceJoining !== null && sinceJoining < idleDays
  const hasNoGroup = mentor.currentAssignedCount === 0

  return spokeRecently || joinedRecently || hasNoGroup ? null : 'idle'
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