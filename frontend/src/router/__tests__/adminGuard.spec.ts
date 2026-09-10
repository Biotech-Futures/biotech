import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

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

// '/admin/matching' is deliberately absent — it redirects to /admin/groups
// (matching is a tab there). Its redirect is covered by its own test below.
const adminRoutes = [
  '/admin',
  '/admin/users',
  '/admin/groups',
  '/admin/matching',
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

  it('redirects /admin/matching to the Groups & Matching page', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    await router.push('/admin/matching')
    expect(router.currentRoute.value.path).toBe('/admin/groups')
  })

  // The Students page deep-links to /admin/matching?run=true to auto-run the
  // matcher, so the redirect has to carry the query across.
  it('preserves the query string when redirecting /admin/matching', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    await router.push('/admin/matching?run=true')
    expect(router.currentRoute.value.path).toBe('/admin/groups')
    expect(router.currentRoute.value.query.run).toBe('true')
  })

  it('sends authenticated admins who visit /login to the admin dashboard', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    await router.push('/admin')
    await router.push('/login')
    expect(router.currentRoute.value.path).toBe('/admin')
  })

  it('sends admins away from member group routes to /admin', async () => {
    const auth = useAuthStore()
    auth.loginWithUser(adminUser)

    await router.push('/groups')
    expect(router.currentRoute.value.path).toBe('/admin')

    await router.push('/groups/42')
    expect(router.currentRoute.value.path).toBe('/admin')
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
