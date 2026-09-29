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

// The roles that carry no geography, so the editor hides the country and state
// fields for them, a role change to one clears them, validation does not ask
// for a country, the create call sends neither and the update call sends
// null for both. Support is here for the same reason admin is: nothing reads
// an agent's country (Ticket.region snapshots the requester's, taken at
// submission), so asking for one would be asking for a fact no code looks at.
//
// The backend twin is ROLES_WITHOUT_GEOGRAPHY in
// backend/apps/admin/services/user.py. The two must agree: "support" was once
// added to the create path's exemption and not the update path's, so an agent
// could be created and then never saved again ("Country cannot be cleared").
// userOptions.spec.ts reads the backend file to keep them in step.
export const ROLES_WITHOUT_GEOGRAPHY: readonly UserRole[] = ['admin', 'support']

export function roleHasGeography(role: string): boolean {
  return !(ROLES_WITHOUT_GEOGRAPHY as readonly string[]).includes(role)
}

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