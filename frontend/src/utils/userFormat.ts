import type { AdminUser, AdminUserCountry, AdminUserState } from '@/utils/adminAPI'
import { formatExactTime } from '@/utils/date'
import { MENTOR_BACKGROUND_OPTIONS } from '@/utils/userOptions'

/** Capitalized role name (e.g. 'student' -> 'Student'); '—' for nothing. */
export const roleLabel = (role: string | null | undefined) =>
  role ? role.charAt(0).toUpperCase() + role.slice(1) : '—'

/**
 * Label for a stored mentor background ('hdr' -> 'HDR'). An older free-text
 * value outside the five categories is shown as stored; '—' for nothing.
 */
export const mentorBackgroundLabel = (value: string | null | undefined) =>
  MENTOR_BACKGROUND_OPTIONS.find((option) => option.value === value)?.label ?? (value || '—')

export const labelizeCountry =(country: AdminUserCountry | null | undefined) =>
  country?.countryName ?? 'Unassigned'

export const labelizeState = (state: AdminUserState | null | undefined) =>
  state?.stateName ?? '-'

// The backend list payload has firstName/lastName, not a combined `name`.
export const userName = (user: AdminUser | null | undefined) =>
  [user?.firstName, user?.lastName].filter(Boolean).join(' ').trim() || '—'

/** DataTable slots hand rows out as Record<string, unknown>. */
export const toAdminUser = (row: Record<string, unknown>): AdminUser => row as unknown as AdminUser

export const joinInterests = (interests: string[] | undefined | null) =>
  interests && interests.length ? interests.join(', ') : '—'

export const supervisorLabel = (user: AdminUser) => {
  if (!user.supervisorName && !user.supervisorEmail) return '—'
  return [user.supervisorName, user.supervisorEmail ? `(${user.supervisorEmail})` : '']
    .filter(Boolean)
    .join(' ')
}

export const superviseesLabel = (user: AdminUser) =>
  (user.supervisees || []).map((s) => `${s.name} (${s.email})`).join(', ')

/** An exact moment, "09/10/26 16:12:01", or '—' for nothing. */
export const formatFullDate = (value: string | null | undefined) => formatExactTime(value) || '—'