import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import {
  mentorWithAccess,
  pureAgent,
  student,
  supportWithoutAccess,
  ticketAdmin
} from '@/__tests__/supportAccountFixtures'

// The real store, signed in with /users/me/-shaped users. The point of these
// getters is which truth each one reads: the ticket side reads the server's
// isAdmin / isSupport flags, never the role name, and the role name decides
// only who the account is.
describe('auth store support getters', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  const signIn = (user: object) => {
    const auth = useAuthStore()
    auth.loginWithUser(user as never)
    return auth
  }

  it.each([
    ['pure support agent', pureAgent, { role: 'support', label: 'Support', canWork: true, ticketAdmin: false, supportOnly: true }],
    ['mentor granted access', mentorWithAccess, { role: 'mentor', label: 'Mentor', canWork: true, ticketAdmin: false, supportOnly: false }],
    ['role-support account without access', supportWithoutAccess, { role: 'support', label: 'Support', canWork: false, ticketAdmin: false, supportOnly: true }],
    ['admin', ticketAdmin, { role: 'admin', label: 'Administrator', canWork: true, ticketAdmin: true, supportOnly: false }],
    ['student', student, { role: 'student', label: 'Student', canWork: false, ticketAdmin: false, supportOnly: false }]
  ] as Array<[string, object, { role: string; label: string; canWork: boolean; ticketAdmin: boolean; supportOnly: boolean }]>)(
    '%s',
    (_label, fixture, expected) => {
      const auth = signIn(fixture)
      expect({
        role: auth.normalizedRole,
        label: auth.roleLabel,
        canWork: auth.canWorkTickets,
        ticketAdmin: auth.isTicketAdmin,
        supportOnly: auth.isSupportOnly
      }).toEqual(expected)
    }
  )

  it('folds the case of the support role name, like the other roles', () => {
    for (const name of ['Support', 'SUPPORT']) {
      const auth = signIn({ ...pureAgent, current_role_name: name })
      expect(auth.normalizedRole).toBe('support')
      expect(auth.roleLabel).toBe('Support')
    }
  })

  it('no longer counts a support agent as a student', () => {
    const auth = signIn(pureAgent)
    expect(auth.isStudent).toBe(false)
    expect(auth.isMentor).toBe(false)
    expect(auth.isSupervisor).toBe(false)
    expect(auth.isTeacher).toBe(false)
    expect(auth.isAdmin).toBe(false)
  })

  it('does not grant the queue from an admin role name without the server flag', () => {
    // A cached user from before the flags existed, or an account whose role
    // says admin while the server disagrees: the queue follows the server.
    const auth = signIn({ ...ticketAdmin, isSupport: undefined, isAdmin: undefined })
    expect(auth.isAdmin).toBe(true)
    expect(auth.canWorkTickets).toBe(false)
    expect(auth.isTicketAdmin).toBe(false)
  })

  it('takes ticket-admin rights from the server flag even when the role name is not admin', () => {
    const auth = signIn({ ...student, isAdmin: true, isSupport: true })
    expect(auth.isAdmin).toBe(false)
    expect(auth.isTicketAdmin).toBe(true)
    expect(auth.canWorkTickets).toBe(true)
  })

  it('does not treat a support-role account the server calls an admin as support-only', () => {
    const auth = signIn({ ...pureAgent, isAdmin: true })
    expect(auth.normalizedRole).toBe('support')
    expect(auth.isSupportOnly).toBe(false)
  })

  it('reads the flags as strictly true, so a missing or non-boolean flag grants nothing', () => {
    const auth = signIn({ ...mentorWithAccess, isSupport: 'true', isAdmin: 1 })
    expect(auth.canWorkTickets).toBe(false)
    expect(auth.isTicketAdmin).toBe(false)
  })
})
