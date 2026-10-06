import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminPeoplePage from '@/views/admin/AdminPeoplePage.vue'
import AdminStudentImportSheet from '@/components/admin/users/AdminStudentImportSheet.vue'
import AdminMentorImportSheet from '@/components/admin/mentors/AdminMentorImportSheet.vue'

const country = { id: 1, countryName: 'Australia' }
const state = { id: 1, stateName: 'NSW', countryName: 'Australia' }

const user = {
  id: 1,
  firstName: 'Ada',
  lastName: 'Lovelace',
  email: 'ada@example.com',
  role: 'student',
  country,
  state,
  groupId: null,
  groupName: 'Group A',
  schoolName: 'State High',
  mentorBackground: null,
  mentorInstitution: null,
  mentorReason: null,
  mentorMaxGroupCount: null,
  yearLevel: 10,
  joinPermissionReceived: false,
  interests: ['Science'],
  isAdmin: false,
  isActive: true,
  hasLoggedIn: true,
  lastLogin: '2026-02-01T00:00:00Z',
  accountStatus: 'active',
  invitedAt: '2026-01-01T00:00:00Z',
  activatedAt: '2026-01-02T00:00:00Z',
  supervisorName: null,
  supervisorEmail: null,
  supervisees: []
}

const fetchMock = vi.fn().mockImplementation((url: string) => {
  let payload: Record<string, unknown>
  if (url.includes('/user/countries/')) {
    payload = { msg: 'ok', data: [country] }
  } else if (url.includes('/user/states/')) {
    payload = { msg: 'ok', data: [state] }
  } else if (url.includes('/user/')) {
    payload = { msg: 'ok', data: { items: [user], total: 1, page: 1, limit: 25, hasMore: false } }
  } else if (
    url.includes('/mentor-match/matched-groups/') ||
    url.includes('/mentor-match/mentors/') ||
    url.includes('/mentor/')
  ) {
    payload = { msg: 'ok', data: [] }
  } else {
    payload = {}
  }
  return Promise.resolve(
    new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } })
  )
})

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

const tabButtons = () => wrapper!.findAll('[role="tab"]')
const tabAddButton = () => wrapper!.find('.people-toolbar .btn-primary')
const dialogs = () => Array.from(document.body.querySelectorAll('[role="dialog"]'))

describe('AdminPeoplePage', () => {
  it('renders the four tab labels', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    const tabs = tabButtons().map((b) => b.text())
    expect(tabs).toEqual(['Users', 'Students', 'Mentors', 'Supervisors'])
    expect(wrapper.text()).toContain('People')
  })

  it('starts on the Users tab and loads the user list', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    const tabs = tabButtons()
    const active = tabs.find((b) => b.attributes('aria-selected') === 'true')
    expect(active?.text()).toBe('Users')

    expect(wrapper.find('#role-filter').exists()).toBe(true)
    expect(wrapper.text()).toContain('Ada Lovelace')
    expect(wrapper.text()).toContain('Add User')
  })

  it('switches to the Students tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Students')!.trigger('click')
    await flushPromises()

    const active = tabButtons().find((b) => b.attributes('aria-selected') === 'true')
    expect(active?.text()).toBe('Students')
    expect(wrapper.text()).toContain('Add Student')
    expect(wrapper.find('#role-filter').exists()).toBe(false)
    expect(wrapper.text()).toContain('Ada Lovelace')
  })

  it('switches to the Supervisors tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Supervisors')!.trigger('click')
    await flushPromises()

    const active = tabButtons().find((b) => b.attributes('aria-selected') === 'true')
    expect(active?.text()).toBe('Supervisors')
    expect(wrapper.text()).toContain('Add Supervisor')
    expect(wrapper.find('#role-filter').exists()).toBe(false)
    expect(wrapper.text()).toContain('Ada Lovelace')
  })

  it('switches to the Mentors tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Mentors')!.trigger('click')
    await flushPromises()

    const active = tabButtons().find((b) => b.attributes('aria-selected') === 'true')
    expect(active?.text()).toBe('Mentors')
    expect(wrapper.find('#inactive-days-input').exists()).toBe(true)
    expect(wrapper.text()).toContain('0 mentors registered')
    expect(wrapper.text()).toContain('No mentors registered yet.')
    expect(wrapper.find('#role-filter').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Add Mentor')
  })

  it('opens the create form from the tabs-line Add button on the Users tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    const add = tabAddButton()
    expect(add.exists()).toBe(true)
    expect(add.text()).toContain('Add User')
    await add.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Add user'))
    expect(dialog).toBeDefined()
    expect(dialog!.querySelector('#f-email')).not.toBeNull()
  })

  it('switches the tabs-line Add button label when the active tab changes', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Students')!.trigger('click')
    await flushPromises()
    expect(tabAddButton().text()).toContain('Add Student')

    await tabButtons().find((b) => b.text() === 'Supervisors')!.trigger('click')
    await flushPromises()
    expect(tabAddButton().text()).toContain('Add Supervisor')

    await tabButtons().find((b) => b.text() === 'Users')!.trigger('click')
    await flushPromises()
    expect(tabAddButton().text()).toContain('Add User')
  })

  it('does not render an Add button on the Mentors tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Mentors')!.trigger('click')
    await flushPromises()
    expect(tabAddButton().exists()).toBe(false)
  })

  it('opens the student CSV import sheet from the Students tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Students')!.trigger('click')
    await flushPromises()

    const importButton = wrapper
      .find('.people-toolbar')
      .findAll('button')
      .find((b) => b.text().trim() === 'Import Students CSV')
    expect(importButton).toBeDefined()
    await importButton!.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(AdminStudentImportSheet).props('modelValue')).toBe(true)
  })

  it('opens the mentor CSV import sheet from the Mentors tab', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    await tabButtons().find((b) => b.text() === 'Mentors')!.trigger('click')
    await flushPromises()

    const importButton = wrapper
      .find('.people-toolbar')
      .findAll('button')
      .find((b) => b.text().trim() === 'Import Mentors CSV')
    expect(importButton).toBeDefined()
    await importButton!.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(AdminMentorImportSheet).props('modelValue')).toBe(true)
  })

  it('hides CSV import buttons on the Users and Supervisors tabs', async () => {
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminPeoplePage)
    await flushPromises()

    const importLabels = () =>
      wrapper!
        .find('.people-toolbar')
        .findAll('button')
        .map((b) => b.text().trim())
        .filter((t) => t.includes('CSV'))
    expect(importLabels()).toEqual([])

    await tabButtons().find((b) => b.text() === 'Supervisors')!.trigger('click')
    await flushPromises()
    expect(importLabels()).toEqual([])
  })
})