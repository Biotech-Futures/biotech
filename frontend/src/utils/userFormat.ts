import type { AdminUser, AdminUserCountry, AdminUserState } from '@/utils/adminAPI'

/** Capitalized role name (e.g. 'student' -> 'Student'); '—' for nothing. */
export const roleLabel = (role: string | null | undefined) =>
  role ? role.charAt(0).toUpperCase() + role.slice(1) : '—'

export const labelizeCountry = (country: AdminUserCountry | null | undefined) =>
  country?.countryName ?? 'Unassigned'

export const labelizeState = (state: AdminUserState | null | undefined) =>
  state?.stateName ?? '-'

// The backend list payload has firstName/lastName, not a combined `name`.
export const userName = (user: AdminUser | null | undefined) =>
  [user?.firstName, user?.lastName].filter(Boolean).join(' ').trim() || '—'

/** DataTable slots hand rows out as Record<string, unknown>. */
export const toAdminUser = (row: Record<string, unknown>): AdminUser => row as unknown as AdminUser

/** First few interests for the table cell, with the overflow hidden behind a "+n". */
export const visibleInterests = (user: AdminUser) => (user.interests ?? []).slice(0, 3)

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

export const formatLoginDate = (value: string | null) => {
  if (!value) return ''
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString()
}

export const formatFullDate = (value: string | null | undefined) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString()
}