// Constants and shared option lists for the admin user-management screens.

export const USER_ROLES = ['student', 'mentor', 'supervisor', 'admin'] as const
export type UserRole = (typeof USER_ROLES)[number]

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

export const PAGE_SIZE_OPTIONS = [25, 50, 100, 200]

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