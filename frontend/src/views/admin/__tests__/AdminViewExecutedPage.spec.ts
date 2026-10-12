import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory } from 'vue-router'
import AdminViewExecutedPage from '@/views/admin/AdminViewExecutedPage.vue'

const country = { id: 1, countryName: 'Australia' }
const state = { id: 1, stateName: 'NSW', countryName: 'Australia' }

const baseUser = {
  id: 1,
  firstName: 'Ada',
  lastName: 'Lovelace',
  email: 'ada@example.com',
  role: 'student',
  country,
  state,
  groupId: null,
  groupName: null,
  schoolName: 'State High',
  mentorBackground: null,
  mentorInstitution: null,
  mentorReason: null,
  mentorMaxGroupCount: null,
  yearLevel: 10,
  joinPermissionReceived: false,
  interests: [],
  isAdmin: false,
  isActive: true,
  hasLoggedIn: true,
  lastLogin: null,
  accountStatus: 'active',
  invitedAt: null,
  activatedAt: null,
  supervisorName: null,
  supervisorEmail: null,
  supervisees: []
}

const buildUser = (overrides: Record<string, unknown> = {}) => ({ ...baseUser, ...overrides })

const baseView = {
  id: 5,
  name: 'Test Student View',
  description: '',
  isDefault: false,
  targetRoles: ['student'],
  accountStatus: 'all',
  engagementStatus: 'all',
  advancedConditions: [],
  visibleColumns: ['name', 'email', 'role']
}

const buildView = (overrides: Record<string, unknown> = {}) => ({ ...baseView, ...overrides })

const envelope = (data: unknown) =>
  new Response(JSON.stringify({ msg: 'ok', data }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' }
  })

const fetchMockFor = (users: unknown[], view: Record<string, unknown>) =>
  vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const u = String(url)
    if (u.includes('/services/csrf/')) {
      return Promise.resolve(new Response(JSON.stringify({ csrfToken: 'csrf-test' }), { status: 200 }))
    }
    if (u.includes('/export-csv/')) {
      return Promise.resolve(new Response('name,email\nAda,ada@example.com', { status: 200 }))
    }
    if (u.includes('/run/')) {
      return Promise.resolve(
        envelope({ items: users, total: users.length, page: 1, limit: 25, hasMore: false, view })
      )
    }
    if (u.includes('/user/countries/')) return Promise.resolve(envelope([country]))
    if (u.includes('/user/states/')) return Promise.resolve(envelope([state]))
    if (u.includes('/match/confirm/')) return Promise.resolve(envelope({ assigned_count: 1 }))
    if (u.includes('/user/bulk-status/')) {
      return Promise.resolve(envelope({ updatedIds: [1], unchangedIds: [], notFoundIds: [] }))
    }
    if (u.includes('/user/bulk-delete/')) {
      return Promise.resolve(
        envelope({ deletedIds: [1], failedIds: [], notFoundIds: [], skippedSelf: false, skippedAdmins: 0 })
      )
    }
    if (u.includes('/status/')) return Promise.resolve(envelope(buildUser()))
    if (u.includes('/guardian-consent-request/')) {
      // The student as the server returns them after the request goes out.
      return Promise.resolve(
        envelope(buildUser({ guardianEmail: 'pat@example.com', consentRequestSentAt: '2026-10-08T03:00:00Z' }))
      )
    }
    if (u.match(/\/user\/\d+\/$/) && String(init?.method).toUpperCase() === 'DELETE') {
      return Promise.resolve(envelope(null))
    }
    if (u.includes('/user/')) {
      // Supervisor lookup for the edit form sheet (fetchAdminUsers({role:'supervisor'})).
      return Promise.resolve(envelope({ items: [], total: 0, page: 1, limit: 200, hasMore: false }))
    }
    return Promise.resolve(envelope({}))
  })

const dialogs = () => Array.from(document.body.querySelectorAll('[role="dialog"]'))

const stub = { template: '<div />' }
const ROUTES = [
  { path: '/admin/views/:id(\\d+)', name: 'admin-view-detail', component: stub },
  { path: '/admin/views', name: 'admin-views', component: stub }
]

const queryDrawerStub = {
  name: 'AdminViewQueryDrawerStub',
  props: ['modelValue', 'view'],
  emits: ['update:modelValue', 'saved'],
  template:
    '<div v-if="modelValue" class="query-drawer-stub">' +
    '<span>{{ view && view.name }}</span>' +
    '<button type="button" @click="$emit(\'saved\', view)">stub-save</button>' +
    '</div>'
}

const mountPage = async (users: unknown[], view: Record<string, unknown>, path = '/admin/views/5') => {
  const fetchMock = fetchMockFor(users, view)
  vi.stubGlobal('fetch', fetchMock)
  const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
  await router.push(path)
  await router.isReady()
  const wrapper = mount(AdminViewExecutedPage, {
    global: {
      plugins: [router],
      stubs: { AdminViewQueryDrawer: queryDrawerStub }
    }
  })
  await flushPromises()
  return { wrapper, fetchMock }
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('AdminViewExecutedPage', () => {
  it('renders only the columns specified by the view', async () => {
    const view = buildView({ visibleColumns: ['name', 'email', 'role'] })
    const result = await mountPage([buildUser()], view)
    wrapper = result.wrapper

    const headers = wrapper.findAll('.data-table-head').map((h) => h.text().replace(/[^\w ]/g, '').trim())
    // Edit and Activate/Deactivate each have a column, both headed Actions for screen readers.
    expect(headers).toEqual(['Full Name', 'Email', 'Role', 'Actions', 'Actions'])
  })

  it('opens the user detail sheet from a name click, then the edit form from within it', async () => {
    const result = await mountPage([buildUser()], buildView())
    wrapper = result.wrapper

    const nameButton = wrapper.find('.admin-view-table__name-btn')
    expect(nameButton.exists()).toBe(true)
    await nameButton.trigger('click')
    await flushPromises()

    const detail = dialogs().find((d) => d.textContent!.includes('Account'))
    expect(detail).toBeDefined()
    expect(detail!.textContent).toContain('ada@example.com')

    const editButton = Array.from(detail!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Edit'
    )
    expect(editButton).toBeDefined()
    await editButton!.click()
    await flushPromises()

    const editor = dialogs().find((d) => d.textContent!.includes('Edit user'))
    expect(editor).toBeDefined()
    expect((editor!.querySelector('#f-first') as HTMLInputElement).value).toBe('Ada')
  })

  it('shows a sent consent request on the open sheet and reloads the results', async () => {
    const result = await mountPage([buildUser({ guardianEmail: 'pat@example.com' })], buildView())
    wrapper = result.wrapper
    await wrapper.find('.admin-view-table__name-btn').trigger('click')
    await flushPromises()
    const sheet = () => dialogs().find((d) => d.textContent!.includes('Account'))!
    expect(sheet().querySelector('[data-test="admin-consent-request-sent"]')).toBeNull()
    const runsBefore = result.fetchMock.mock.calls.filter(([url]) => String(url).includes('/run/')).length

    ;(sheet().querySelector('[data-test="admin-send-consent-request"]') as HTMLButtonElement).click()
    await flushPromises()

    expect(sheet().querySelector('[data-test="admin-consent-request-sent"]')).not.toBeNull()
    expect(result.fetchMock.mock.calls.filter(([url]) => String(url).includes('/run/')).length).toBeGreaterThan(runsBefore)
  })

  it('confirms then deactivates a user via the row action', async () => {
    const result = await mountPage([buildUser()], buildView())
    wrapper = result.wrapper

    const deactivateButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Deactivate')
    expect(deactivateButton).toBeDefined()
    await deactivateButton!.trigger('click')
    await flushPromises()

    const confirm = dialogs().find((d) => d.textContent!.includes('Deactivate user'))
    expect(confirm).toBeDefined()
    expect(confirm!.textContent).toContain('Ada Lovelace')

    const confirmButton = Array.from(confirm!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Deactivate'
    )
    await confirmButton!.click()
    await flushPromises()

    const patchCall = result.fetchMock.mock.calls.find(
      (call) => String(call[0]).includes('/status/') && String(call[1]?.method).toUpperCase() === 'PATCH'
    )
    expect(patchCall).toBeDefined()
    expect(JSON.parse(String(patchCall![1]!.body))).toEqual({ isActive: false })
  })

  it('selects rows, shows the bulk bar, and bulk-deactivates through it', async () => {
    const result = await mountPage(
      [buildUser(), buildUser({ id: 2, firstName: 'Grace', lastName: 'Hopper' })],
      buildView()
    )
    wrapper = result.wrapper

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await checkboxes[2].setValue(true)
    await flushPromises()

    expect(wrapper.find('[role="toolbar"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('2 users selected')

    const deactivateButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Deactivate')
    await deactivateButton!.trigger('click')
    await flushPromises()

    const confirm = dialogs().find((d) => d.textContent!.includes('Deactivate 2 users?'))
    expect(confirm).toBeDefined()
    const confirmButton = Array.from(confirm!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Deactivate'
    )
    await confirmButton!.click()
    await flushPromises()

    const bulkCall = result.fetchMock.mock.calls.find((call) => String(call[0]).includes('/user/bulk-status/'))
    expect(bulkCall).toBeDefined()
    expect(JSON.parse(String(bulkCall![1]!.body))).toEqual({ isActive: false, userIds: [1, 2] })
  })

  it('disables Assign to Group for a mixed selection and enables it for an all-student selection', async () => {
    const result = await mountPage(
      [buildUser(), buildUser({ id: 2, firstName: 'Sam', lastName: 'Mentor', role: 'mentor' })],
      buildView({ visibleColumns: ['name', 'email', 'role'] })
    )
    wrapper = result.wrapper

    const checkboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await checkboxes[1].setValue(true)
    await checkboxes[2].setValue(true)
    await flushPromises()

    let assignButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Assign to group')
    expect(assignButton).toBeDefined()
    expect(assignButton!.attributes('disabled')).toBeDefined()
    expect(assignButton!.element.closest('span')?.getAttribute('title')).toContain(
      'only available when all selected users are students'
    )

    await checkboxes[2].setValue(false)
    await flushPromises()

    assignButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Assign to group')
    expect(assignButton!.attributes('disabled')).toBeUndefined()
  })

  it('disables Edit Query Criteria for a System Default view and enables it for a Custom View', async () => {
    const defaultResult = await mountPage([buildUser()], buildView({ isDefault: true }))
    wrapper = defaultResult.wrapper

    let editCriteriaButton = wrapper.findAll('button').find((b) => b.text().includes('Edit Query Criteria'))
    expect(editCriteriaButton).toBeDefined()
    expect(editCriteriaButton!.attributes('disabled')).toBeDefined()
    expect(editCriteriaButton!.element.closest('span')?.getAttribute('title')).toContain(
      'System default views cannot be edited'
    )

    wrapper.unmount()
    const customResult = await mountPage([buildUser()], buildView({ isDefault: false }))
    wrapper = customResult.wrapper

    editCriteriaButton = wrapper.findAll('button').find((b) => b.text().includes('Edit Query Criteria'))
    expect(editCriteriaButton!.attributes('disabled')).toBeUndefined()
  })

  it('reloads from page 1 when the query drawer reports a saved view', async () => {
    const result = await mountPage([buildUser()], buildView())
    wrapper = result.wrapper

    const editCriteriaButton = wrapper.findAll('button').find((b) => b.text().includes('Edit Query Criteria'))
    await editCriteriaButton!.trigger('click')
    await flushPromises()

    expect(wrapper.find('.query-drawer-stub').exists()).toBe(true)

    const runCallsBefore = result.fetchMock.mock.calls.filter((call) => String(call[0]).includes('/run/')).length

    const saveButton = wrapper.find('.query-drawer-stub button')
    await saveButton.trigger('click')
    await flushPromises()

    const runCalls = result.fetchMock.mock.calls.filter((call) => String(call[0]).includes('/run/'))
    expect(runCalls.length).toBe(runCallsBefore + 1)
    expect(String(runCalls.at(-1)?.[0])).toContain('page=1')
  })

  it('exports CSV including the currently applied search term', async () => {
    vi.useFakeTimers()
    window.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    window.URL.revokeObjectURL = vi.fn()
    // jsdom doesn't implement anchor-download navigation; suppress the resulting
    // "Not implemented: navigation" console noise from exportCsv()'s temp <a> click.
    const realCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const el = realCreateElement(tag)
      if (tag === 'a') el.click = vi.fn()
      return el
    })
    const result = await mountPage([buildUser()], buildView())
    wrapper = result.wrapper

    await wrapper.find<HTMLInputElement>('input[placeholder="Name or email"]').setValue('Ada')
    await vi.advanceTimersByTimeAsync(350)
    await flushPromises()

    const exportButton = wrapper.findAll('button').find((b) => b.text().includes('Export CSV'))
    expect(exportButton).toBeDefined()
    await exportButton!.trigger('click')
    await flushPromises()

    const exportCall = result.fetchMock.mock.calls.find((call) => String(call[0]).includes('/export-csv/'))
    expect(exportCall).toBeDefined()
    expect(String(exportCall![0])).toContain('search=Ada')
    expect(exportCall![1]).toMatchObject({ credentials: 'include' })

    vi.useRealTimers()
  })
})
