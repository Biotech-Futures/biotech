import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { RouterView } from 'vue-router'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import {
  mentorWithAccess,
  pureAgent,
  student,
  supportWithoutAccess,
  ticketAdmin
} from '@/__tests__/supportAccountFixtures'

// Rendered through the real route table: /support-access resolves to the
// page exactly as it does in the app, on the real router and store.
const Host = defineComponent({ render: () => h(RouterView) })

describe('SupportAccessPage', () => {
  let pinia: ReturnType<typeof createPinia>
  let wrapper: VueWrapper | null = null

  beforeEach(async () => {
    pinia = createPinia()
    setActivePinia(pinia)
    await router.push('/login')
    // The page a user is moved on to renders in the host and loads its own
    // data; answer it with nothing rather than let it reach the network.
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(() => Promise.resolve(new Response('[]', { status: 200 })))
    )
  })

  afterEach(() => {
    wrapper?.unmount()
    wrapper = null
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    localStorage.clear()
  })

  it('tells a role-support account without queue access why there is nothing here', async () => {
    useAuthStore().loginWithUser(supportWithoutAccess as never)
    const replace = vi.spyOn(router, 'replace')
    // Where signing in, the guard and /login all send this account.
    await router.push('/dashboard')
    wrapper = mount(Host, { global: { plugins: [router, pinia] } })
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/support-access')
    expect(replace).not.toHaveBeenCalled()
    expect(wrapper.find('h1').text()).toBe('Support queue')
    expect(wrapper.find('.support-access__text').text()).toBe(
      'Your account does not have access to the support queue. If you think it should, ask an administrator to grant you support access.'
    )
    expect(wrapper.find('.support-access__account').text()).toBe('Signed in as revoked@example.com')
  })

  const others: Array<[string, string, object]> = [
    ['pure support agent', '/admin/tickets', pureAgent],
    ['mentor granted access', '/dashboard', mentorWithAccess],
    ['admin', '/admin', ticketAdmin],
    ['student', '/dashboard', student]
  ]

  it.each(others)('%s: opening the address moves on to %s', async (_label, expected, fixture) => {
    useAuthStore().loginWithUser(fixture as never)
    await router.push('/support-access')
    // The guard lets these accounts open it; the page is what moves them on.
    expect(router.currentRoute.value.path).toBe('/support-access')
    const replace = vi.spyOn(router, 'replace')

    wrapper = mount(Host, { global: { plugins: [router, pinia] } })
    await flushPromises()

    expect(replace).toHaveBeenCalledTimes(1)
    expect(replace).toHaveBeenCalledWith(expected)
    // The navigation the page started, finished (lazy route components).
    await replace.mock.results[0]?.value
    expect(router.currentRoute.value.path).toBe(expected)
  })
})
