import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'
import {
  mentorWithAccess,
  pureAgent,
  student,
  supportWithoutAccess,
  ticketAdmin
} from '@/__tests__/supportAccountFixtures'

const adminUser = {
  id: 1,
  email: 'admin@example.com',
  first_name: 'Admin',
  last_name: 'User',
  current_role_name: 'admin'
} as never

const memberUser = {
  id: 2,
  email: 'member@example.com',
  first_name: 'Member',
  last_name: 'User',
  current_role_name: 'student'
} as never

const adminRoutes = [
  '/admin',
  '/admin/users',
  '/admin/groups',
  '/admin/tasks'
]

describe('admin router guard', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    // Reset the singleton router to a neutral, unauthenticated state so tests
    // don't inherit navigation/auth state from one another.
    await router.push('/login')
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('redirects unauthenticated users from admin routes to /login', async () => {
    await router.push('/admin/users')
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it('redirects authenticated non-admins from admin routes to /dashboard', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(memberUser)

    await router.push('/admin')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('lets authenticated admins reach every admin route', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    for (const path of adminRoutes) {
      await router.push(path)
      expect(router.currentRoute.value.path).toBe(path)
    }
  })

  it('sends authenticated admins who visit /login to the admin dashboard', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    await router.push('/admin')
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('lets admins open any group page and its submission', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    await router.push('/groups/42')
    expect(router.currentRoute.value.path).toBe('/groups/42')
    await router.push('/groups/42/submission')
    expect(router.currentRoute.value.path).toBe('/groups/42/submission')
  })

  it("lands an admin on the first of every group, reading every page of the list", async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    const pages: Record<string, unknown> = {
      '': { results: [{ id: 7, group_name: 'BTF1' }], next: 'https://elsewhere.example/groups/groups/?page=2' },
      '?page=2': { results: [{ id: 9, group_name: 'BTF2' }], next: null }
    }
    const fetchMock = vi.fn().mockImplementation((url: string) =>
      Promise.resolve(new Response(JSON.stringify(pages[new URL(url).search]), { status: 200 }))
    )
    globalThis.fetch = fetchMock

    await router.push('/groups')
    expect(router.currentRoute.value.path).toBe('/groups/7')
    // Not only the admin's own groups; the next page is asked of our own API.
    const urls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(urls.every((url) => !url.includes('mine=true'))).toBe(true)
    expect(urls[1]).toMatch(/^http:\/\/localhost:8000\/groups\/groups\/\?page=2$/)
  })

  it('sends an admin to Admin > Groups while there are no groups at all', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)
    globalThis.fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response('{"results": [], "next": null}', { status: 200 })))
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})

    await router.push('/groups')
    expect(router.currentRoute.value.path).toBe('/admin/groups')
    expect(alert).not.toHaveBeenCalled()
  })

  it('lets non-admins reach the member groups route', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(memberUser)

    // Stub the groups fetch and alert so the /groups beforeEnter resolver
    // falls back to /dashboard (no memberships) without real network/UI.
    globalThis.fetch = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response('[]', { status: 200 })))
    vi.spyOn(window, 'alert').mockImplementation(() => {})

    // Non-admins are not redirected to /admin; the resolver sends them to
    // /dashboard when they belong to no groups.
    await router.push('/groups')
    expect(router.currentRoute.value.path).not.toBe('/admin')
  })
})

// Support tickets (port-design.md sections 1-3). The real router and the real
// store: each account signs in exactly as /users/me/ describes it, then opens
// a page, and the assertion is where the guard actually left them.
describe('support ticket access in the router guard', () => {
  const groupsResponse = { results: [{ id: 7, group_name: 'BTF1' }], next: null }
  let fetchMock: ReturnType<typeof vi.fn>
  let alertSpy: ReturnType<typeof vi.spyOn>

  const signIn = (fixture: object) => useAuthStore().loginWithUser(fixture as never)

  beforeEach(async () => {
    setActivePinia(createPinia())
    await router.push('/login')
    // Only /groups fetches (its beforeEnter reads the groups store): one
    // group, so a member who may open it lands on it rather than on an alert.
    fetchMock = vi
      .fn()
      .mockImplementation(() => Promise.resolve(new Response(JSON.stringify(groupsResponse), { status: 200 })))
    vi.stubGlobal('fetch', fetchMock)
    alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    alertSpy.mockRestore()
    localStorage.clear()
  })

  // [account, path opened, where the guard leaves them, the account's /users/me/]
  const table: Array<[string, string, string, object]> = [
    ['pure support agent', '/admin/tickets', '/admin/tickets', pureAgent],
    ['pure support agent', '/admin/tickets/audit', '/admin/tickets/audit', pureAgent],
    ['pure support agent', '/admin/tickets/analytics', '/admin/tickets/analytics', pureAgent],
    ['pure support agent', '/admin/support-agents', '/admin/tickets', pureAgent],
    ['pure support agent', '/admin/users', '/admin/tickets', pureAgent],
    ['pure support agent', '/dashboard', '/admin/tickets', pureAgent],
    ['pure support agent', '/groups', '/admin/tickets', pureAgent],
    ['pure support agent', '/support', '/admin/tickets', pureAgent],
    ['pure support agent', '/grading/by-group', '/admin/tickets', pureAgent],
    ['pure support agent', '/profile', '/profile', pureAgent],
    // Signing in again by magic link, or resetting a password, while signed in.
    ['pure support agent', '/auth/callback', '/auth/callback', pureAgent],
    ['pure support agent', '/auth/reset-password', '/auth/reset-password', pureAgent],

    ['mentor granted access', '/admin/tickets', '/admin/tickets', mentorWithAccess],
    ['mentor granted access', '/admin/tickets/audit', '/admin/tickets/audit', mentorWithAccess],
    ['mentor granted access', '/admin/support-agents', '/dashboard', mentorWithAccess],
    ['mentor granted access', '/dashboard', '/dashboard', mentorWithAccess],
    ['mentor granted access', '/groups', '/groups/7', mentorWithAccess],
    ['mentor granted access', '/profile', '/profile', mentorWithAccess],

    ['role-support account without access', '/admin/tickets', '/support-access', supportWithoutAccess],
    ['role-support account without access', '/admin/tickets/audit', '/support-access', supportWithoutAccess],
    ['role-support account without access', '/admin/support-agents', '/support-access', supportWithoutAccess],
    ['role-support account without access', '/dashboard', '/support-access', supportWithoutAccess],
    ['role-support account without access', '/groups', '/support-access', supportWithoutAccess],
    ['role-support account without access', '/profile', '/profile', supportWithoutAccess],
    ['role-support account without access', '/auth/callback', '/auth/callback', supportWithoutAccess],

    ['admin', '/admin/tickets', '/admin/tickets', ticketAdmin],
    ['admin', '/admin/tickets/audit', '/admin/tickets/audit', ticketAdmin],
    ['admin', '/admin/support-agents', '/admin/support-agents', ticketAdmin],
    ['admin', '/dashboard', '/dashboard', ticketAdmin],
    ['admin', '/groups', '/groups/7', ticketAdmin],
    ['admin', '/profile', '/profile', ticketAdmin],

    ['student', '/admin/tickets', '/dashboard', student],
    ['student', '/admin/tickets/audit', '/dashboard', student],
    ['student', '/admin/support-agents', '/dashboard', student],
    ['student', '/dashboard', '/dashboard', student],
    ['student', '/groups', '/groups/7', student],
    ['student', '/profile', '/profile', student]
  ]

  it.each(table)('%s opening %s ends on %s', async (_label, path, expected, fixture) => {
    signIn(fixture)
    await router.push(path)
    expect(router.currentRoute.value.path).toBe(expected)
  })

  it('never runs the /groups resolver for a pure support agent, so no alert and no groups request', async () => {
    signIn(pureAgent)
    await router.push('/groups')
    expect(router.currentRoute.value.path).toBe('/admin/tickets')
    expect(fetchMock).not.toHaveBeenCalled()
    expect(alertSpy).not.toHaveBeenCalled()
  })

  const landings: Array<[string, string, object]> = [
    ['pure support agent', '/admin/tickets', pureAgent],
    ['mentor granted access', '/dashboard', mentorWithAccess],
    ['role-support account without access', '/support-access', supportWithoutAccess],
    ['admin', '/admin', ticketAdmin],
    ['student', '/dashboard', student]
  ]

  it.each(landings)('%s: signed in, /login bounces to %s', async (_label, expected, fixture) => {
    signIn(fixture)
    // Somewhere every account may stay, so the /login push is a real navigation.
    await router.push('/profile')
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe(expected)
  })

  it.each(landings)(
    '%s: with no password left to set, /auth/set-password moves on to %s',
    async (_label, expected, fixture) => {
      signIn(fixture)
      await router.push('/profile')
      await router.push('/auth/set-password')
      expect(router.currentRoute.value.path).toBe(expected)
    }
  )

  it('puts setting a first password ahead of the queue for a new support agent', async () => {
    signIn({ ...pureAgent, must_change_password: true })
    await router.push('/admin/tickets')
    expect(router.currentRoute.value.path).toBe('/auth/set-password')
  })

  it('keeps the ?ticket= deep link from a screening ticket when an agent opens it', async () => {
    // The backend's link is FRONTEND_BASE_URL/#/admin/tickets?ticket=<id>
    // (apps/tickets/services/handoff.py); the queue page reads the query.
    signIn(pureAgent)
    await router.push('/admin/tickets?ticket=42')
    expect(router.currentRoute.value.name).toBe('admin-tickets')
    expect(router.currentRoute.value.query.ticket).toBe('42')
  })
})
