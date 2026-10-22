import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProfilePage from '@/views/ProfilePage.vue'
import { useAuthStore } from '@/stores/auth'
import { useGroupsStore } from '@/stores/groups'
import { setSupervisorPages } from '@/composables/useSupervisorPages'
import { formatDayMonthTime } from '@/utils/date'

vi.mock('@/utils/csrf', () => ({
  buildSessionHeaders: () => ({ 'Content-Type': 'application/json' }),
  ensureCsrfCookie: async () => true,
}))

describe('Student profile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 1, email: 'student@example.org', first_name: 'Hiro', last_name: 'Bianchi',
      current_role_name: 'student', school_name: 'Test High', year_lvl: '10',
      pg_firstname: 'Pat', pg_lastname: 'Bianchi', pg_email: 'guardian@example.org',
      guardian_reminder: { last_sent_at: null, next_due_at: null, can_send: false, unavailable_reason: 'Invitations are not configured.' },
    }
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      if (input.includes('profile-options')) return new Response(JSON.stringify({
        countries: [{ id: 1, country_name: 'Australia' }],
        regions: [{ id: 2, country_id: 1, state_name: 'NSW' }],
        interests: [{ id: 3, interest_desc: 'Biology' }], selected_interest_ids: [],
      }))
      if (input.includes('group-members')) return new Response(JSON.stringify([
        { id: 1, membership_role: 'student', student_details: { first_name: 'Hiro', last_name: 'Bianchi', year_level: '10', school: 'Test High', supervisor: 'Grace Green' } },
        { id: 2, membership_role: 'mentor', student_details: null },
      ]))
      return new Response(JSON.stringify({ results: [{ id: 10, group_name: 'Test Team' }] }))
    }))
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('shows initials, student name and expanded team columns without status', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.get('.profile-avatar-initials').text()).toBe('HB')
    expect(wrapper.get('.team-table').text()).toContain('Grace Green')
    expect(wrapper.findAll('.team-table th').map(cell => cell.text())).toEqual(['First name', 'Last name', 'Year level', 'School', 'Supervisor'])
    expect(wrapper.findAll('.team-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('Name:')
    wrapper.unmount()
  })

  it('loads edit choices for geography and interests', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('.profile-edit-button').trigger('click')
    await flushPromises()
    const form = wrapper.get('.student-edit-form')
    expect(form.text()).toContain('Australia')
    expect(form.text()).toContain('Biology')
    expect(form.findAll('input[type="checkbox"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('locks a student their supervisor registered or edited, naming the supervisor', async () => {
    Object.assign(useAuthStore().user!, {
      supervisor_id: 9, details_locked: true, supervisor_name: 'Grace Green', supervisor_email: 'grace@school.edu',
    })
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('.profile-edit-button').exists()).toBe(false)
    expect(wrapper.find('[data-test="details-lock"]').attributes('data-tooltip')).toBe(
      'Your supervisor, Grace Green (grace@school.edu), manages these details. Contact them to make changes.'
    )
    // Guardian details stay the student's to change.
    expect(wrapper.find('[data-test="guardian-edit"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('leaves a student who registered themselves free to edit, supervisor or not', async () => {
    Object.assign(useAuthStore().user!, { supervisor_id: 9, details_locked: false })
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('.profile-edit-button').exists()).toBe(true)
    expect(wrapper.find('[data-test="details-lock"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('explains why sending is unavailable and does not invent reminder dates', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe('Not received, Invitations are not configured.')
    expect(wrapper.find('[data-test="guardian-send"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="guardian-reminders"]').text()).toBe('Not emailed yet.')
    wrapper.unmount()
  })

  it('sends the consent email from the link, then says when it can be sent again', async () => {
    const auth = useAuthStore()
    auth.user!.guardian_reminder = { last_sent_at: null, next_due_at: null, can_send: true, unavailable_reason: '' }
    const student = { ...auth.user! }
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await wrapper.find('[data-test="guardian-send"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/users/me/guardian-invitation/'))).toBe(true)

    // The profile as the server returns it after sending, two and a half minutes on.
    auth.user = {
      ...student,
      guardian_reminder: {
        last_sent_at: new Date(Date.now() - 2.5 * 60 * 1000).toISOString(), next_due_at: null, can_send: false,
        unavailable_reason: 'An invitation was sent recently. Please wait 10 minutes before resending.',
      },
    }
    await flushPromises()
    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe(
      'Not received, emailed guardian@example.org, you can send it again in 8 minutes'
    )
    wrapper.unmount()
  })

  it('shows what went wrong with a send at the bottom of Guardian Details', async () => {
    const auth = useAuthStore()
    auth.user!.guardian_reminder = { last_sent_at: null, next_due_at: null, can_send: true, unavailable_reason: '' }
    const message = "The mail server didn't accept the email. Try again shortly."
    const fallback = vi.mocked(fetch).getMockImplementation()!
    vi.mocked(fetch).mockImplementation(async (input, init) =>
      String(input).includes('guardian-invitation')
        // As the server's error handler sends it.
        ? new Response(JSON.stringify({ error: message, code: 'invalid' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
        : fallback(input, init)
    )
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await wrapper.find('[data-test="guardian-send"]').trigger('click')
    await flushPromises()

    const section = wrapper.find('[data-test="guardian-details"]')
    const notice = section.find('[data-test="guardian-notice"]')
    expect(notice.text()).toBe(message)
    expect(notice.classes()).toContain('guardian-notice--error')
    // The last thing in the section, not the top of the page.
    expect(section.element.lastElementChild).toBe(notice.element)
    expect(wrapper.text().indexOf(message)).toBe(wrapper.text().lastIndexOf(message))
    wrapper.unmount()
  })

  it('folds the reminders into one line under Permission', async () => {
    const auth = useAuthStore()
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
    auth.user!.guardian_reminder = {
      last_sent_at: '2026-09-14T03:00:00Z', next_due_at: tomorrow, can_send: true, unavailable_reason: '',
    }
    const wrapper = mount(ProfilePage)
    await flushPromises()

    expect(wrapper.find('[data-test="guardian-reminders"]').text()).toBe(
      `Last emailed ${formatDayMonthTime('2026-09-14T03:00:00Z')}. They'll be emailed again tomorrow.`
    )
    expect(wrapper.text()).not.toContain('Last reminder email sent')
    wrapper.unmount()
  })
})

describe('Supervisor profile: every group they are in (SP1)', () => {
  // The supervisor's own groups (?mine=true), as the server sends them.
  let myGroups: Response | Promise<Response>
  const fetchMock = vi.fn()
  // The group list the store loads (the student Team members request, made on
  // every profile, asks for page_size=1 and is left as it was).
  const groupsRequests = () =>
    fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('page_size=100&mine=true'))
  const page = (...groups: [number, string][]) =>
    new Response(JSON.stringify({ results: groups.map(([id, group_name]) => ({ id, group_name })), next: null }))

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 7, email: 'sam@example.org', first_name: 'Sam', last_name: 'Lee',
      current_role_name: 'supervisor', supervisor_school_name: 'Cardinal College', supervised_students: [],
    } as never
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    // Group pages open to supervisors, so each group is a link (following one
    // through the app's router: ProfilePageGroupLinks.spec.ts).
    setSupervisorPages({ shown: true })
    myGroups = page()
    fetchMock.mockReset()
    fetchMock.mockImplementation(async (input: string) => {
      if (input.includes('mine=true') && input.includes('page_size=100')) return myGroups
      // The student Team members request, which has nothing for a supervisor.
      return new Response(JSON.stringify({ results: [] }))
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  const mountProfile = async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/profile', name: 'profile', component: { template: '<div />' } },
        { path: '/groups/:id', name: 'group-detail', component: { template: '<div />' } },
      ],
    })
    await router.push('/profile')
    const wrapper = mount(ProfilePage, { global: { plugins: [router] } })
    await flushPromises()
    return wrapper
  }
  const section = (wrapper: Awaited<ReturnType<typeof mountProfile>>) => wrapper.find('[data-test="supervisor-groups"]')
  const links = (wrapper: Awaited<ReturnType<typeof mountProfile>>) =>
    section(wrapper).findAll('a').map((link) => [link.text(), link.attributes('href')])

  it('lists every group, each linking to its own group page, in natural order', async () => {
    myGroups = page([10, 'BTF10'], [5, 'BTF5'], [9, 'BTF9'])
    const wrapper = await mountProfile()

    expect(links(wrapper)).toEqual([['BTF5', '/groups/5'], ['BTF9', '/groups/9'], ['BTF10', '/groups/10']])
    expect(groupsRequests()).toHaveLength(1)
    wrapper.unmount()
  })

  it('shows a supervisor with one group exactly that group', async () => {
    myGroups = page([3, 'BTF3'])
    const wrapper = await mountProfile()

    expect(links(wrapper)).toEqual([['BTF3', '/groups/3']])
    wrapper.unmount()
  })

  it('says so when they are in no groups', async () => {
    const wrapper = await mountProfile()

    expect(section(wrapper).text()).toContain('You are not in any groups yet.')
    expect(section(wrapper).find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows loading until the groups arrive', async () => {
    let answer!: (response: Response) => void
    myGroups = new Promise((resolve) => { answer = resolve })
    const wrapper = await mountProfile()
    expect(section(wrapper).text()).toContain('Loading your groups')
    expect(section(wrapper).text()).not.toContain('not in any groups')

    answer(page([4, 'BTF4']))
    await flushPromises()
    expect(links(wrapper)).toEqual([['BTF4', '/groups/4']])
    wrapper.unmount()
  })

  it('says the groups could not be loaded, rather than that there are none', async () => {
    myGroups = new Response(JSON.stringify({ error: 'Server error', code: 'x', request_id: 'r' }), { status: 500 })
    const wrapper = await mountProfile()

    expect(section(wrapper).text()).toContain('Your groups could not be loaded.')
    expect(section(wrapper).text()).not.toContain('not in any groups')
    expect(section(wrapper).find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  it('reuses groups already loaded this session', async () => {
    const groups = useGroupsStore()
    groups.groups = [
      { id: '12', name: 'BTF12', memberCount: 4, createdAt: '' },
      { id: '2', name: 'BTF2', memberCount: 3, createdAt: '' },
    ]
    groups.loaded = true
    const wrapper = await mountProfile()

    expect(links(wrapper)).toEqual([['BTF2', '/groups/2'], ['BTF12', '/groups/12']])
    expect(groupsRequests()).toEqual([])
    wrapper.unmount()
  })

  it('loads them once the profile turns out to be a supervisor', async () => {
    const auth = useAuthStore()
    const supervisor = auth.user
    auth.user = null
    myGroups = page([6, 'BTF6'])
    const wrapper = await mountProfile()
    expect(groupsRequests()).toEqual([])

    auth.user = supervisor
    await flushPromises()
    expect(links(wrapper)).toEqual([['BTF6', '/groups/6']])
    wrapper.unmount()
  })

  it('gives a supervisor no student Team members section', async () => {
    myGroups = page([5, 'BTF5'])
    const wrapper = await mountProfile()

    expect(wrapper.text()).not.toContain('Team members')
    expect(wrapper.find('.team-table').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('Groups on other profiles', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it.each(['student', 'mentor'])('a %s gets no Groups section and no group list request', async (role) => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = { id: 8, email: 'x@example.org', first_name: 'Ana', last_name: 'Ruiz', current_role_name: role } as never
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    const fetchMock = vi.fn<(input: string) => Promise<Response>>(async () => new Response(JSON.stringify({ results: [] })))
    vi.stubGlobal('fetch', fetchMock)

    const wrapper = mount(ProfilePage)
    await flushPromises()

    expect(wrapper.find('[data-test="supervisor-groups"]').exists()).toBe(false)
    expect(fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('page_size=100'))).toEqual([])
    wrapper.unmount()
  })
})
