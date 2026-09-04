import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminUsersView from '@/views/admin/AdminUsersView.vue'
import AdminStudentImportSheet from '@/components/admin/users/AdminStudentImportSheet.vue'

const country = { id: 1, countryName: 'Australia' }
const state = { id: 1, stateName: 'NSW', countryName: 'Australia' }

const group = {
  id: 1,
  name: 'Team A',
  members: [],
  mentor: null,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z'
}

const baseUser = {
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

const buildUser = (overrides: Record<string, unknown> = {}) => ({ ...baseUser, ...overrides })

const fetchMockFor = (users: unknown[]) =>
  vi.fn().mockImplementation((url: string) => {
    let payload: Record<string, unknown>
    if (url.includes('/services/csrf/')) {
      payload = { csrfToken: 'csrf-test' }
    } else if (url.includes('/user/countries/')) {
      payload = { msg: 'ok', data: [country] }
    } else if (url.includes('/user/states/')) {
      payload = { msg: 'ok', data: [state] }
    } else if (url.includes('/match/confirm/')) {
      payload = { msg: 'ok', data: { assigned_count: 1 } }
    } else if (url.includes('/group/')) {
      payload = {
        msg: 'ok',
        data: { items: [group], total: 1, page: 1, limit: 100, hasMore: false }
      }
    } else if (url.includes('/user/')) {
      payload = { msg: 'ok', data: { items: users, total: users.length, page: 1, limit: 25, hasMore: false } }
    } else {
      payload = {}
    }
    return Promise.resolve(
      new Response(JSON.stringify(payload), { status: 200, headers: { 'Content-Type': 'application/json' } })
    )
  })

const listCall = (fetchMock: ReturnType<typeof vi.fn>) =>
  [...fetchMock.mock.calls]
    .reverse()
    .find((call) => {
      const url = String(call[0])
      // The supervisor picker (limit=200) fires on every non-supervisor mount;
      // target the main list query only.
      return (
        url.includes('/user/') &&
        !url.includes('/user/countries/') &&
        !url.includes('/user/states/') &&
        !url.includes('limit=200')
      )
    })

const dialogs = () => Array.from(document.body.querySelectorAll('[role="dialog"]'))

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe('AdminUsersView', () => {
  it('loads and renders user rows', async () => {
    vi.stubGlobal(
      'fetch',
      fetchMockFor([
        buildUser(),
        buildUser({ id: 2, firstName: 'Grace', lastName: 'Hopper', role: 'supervisor' })
      ])
    )
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    expect(wrapper.text()).toContain('Ada Lovelace')
    expect(wrapper.text()).toContain('Grace Hopper')
    expect(wrapper.text()).toContain('Add User')
  })

  it('requests the supervisors role filter and hides the role filter control', async () => {
    const fetchMock = fetchMockFor([buildUser({ id: 9, role: 'supervisor' })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Supervisors', noun: 'supervisor', roleFilter: 'supervisor' }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Add Supervisor')
    expect(String(listCall(fetchMock)?.[0])).toContain('role=supervisor')
    expect(wrapper.find('#role-filter').exists()).toBe(false)
    expect(wrapper.find('#country-filter').exists()).toBe(false)
  })

  it('locks the role for students while keeping the full filter card', async () => {
    const fetchMock = fetchMockFor([buildUser()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Add Student')
    expect(String(listCall(fetchMock)?.[0])).toContain('role=student')
    expect(wrapper.find('#role-filter').exists()).toBe(false)
    expect(wrapper.find('#country-filter').exists()).toBe(true)
    expect(wrapper.find('#status-filter').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('Role')
  })

  it('shows the bulk bar once a row is selected', async () => {
    vi.stubGlobal('fetch', fetchMockFor([buildUser()]))
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    const checkbox = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    expect(checkbox.exists()).toBe(true)
    await checkbox.setValue(true)
    await flushPromises()

    expect(wrapper.find('[role="toolbar"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('1 user selected')
  })

  it('does not offer bulk delete to supervisors', async () => {
    vi.stubGlobal('fetch', fetchMockFor([buildUser({ id: 9, role: 'supervisor' })]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Supervisors', noun: 'supervisor', roleFilter: 'supervisor' }
    })
    await flushPromises()

    const header = wrapper.find<HTMLInputElement>('input[type="checkbox"]')
    await header.setValue(true)
    await flushPromises()

    const toolbar = wrapper.find('[role="toolbar"]')
    expect(toolbar.exists()).toBe(true)
    expect(toolbar.text()).not.toContain('Delete')
  })

  it('opens the create form when "Add User" is clicked', async () => {
    vi.stubGlobal('fetch', fetchMockFor([]))
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    const button = wrapper.findAll('button').find((b) => b.text().trim() === 'Add User')
    expect(button).toBeDefined()
    await button!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Add user'))
    expect(dialog).toBeDefined()
    expect(dialog!.querySelector('#f-email')).not.toBeNull()
  })

  it('offers a delete action from the editor for regular users', async () => {
    vi.stubGlobal('fetch', fetchMockFor([buildUser()]))
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    const editButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Edit')
    await editButton!.trigger('click')
    await flushPromises()

    const editor = dialogs().find((d) => d.textContent!.includes('Edit user'))
    expect(editor).toBeDefined()
    const deleteButton = Array.from(editor!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Delete'
    )
    expect(deleteButton).toBeDefined()
    await deleteButton!.click()
    await flushPromises()

    const confirm = dialogs().find((d) => d.textContent!.includes('Delete user'))
    expect(confirm).toBeDefined()
    expect(confirm!.textContent).toContain('permanently removes the account')
  })

  it('hides the editor delete action for supervisors', async () => {
    vi.stubGlobal('fetch', fetchMockFor([buildUser({ id: 9, role: 'supervisor' })]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Supervisors', noun: 'supervisor', roleFilter: 'supervisor' }
    })
    await flushPromises()

    const editButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Edit')
    await editButton!.trigger('click')
    await flushPromises()

    const editor = dialogs().find((d) => d.textContent!.includes('Edit supervisor'))
    expect(editor).toBeDefined()
    const deleteButton = Array.from(editor!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Delete'
    )
    expect(deleteButton).toBeUndefined()
  })

  it('confirms before deactivating a user via the row action', async () => {
    const fetchMock = fetchMockFor([buildUser()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    const deactivateButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Deactivate')
    expect(deactivateButton).toBeDefined()
    await deactivateButton!.trigger('click')
    await flushPromises()

    const confirm = dialogs().find((d) => d.textContent!.includes('Deactivate user'))
    expect(confirm).toBeDefined()
    expect(confirm!.textContent).toContain('Ada Lovelace')
    expect(confirm!.textContent).toContain('no longer be able to sign in')

    const patchCalls = () =>
      fetchMock.mock.calls.filter((call) => String(call[1]?.method).toUpperCase() === 'PATCH')

    expect(patchCalls()).toHaveLength(0)

    const confirmButton = Array.from(confirm!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Deactivate'
    )
    await confirmButton!.click()
    await flushPromises()

    expect(patchCalls()).toHaveLength(1)
    const call = patchCalls()[0]
    expect(String(call![0])).toContain('/user/1/status/')
    expect(JSON.parse(String(call![1]!.body))).toEqual({ isActive: false })
  })

  it('reactivates an inactive user immediately without confirmation', async () => {
    const fetchMock = fetchMockFor([buildUser({ isActive: false })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    const activateButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Activate')
    expect(activateButton).toBeDefined()
    await activateButton!.trigger('click')
    await flushPromises()

    const confirm = dialogs().some((d) => d.textContent!.includes('Deactivate user'))
    expect(confirm).toBe(false)

    const call = fetchMock.mock.calls.find((c) => String(c[1]?.method).toUpperCase() === 'PATCH')
    expect(call).toBeDefined()
    expect(String(call![0])).toContain('/user/1/status/')
    expect(JSON.parse(String(call![1]!.body))).toEqual({ isActive: true })
  })

  it('shows the in-group filter for students and passes it to the query', async () => {
    const fetchMock = fetchMockFor([buildUser({ groupId: null, groupName: null })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const filter = wrapper.find<HTMLSelectElement>('#in-group-filter')
    expect(filter.exists()).toBe(true)
    await filter.setValue('yes')
    await flushPromises()

    expect(String(listCall(fetchMock)?.[0])).toContain('inGroup=yes')
  })

  it('omits the in-group filter outside student mode', async () => {
    vi.stubGlobal('fetch', fetchMockFor([buildUser()]))
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    expect(wrapper.find('#in-group-filter').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('In group')
  })

  it('renders the Group column and Assign/Remove actions for students', async () => {
    vi.stubGlobal('fetch', fetchMockFor([
      buildUser({ groupId: null, groupName: null }),
      buildUser({ id: 2, firstName: 'Grace', lastName: 'Hopper', groupId: 7, groupName: 'Team B' })
    ]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Team B')
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Assign')).toBe(true)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Remove')).toBe(true)
    // Student mode omits row-level Edit/Deactivate and bulk Activate/Deactivate/Delete.
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Edit')).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Deactivate')).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Activate')).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Delete')).toBe(false)
  })

  it('shows row-level Edit/Deactivate and bulk actions for the users tab', async () => {
    vi.stubGlobal('fetch', fetchMockFor([
      buildUser({ groupId: null, groupName: null })
    ]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Users', noun: 'user' }
    })
    await flushPromises()

    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Edit')).toBe(true)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Deactivate')).toBe(true)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Assign')).toBe(false)
    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Remove')).toBe(false)
  })

  it('builds the student table with the expected columns in order', async () => {
    vi.stubGlobal('fetch', fetchMockFor([
      buildUser({
        groupId: null,
        groupName: null,
        schoolName: 'State High',
        yearLevel: 10,
        interests: ['Science', 'Maths'],
        hasLoggedIn: false,
        lastLogin: null
      })
    ]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const headers = wrapper
      .findAll('.admin-table__head')
      .map((h) => h.text().replace(/[^\w ]/g, '').trim())
    expect(headers).toEqual([
      'Student',
      'School',
      'Year',
      'Country',
      'State',
      'Group',
      'Interests',
      'Logged In',
      'Actions'
    ])

    const sortableHeaders = wrapper
      .findAll('.admin-table__sort-btn')
      .map((button) => button.text().replace(/[^\w ]/g, '').trim())
    expect(sortableHeaders).toEqual([
      'Student',
      'School',
      'Year',
      'Country',
      'State',
      'Group',
      'Logged In'
    ])
    expect(sortableHeaders).not.toContain('Interests')
    expect(sortableHeaders).not.toContain('Actions')

    // Name and email share one Student cell; no separate Email column.
    expect(wrapper.findAll('.admin-table__head').some((h) => h.text().includes('Email'))).toBe(false)
    const studentCell = wrapper.find('.admin-users__student-cell')
    expect(studentCell.exists()).toBe(true)
    expect(studentCell.text()).toContain('Ada Lovelace')
    expect(studentCell.text()).toContain('ada@example.com')

    // School / Year / Interests cells render their data in the row.
    const firstRow = wrapper.find('.admin-table__row')
    expect(firstRow.text()).toContain('State High')
    expect(firstRow.text()).toContain('10')
    expect(firstRow.text()).toContain('Science')
    expect(firstRow.text()).toContain('Maths')
    expect(firstRow.text()).toContain('No')
  })

  it('maps student sortable columns to the supported backend sort fields', async () => {
    const fetchMock = fetchMockFor([buildUser()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    expect(String(listCall(fetchMock)?.[0])).toContain('sortBy=name')
    expect(String(listCall(fetchMock)?.[0])).toContain('sortOrder=asc')

    const expectedSorts = [
      ['School', 'school'],
      ['Year', 'yearLevel'],
      ['Country', 'country'],
      ['State', 'state'],
      ['Group', 'group'],
      ['Logged In', 'hasLoggedIn']
    ] as const

    for (const [label, sortBy] of expectedSorts) {
      const button = wrapper
        .findAll('.admin-table__sort-btn')
        .find((candidate) => candidate.text().replace(/[^\w ]/g, '').trim() === label)
      expect(button, `${label} sort button`).toBeDefined()
      await button!.trigger('click')
      await flushPromises()

      const url = String(listCall(fetchMock)?.[0])
      expect(url).toContain(`sortBy=${sortBy}`)
      expect(url).toContain('sortOrder=asc')
      expect(url).toContain('role=student')
    }
  })

  it('toggles student sort direction when clicking the same sortable column twice', async () => {
    const fetchMock = fetchMockFor([buildUser()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const schoolSort = wrapper
      .findAll('.admin-table__sort-btn')
      .find((candidate) => candidate.text().replace(/[^\w ]/g, '').trim() === 'School')
    expect(schoolSort).toBeDefined()

    await schoolSort!.trigger('click')
    await flushPromises()
    let params = new URL(String(listCall(fetchMock)?.[0])).searchParams
    expect(params.get('sortBy')).toBe('school')
    expect(params.get('sortOrder')).toBe('asc')

    await schoolSort!.trigger('click')
    await flushPromises()
    params = new URL(String(listCall(fetchMock)?.[0])).searchParams
    expect(params.get('sortBy')).toBe('school')
    expect(params.get('sortOrder')).toBe('desc')
  })

  it('preserves active student search and filters when sorting', async () => {
    vi.useFakeTimers()
    const fetchMock = fetchMockFor([buildUser()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    await wrapper.find<HTMLInputElement>('#user-search').setValue('Ada')
    vi.advanceTimersByTime(350)
    await flushPromises()
    await wrapper.find<HTMLSelectElement>('#country-filter').setValue('Australia')
    await flushPromises()
    await wrapper.find<HTMLSelectElement>('#state-filter').setValue('NSW')
    await flushPromises()
    await wrapper.find<HTMLSelectElement>('#in-group-filter').setValue('yes')
    await flushPromises()
    await wrapper.find<HTMLSelectElement>('#status-filter').setValue('active')
    await flushPromises()

    const yearSort = wrapper
      .findAll('.admin-table__sort-btn')
      .find((candidate) => candidate.text().replace(/[^\w ]/g, '').trim() === 'Year')
    expect(yearSort).toBeDefined()
    await yearSort!.trigger('click')
    await flushPromises()

    const params = new URL(String(listCall(fetchMock)?.[0])).searchParams
    expect(params.get('sortBy')).toBe('yearLevel')
    expect(params.get('sortOrder')).toBe('asc')
    expect(params.get('role')).toBe('student')
    expect(params.get('search')).toBe('Ada')
    expect(params.get('country')).toBe('Australia')
    expect(params.get('state')).toBe('NSW')
    expect(params.get('inGroup')).toBe('yes')
    expect(params.get('active')).toBe('true')
  })

  it('resets student sorting to page one and clears row selection', async () => {
    const fetchMock = fetchMockFor(
      Array.from({ length: 26 }, (_, index) =>
        buildUser({
          id: index + 1,
          firstName: `Student${index + 1}`,
          email: `student${index + 1}@example.com`
        })
      )
    )
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const nextPageButton = wrapper.find('button[aria-label="Next page"]')
    expect(nextPageButton.exists()).toBe(true)
    await nextPageButton.trigger('click')
    await flushPromises()
    let params = new URL(String(listCall(fetchMock)?.[0])).searchParams
    expect(params.get('page')).toBe('2')

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await flushPromises()
    expect(wrapper.text()).toContain('1 student selected')

    const groupSort = wrapper
      .findAll('.admin-table__sort-btn')
      .find((candidate) => candidate.text().replace(/[^\w ]/g, '').trim() === 'Group')
    expect(groupSort).toBeDefined()
    await groupSort!.trigger('click')
    await flushPromises()

    params = new URL(String(listCall(fetchMock)?.[0])).searchParams
    expect(params.get('page')).toBe('1')
    expect(params.get('sortBy')).toBe('group')
    expect(params.get('sortOrder')).toBe('asc')
    expect(wrapper.text()).not.toContain('1 student selected')
  })

  it('opens the student CSV import sheet from the Students toolbar only', async () => {
    vi.stubGlobal('fetch', fetchMockFor([buildUser()]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const importButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Import Students CSV')
    expect(importButton).toBeDefined()
    await importButton!.trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(AdminStudentImportSheet).props('modelValue')).toBe(true)

    wrapper.unmount()
    wrapper = mount(AdminUsersView, { props: { title: 'Users', noun: 'user' } })
    await flushPromises()

    expect(wrapper.findAll('button').some((b) => b.text().trim() === 'Import Students CSV')).toBe(false)
    expect(wrapper.findComponent(AdminStudentImportSheet).exists()).toBe(false)
  })

  it('reloads students after a successful CSV import', async () => {
    const fetchMock = fetchMockFor([buildUser()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const initialListCalls = fetchMock.mock.calls.filter(
      (call) => String(call[0]).includes('/user/') && !String(call[0]).includes('limit=200')
    ).length

    const importButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Import Students CSV')
    await importButton!.trigger('click')
    await flushPromises()

    wrapper.findComponent(AdminStudentImportSheet).vm.$emit('imported', {
      msg: 'Bulk import complete: 1 created, 0 skipped',
      data: { created: [], skipped: [] }
    })
    await flushPromises()

    const listCalls = fetchMock.mock.calls.filter(
      (call) => String(call[0]).includes('/user/') && !String(call[0]).includes('limit=200')
    )
    expect(listCalls).toHaveLength(initialListCalls + 1)
    expect(String(listCalls.at(-1)?.[0])).toContain('role=student')
  })

  it('assigns a student to a group through the assign dialog', async () => {
    const fetchMock = fetchMockFor([buildUser({ groupId: null, groupName: null })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const assignButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Assign')
    expect(assignButton).toBeDefined()
    await assignButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Assign Student to Group'))
    expect(dialog).toBeDefined()

    const select = dialog!.querySelector<HTMLSelectElement>('#assign-group-select')
    expect(select).not.toBeNull()
    select!.value = '1' // Team A
    select!.dispatchEvent(new Event('change', { bubbles: true }))
    await flushPromises()

    const confirmButton = Array.from(dialog!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Confirm assignment'
    )
    expect(confirmButton).toBeDefined()
    await confirmButton!.click()
    await flushPromises()

    const postCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes('/match/confirm/')
    )
    expect(postCall).toBeDefined()
    expect(String(postCall![1]?.method).toUpperCase()).toBe('POST')
    expect(JSON.parse(String(postCall![1]!.body))).toEqual({
      assignments: [{ studentId: 1, groupId: 1 }]
    })
  })

  it('opens the assign dialog with the selected students from the bulk bar', async () => {
    vi.stubGlobal('fetch', fetchMockFor([
      buildUser({ groupId: null, groupName: null }),
      buildUser({ id: 2, firstName: 'Grace', lastName: 'Hopper', groupId: null, groupName: null })
    ]))
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await rowCheckboxes[2].setValue(true)
    await flushPromises()

    const assignButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Assign to group')
    expect(assignButton).toBeDefined()
    await assignButton!.trigger('click')
    await flushPromises()

    const dialog = dialogs().find((d) => d.textContent!.includes('Assign students to a group'))
    expect(dialog).toBeDefined()
    expect(dialog!.textContent).toContain('Assigning 2 students')
  })

  it('removes a grouped student after confirmation', async () => {
    const fetchMock = fetchMockFor([
      buildUser({ id: 2, firstName: 'Grace', lastName: 'Hopper', groupId: 7, groupName: 'Team B' })
    ])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mount(AdminUsersView, {
      props: { title: 'Students', noun: 'student', roleFilter: 'student' }
    })
    await flushPromises()

    const removeButton = wrapper.findAll('button').find((b) => b.text().trim() === 'Remove')
    expect(removeButton).toBeDefined()
    await removeButton!.trigger('click')
    await flushPromises()

    const confirm = dialogs().find((d) => d.textContent!.includes('Remove from group'))
    expect(confirm).toBeDefined()
    expect(confirm!.textContent).toContain('Grace Hopper')

    const confirmButton = Array.from(confirm!.querySelectorAll('button')).find(
      (b) => b.textContent!.trim() === 'Remove'
    )
    expect(confirmButton).toBeDefined()
    await confirmButton!.click()
    await flushPromises()

    const deleteCall = fetchMock.mock.calls.find(
      (c) => String(c[0]).includes('/group/7/members/2/')
    )
    expect(deleteCall).toBeDefined()
    expect(String(deleteCall![1]?.method).toUpperCase()).toBe('DELETE')
  })
})
