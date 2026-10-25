// Constants and shared option lists for the admin user-management screens.

// "support" was added on 2026-09-04 (ported from adminweb/src/type/user.ts).
// Asked where support agents come from, the client answered: "The admin would
// create a new account for the support agent, similar to how they can
// currently create a new admin user, but rather assign the support role to
// them." So it is a role in this dropdown, and its side effect on the server
// is a SupportScope row rather than an AdminScope one: a support agent can
// work the ticket queue and nothing else.
//
// This list feeds the create/edit role select and the People role filter. It
// does NOT feed any bulk import: the backend refuses support and admin on
// every import path on purpose (BULK_IMPORTABLE_ROLES in
// backend/apps/admin/services/user.py), and userOptions.spec.ts holds both
// halves of that to the backend source.
export const USER_ROLES = ['student', 'mentor', 'supervisor', 'admin', 'support'] as const
export type UserRole = (typeof USER_ROLES)[number]

/**
 * Mentor background categories, in display order. `value` is the key the
 * backend stores (MentorProfile.BackgroundChoices). The label no longer
 * lowercases to the key, so never derive one from the other.
 */
export const MENTOR_BACKGROUND_OPTIONS = [
  { value: 'academic', label: 'Academic' },
  { value: 'industry', label: 'Industry' },
  { value: 'undergraduate', label: 'University Student – Undergraduate' },
  { value: 'postgraduate', label: 'University Student – Postgraduate' },
  { value: 'hdr', label: 'University Student – HDR' }
] as const
export type MentorBackground = (typeof MENTOR_BACKGROUND_OPTIONS)[number]['value']

export const isMentorBackground = (value: unknown): value is MentorBackground =>
  MENTOR_BACKGROUND_OPTIONS.some((option) => option.value === value)

export const INTEREST_OPTIONS = [
  'Biomedical Innovations',
  'Environmental Sustainability & Climate Tech',
  'Space & Astrobiology',
  'AI & Robotics and Smart Systems',
  'Nanotechnology & Materials Science',
  'Food & Agriculture Technology',
  'Neuroscience & Mental Health Tech',
  'Water & Energy Tech',
  'Ethical & Societal Impacts of Emerging Tech'
]

export interface AdminUserFilters {
  role: UserRole | 'all'
  country: string
  state: string
  inGroup: 'all' | 'yes' | 'no'
  status: 'all' | 'active' | 'inactive'
}

export const defaultAdminUserFilters = (): AdminUserFilters => ({
  role: 'all',
  country: 'all',
  state: 'all',
  inGroup: 'all',
  status: 'all'
})