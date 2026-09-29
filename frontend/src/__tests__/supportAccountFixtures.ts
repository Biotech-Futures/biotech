// The five accounts every support-entry spec is checked against (guard,
// sidebar, post-login redirect, set-password, the support-access page). One
// copy, so the specs cannot drift into testing different people under the
// same name.
//
// Shaped like /users/me/ (MeSerializer): current_role_name is the role, and
// isAdmin / isSupport are the server's own flags. isSupport is true for admins
// too, exactly as the server sends it.

interface SupportAccountFixture {
  id: number
  email: string
  first_name: string
  last_name: string
  current_role_name: string
  timezone: string
  must_change_password: boolean
  isAdmin: boolean
  isSupport: boolean
}

// A support agent who is not an admin: the queue and nothing else.
export const pureAgent: SupportAccountFixture = {
  id: 11,
  email: 'agent@example.com',
  first_name: 'Sam',
  last_name: 'Reid',
  current_role_name: 'support',
  timezone: 'UTC',
  must_change_password: false,
  isAdmin: false,
  isSupport: true
}

// A mentor granted access on the roster: keeps their member pages, gains the queue.
export const mentorWithAccess: SupportAccountFixture = {
  id: 12,
  email: 'mentor@example.com',
  first_name: 'Maya',
  last_name: 'Chen',
  current_role_name: 'mentor',
  timezone: 'UTC',
  must_change_password: false,
  isAdmin: false,
  isSupport: true
}

// Role support, but the SupportScope row is gone (revoked on the roster).
export const supportWithoutAccess: SupportAccountFixture = {
  id: 13,
  email: 'revoked@example.com',
  first_name: 'Riley',
  last_name: 'Park',
  current_role_name: 'support',
  timezone: 'UTC',
  must_change_password: false,
  isAdmin: false,
  isSupport: false
}

export const ticketAdmin: SupportAccountFixture = {
  id: 14,
  email: 'admin@example.com',
  first_name: 'Ada',
  last_name: 'Admin',
  current_role_name: 'admin',
  timezone: 'UTC',
  must_change_password: false,
  isAdmin: true,
  isSupport: true
}

export const student: SupportAccountFixture = {
  id: 15,
  email: 'student@example.com',
  first_name: 'Stella',
  last_name: 'Nguyen',
  current_role_name: 'student',
  timezone: 'UTC',
  must_change_password: false,
  isAdmin: false,
  isSupport: false
}

export const supportAccounts = [
  ['pure support agent', pureAgent],
  ['mentor granted access', mentorWithAccess],
  ['role-support account without access', supportWithoutAccess],
  ['admin', ticketAdmin],
  ['student', student]
] as const

// Where each account belongs when nothing else says where to go.
export const expectedLanding: Record<number, string> = {
  [pureAgent.id]: '/admin/tickets',
  [mentorWithAccess.id]: '/dashboard',
  [supportWithoutAccess.id]: '/support-access',
  [ticketAdmin.id]: '/admin',
  [student.id]: '/dashboard'
}
