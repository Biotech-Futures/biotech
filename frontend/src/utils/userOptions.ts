// Constants and shared option lists for the admin user-management screens.

export const USER_ROLES = ['student', 'mentor', 'supervisor', 'admin'] as const
export type UserRole = (typeof USER_ROLES)[number]

/**
 * Mentor background categories, in display order. `value` is the key the
 * backend stores (MentorProfile.BackgroundChoices); each label lowercases to it.
 */
export const MENTOR_BACKGROUND_OPTIONS = [
  { value: 'academic', label: 'Academic' },
  { value: 'industry', label: 'Industry' },
  { value: 'undergraduate', label: 'Undergraduate' },
  { value: 'postgraduate', label: 'Postgraduate' },
  { value: 'hdr', label: 'HDR' }
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