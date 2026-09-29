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
