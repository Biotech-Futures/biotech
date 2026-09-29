import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { resetCsrfToken } from '@/utils/csrf'
import SetPasswordPage from '@/views/SetPasswordPage.vue'
import {
  mentorWithAccess,
  pureAgent,
  student,
  supportWithoutAccess,
  ticketAdmin
} from '@/__tests__/supportAccountFixtures'

// The page mounted on the real router and store, with fetch stubbed at the
// network: the CSRF preflight, the role-agnostic set-password endpoint, and
// the /users/me/ re-read that brings back the isAdmin/isSupport flags. The
// assertions read both what the page asked the router for and where the guard
// left the user, because the guard alone would move a support agent off
// /dashboard and hide a page that still asked for it.
describe('SetPasswordPage landing', () => {
  let pinia: ReturnType<typeof createPinia>
  let wrapper: VueWrapper | null = null
  let fetchMock: ReturnType<typeof vi.fn>

  const stubNetwork = (meAfterSetting: object) => {
    fetchMock = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
      const path = new URL(url).pathname
      const method = (init?.method || 'GET').toUpperCase()
      if (path === '/services/csrf/') {
        return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'test-token' }), { status: 200 }))
      }
      if (path === '/api/v1/set-password/' && method === 'POST') {
        return Promise.resolve(new Response(JSON.stringify({ msg: 'Password set' }), { status: 200 }))
      }
      if (path === '/api/v1/users/me/' && method === 'GET') {
        return Promise.resolve(new Response(JSON.stringify(meAfterSetting), { status: 200 }))
      }
      return Promise.resolve(new Response('{}', { status: 404 }))
    })
    vi.stubGlobal('fetch', fetchMock)
  }

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    resetCsrfToken()
    await router.push('/login')
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  const landings: Array<[string, string, object]> = [
    ['pure support agent', '/admin/tickets', pureAgent],
    ['mentor granted access', '/dashboard', mentorWithAccess],
    ['role-support account without access', '/support-access', supportWithoutAccess],
    ['admin', '/admin', ticketAdmin],
    ['student', '/dashboard', student]
  ]

  it.each(landings)(
    '%s: goes to %s once the first password is set',
    async (_label, expected, fixture) => {
      useAuthStore().loginWithUser({ ...fixture, must_change_password: true } as never)
      await router.push('/auth/set-password')
      expect(router.currentRoute.value.path).toBe('/auth/set-password')
      stubNetwork({ ...fixture, must_change_password: false })

      wrapper = mount(SetPasswordPage, { global: { plugins: [router, pinia] } })
      await flushPromises()
      const replace = vi.spyOn(router, 'replace')

      await wrapper.find('#new-password').setValue('correct-horse-9')
      await wrapper.find('#confirm-password').setValue('correct-horse-9')
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      const setCall = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/api/v1/set-password/'))
      expect(setCall?.[1]?.method).toBe('POST')
      expect(replace).toHaveBeenCalledTimes(1)
      expect(replace).toHaveBeenCalledWith(expected)
      // The navigation the page started, finished (the route's component is
      // a lazy import, which one flush does not cover).
      await replace.mock.results[0]?.value
      expect(router.currentRoute.value.path).toBe(expected)
    }
  )

  it.each(landings)(
    '%s: with no password left to set, the page itself moves on to %s',
    async (_label, expected, fixture) => {
      useAuthStore().loginWithUser(fixture as never)
      // Mounted directly: the guard never lets this account onto the route,
      // so this is the page's own fallback for a store that changed under it.
      await router.push('/profile')
      stubNetwork(fixture)
      const replace = vi.spyOn(router, 'replace')

      wrapper = mount(SetPasswordPage, { global: { plugins: [router, pinia] } })
      await flushPromises()

      expect(replace).toHaveBeenCalledTimes(1)
      expect(replace).toHaveBeenCalledWith(expected)
      await replace.mock.results[0]?.value
      expect(router.currentRoute.value.path).toBe(expected)
    }
  )
})
