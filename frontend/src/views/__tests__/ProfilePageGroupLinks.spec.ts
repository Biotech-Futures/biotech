import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ProfilePage from '@/views/ProfilePage.vue'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { setSupervisorPages } from '@/composables/useSupervisorPages'

// The application's own router and guards: a group link is followed as a
// click in the app would be. Management > Supervisor Pages Visibility is set
// per test; the server is never asked.
vi.mock('@/utils/managementAPI', async (original) => ({
  ...(await original<typeof import('@/utils/managementAPI')>()),
  fetchSupervisorPages: vi.fn(async () => ({ shown: false })),
}))
vi.mock('@/utils/csrf', () => ({
  buildSessionHeaders: () => ({ 'Content-Type': 'application/json' }),
  ensureCsrfCookie: async () => true,
}))

const page = (...groups: [number, string][]) =>
  new Response(JSON.stringify({ results: groups.map(([id, group_name]) => ({ id, group_name })), next: null }))

async function openProfile() {
  await router.push('/profile')
  const wrapper = mount(ProfilePage, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

/** Click and wait for the router to finish, lazy group page included. */
async function follow(link: { trigger: (event: string) => Promise<void> }) {
  const done = new Promise<void>((resolve) => {
    const stop = router.afterEach(() => {
      stop()
      resolve()
    })
  })
  await link.trigger('click')
  await done
  await flushPromises()
}

describe("a supervisor's profile group links, through the app's router", () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.loginWithUser({
      id: 7, email: 'sarah@example.test', first_name: 'Sarah', last_name: 'Miller',
      current_role_name: 'supervisor', supervised_students: [],
    } as never)
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn(async (input: string) =>
      input.includes('page_size=100&mine=true') ? page([1, 'BTF1'], [2, 'BTF2']) : new Response('{"results":[]}')))
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  const groupLink = (wrapper: Awaited<ReturnType<typeof openProfile>>, name: string) =>
    wrapper.findAll('[data-test="supervisor-groups"] a').find((link) => link.text() === name)!

  it.each([[1, 'BTF1'], [2, 'BTF2']])('opens group %i\'s page from %s while supervisor pages are shown', async (id, name) => {
    setSupervisorPages({ shown: true })
    const wrapper = await openProfile()

    await follow(groupLink(wrapper, name))

    expect(router.currentRoute.value.name).toBe('group-detail')
    expect(router.currentRoute.value.params.id).toBe(String(id))
    wrapper.unmount()
  })

  it('lists the groups without links while supervisor pages are hidden', async () => {
    setSupervisorPages({ shown: false })
    const wrapper = await openProfile()

    const section = wrapper.find('[data-test="supervisor-groups"]')
    expect(section.findAll('li').map((item) => item.text())).toEqual(['BTF1', 'BTF2'])
    expect(section.find('a').exists()).toBe(false)
    // The rule the names follow: the app sends a supervisor at a group page back here.
    await router.push({ name: 'group-detail', params: { id: '1' } })
    expect(router.currentRoute.value.name).toBe('profile')
    wrapper.unmount()
  })

  it('turns the names into links when an admin shows the pages', async () => {
    setSupervisorPages({ shown: false })
    const wrapper = await openProfile()
    expect(wrapper.find('[data-test="supervisor-groups"] a').exists()).toBe(false)

    setSupervisorPages({ shown: true })
    await flushPromises()
    await follow(groupLink(wrapper, 'BTF2'))
    expect(router.currentRoute.value.params.id).toBe('2')
    wrapper.unmount()
  })
})
