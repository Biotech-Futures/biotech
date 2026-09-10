import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminTasksPage from '@/views/admin/AdminTasksPage.vue'

const baseTask = {
  id: 1,
  name: 'Submit reflection',
  description: 'Write a short weekly update',
  due_date: '2026-09-15T00:00:00+00:00',
  status: 'todo',
  completed: false,
  parent: null,
  task_type: 'individual',
  group: null,
  assigned_user: 42,
  created_by: { id: 99, name: 'Admin User' },
  creator_role: 'global_admin',
  deleted_at: null,
  created_at: '2026-09-01T00:00:00+00:00',
  updated_at: '2026-09-01T00:00:00+00:00'
}

const buildTask = (overrides: Record<string, unknown> = {}) => ({ ...baseTask, ...overrides })

const fetchMockFor = (
  tasks: unknown[],
  total = tasks.length,
  options: {
    roleRecipientCount?: number
    roleRecipientCounts?: Array<number | 'error'>
    failDeleteIds?: number[]
    failPatchIds?: number[]
    patchDelayMs?: number
    trackDeletedTotal?: boolean
    roles?: Array<{ id?: number; roleName: string }>
  } = {}
) => {
  const deletedIds = new Set<number>()
  let roleRecipientLookupCount = 0
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const path = String(url)
    const method = init?.method ?? 'GET'
    const taskId = Number(path.match(/\/api\/v1\/admin\/task\/(\d+)\//)?.[1])
    let payload: unknown
    let status = 200

    if (path.includes('/services/csrf/')) {
      payload = { csrfToken: 'test-token' }
    } else if (path.includes('/api/v1/admin/task/role-recipients/')) {
      const roleRecipientResult = options.roleRecipientCounts?.[roleRecipientLookupCount]
      roleRecipientLookupCount += 1
      if (roleRecipientResult === 'error') {
        status = 500
        payload = { msg: 'Role recipients lookup failed', data: null }
      } else {
        payload = {
          msg: 'Role recipients retrieved successfully',
          data: {
            role: 'mentor',
            count: typeof roleRecipientResult === 'number'
              ? roleRecipientResult
              : options.roleRecipientCount ?? 2
          }
        }
      }
    } else if (path.includes('/api/v1/admin/task/') && method === 'POST') {
      payload = { msg: 'Task created successfully', data: buildTask({ id: 11 }) }
    } else if (path.includes('/api/v1/admin/task/') && method === 'DELETE') {
      if (options.failDeleteIds?.includes(taskId)) {
        status = 500
        payload = { msg: 'Task delete failed', data: null }
      } else {
        status = 204
        payload = null
        if (Number.isFinite(taskId)) deletedIds.add(taskId)
      }
    } else if (path.includes('/api/v1/admin/task/') && method === 'PATCH') {
      if (options.failPatchIds?.includes(taskId)) {
        status = 500
        payload = { msg: 'Task update failed', data: null }
      } else {
        payload = { msg: 'Task updated successfully', data: buildTask({ id: 1 }) }
      }
      if (options.patchDelayMs) {
        return new Promise((resolve) => {
          setTimeout(() => {
            resolve(
              new Response(JSON.stringify(payload), {
                status,
                headers: { 'Content-Type': 'application/json' }
              })
            )
          }, options.patchDelayMs)
        })
      }
    } else if (path.includes('/api/v1/admin/task/')) {
      const params = new URL(path).searchParams
      const currentTotal = options.trackDeletedTotal
        ? Math.max(0, total - deletedIds.size)
        : total
      payload = {
        msg: 'Tasks retrieved successfully',
        data: {
          items: tasks,
          total: currentTotal,
          page: Number(params.get('page') ?? 1),
          limit: Number(params.get('limit') ?? 25),
          has_more: currentTotal > tasks.length
        }
      }
    } else if (path.includes('/api/v1/admin/group/')) {
      payload = {
        msg: 'Groups retrieved successfully',
        data: {
          items: [{ id: 7, name: 'BTF Dummy Group 1', members: [], mentor: null, createdAt: '', updatedAt: '' }],
          total: 1,
          page: 1,
          limit: 200,
          has_more: false
        }
      }
    } else if (path.includes('/api/v1/admin/user/')) {
      payload = {
        msg: 'Users retrieved successfully',
        data: {
          items: [
            {
              id: 42,
              firstName: 'Ada',
              lastName: 'Lovelace',
              email: 'ada@example.edu',
              role: 'student',
              country: null,
              state: null,
              groupId: null,
              groupName: null,
              schoolName: null,
              mentorBackground: null,
              mentorInstitution: null,
              mentorReason: null,
              mentorMaxGroupCount: null,
              yearLevel: null,
              joinPermissionReceived: false,
              interests: [],
              isAdmin: false,
              isActive: true,
              hasLoggedIn: false,
              lastLogin: null,
              accountStatus: 'active',
              invitedAt: null,
              activatedAt: null,
              supervisorName: null,
              supervisorEmail: null,
              supervisees: []
            }
          ],
          total: 1,
          page: 1,
          limit: 200,
          hasMore: false
        }
      }
    } else if (path.includes('/api/v1/admin/event/meta/roles/')) {
      payload = {
        msg: 'Roles retrieved successfully',
        data: options.roles ?? [{ id: 2, roleName: 'mentor' }]
      }
    } else {
      payload = {}
    }

    return Promise.resolve(
      new Response(status === 204 ? null : JSON.stringify(payload), {
        status,
        headers: { 'Content-Type': 'application/json' }
      })
    )
  })
}

const lastTaskListUrl = (fetchMock: ReturnType<typeof vi.fn>) => {
  const call = [...fetchMock.mock.calls]
    .reverse()
    .find(([url]) => String(url).includes('/api/v1/admin/task/'))
  return new URL(String(call?.[0]))
}

const sortableButton = (wrapper: VueWrapper, label: string) =>
  wrapper
    .findAll('.admin-table__sort-btn')
    .find((button) => button.text().replace(/[^\w ]/g, '').trim() === label)

const mountPage = () => mount(AdminTasksPage, { global: { stubs: { Teleport: true } } })

const submitButton = (wrapper: VueWrapper) =>
  wrapper.findAll('button').find((button) => button.text().includes('Save'))

const buttonByText = (wrapper: VueWrapper, text: string) =>
  wrapper.findAll('button').find((button) => button.text().trim() === text)

const lastButtonByText = (wrapper: VueWrapper, text: string) =>
  [...wrapper.findAll('button')].reverse().find((button) => button.text().trim() === text)

const lastTaskMutation = (fetchMock: ReturnType<typeof vi.fn>, method: string) =>
  [...fetchMock.mock.calls]
    .reverse()
    .find(([url, init]) => String(url).includes('/api/v1/admin/task/') && init?.method === method)

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('AdminTasksPage', () => {
  it('loads tasks with the default due ascending sort and renders the table', async () => {
    const fetchMock = fetchMockFor([
      buildTask(),
      buildTask({
        id: 2,
        name: 'Prepare slides',
        description: '',
        task_type: 'group',
        group: 7,
        assigned_user: null,
        status: 'in_progress'
      })
    ])
    vi.stubGlobal('fetch', fetchMock)

    wrapper = mountPage()
    await flushPromises()

    const url = lastTaskListUrl(fetchMock)
    expect(url.pathname).toBe('/api/v1/admin/task/')
    expect(url.searchParams.get('page')).toBe('1')
    expect(url.searchParams.get('limit')).toBe('25')
    expect(url.searchParams.get('sortBy')).toBe('due')
    expect(url.searchParams.get('sortOrder')).toBe('asc')
    expect(url.searchParams.has('task_type')).toBe(false)

    expect(wrapper.text()).toContain('Submit reflection')
    expect(wrapper.text()).toContain('Write a short weekly update')
    expect(wrapper.text()).toContain('Individual')
    expect(wrapper.text()).toContain('User #42')
    expect(wrapper.text()).toContain('Prepare slides')
    expect(wrapper.text()).toContain('Group #7')
    expect(wrapper.text()).toContain('In Progress')

    const headers = wrapper
      .findAll('.admin-table__head')
      .map((header) => header.text().replace(/[^\w ]/g, '').trim())
    expect(headers).toEqual(['Name', 'Type', 'Target', 'Status', 'Due', 'Actions'])
    expect(wrapper.findAll('.admin-table__sort-btn').map((button) => button.text().replace(/[^\w ]/g, '').trim()))
      .toEqual(['Name', 'Type', 'Target', 'Status', 'Due'])
  })

  it('filters tasks by type and resets to the first page', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    expect(lastTaskListUrl(fetchMock).searchParams.get('page')).toBe('1')

    await wrapper.find<HTMLSelectElement>('#task-type-filter').setValue('group')
    await flushPromises()

    const params = lastTaskListUrl(fetchMock).searchParams
    expect(params.get('page')).toBe('1')
    expect(params.get('task_type')).toBe('group')
    expect(params.get('sortBy')).toBe('due')
    expect(params.get('sortOrder')).toBe('asc')
  })

  it('sorts task columns through server-side query parameters', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    const nameSort = sortableButton(wrapper, 'Name')
    expect(nameSort).toBeDefined()
    await nameSort!.trigger('click')
    await flushPromises()

    let params = lastTaskListUrl(fetchMock).searchParams
    expect(params.get('sortBy')).toBe('name')
    expect(params.get('sortOrder')).toBe('asc')

    await nameSort!.trigger('click')
    await flushPromises()

    params = lastTaskListUrl(fetchMock).searchParams
    expect(params.get('sortBy')).toBe('name')
    expect(params.get('sortOrder')).toBe('desc')
  })

  it('supports page navigation and page-size changes', async () => {
    const fetchMock = fetchMockFor([buildTask()], 60)
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()

    let params = lastTaskListUrl(fetchMock).searchParams
    expect(params.get('page')).toBe('2')
    expect(params.get('limit')).toBe('25')

    await wrapper.find<HTMLSelectElement>('.admin-table__page-size select').setValue('50')
    await flushPromises()

    params = lastTaskListUrl(fetchMock).searchParams
    expect(params.get('page')).toBe('1')
    expect(params.get('limit')).toBe('50')
  })

  it('supports row selection with the existing admin table pattern', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    expect(rowCheckboxes.length).toBeGreaterThan(1)
    await rowCheckboxes[1].setValue(true)
    await flushPromises()

    expect(wrapper.text()).toContain('1 task selected')
  })

  it('clears selected tasks when navigating to another page', async () => {
    const fetchMock = fetchMockFor([buildTask()], 60)
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await flushPromises()
    expect(wrapper.text()).toContain('1 task selected')

    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()

    expect(lastTaskListUrl(fetchMock).searchParams.get('page')).toBe('2')
    expect(wrapper.text()).not.toContain('task selected')
  })

  it('deletes an individual task after confirmation and refreshes the list', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await buttonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Delete task')
    expect(wrapper.text()).toContain('Delete "Submit reflection"? This cannot be undone.')

    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    const deleteCall = lastTaskMutation(fetchMock, 'DELETE') as [string, RequestInit]
    expect(deleteCall[0]).toContain('/api/v1/admin/task/1/')
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/v1/admin/task/')).length)
      .toBeGreaterThan(1)
  })

  it('shows individual delete failures inside the open confirmation dialog', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const fetchMock = fetchMockFor([buildTask()], 1, { failDeleteIds: [1] })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await buttonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Delete task')
    expect(wrapper.text()).toContain('Delete "Submit reflection"? This cannot be undone.')
    expect(wrapper.find('.admin-tasks__dialog-error').text()).toContain('Task delete failed')
    expect(wrapper.text()).toContain('Submit reflection')

    consoleSpy.mockRestore()
  })

  it('clamps to the new last page after deleting the final row on the final page', async () => {
    const fetchMock = fetchMockFor([buildTask({ id: 51 })], 51, { trackDeletedTotal: true })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    expect(lastTaskListUrl(fetchMock).searchParams.get('page')).toBe('3')

    await buttonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(lastTaskListUrl(fetchMock).searchParams.get('page')).toBe('2')
    expect(wrapper.text()).toContain('Page 2 of 2')
    expect(wrapper.text()).not.toContain('Page 3 of 2')
  })

  it('bulk deletes selected tasks and clears successful selections', async () => {
    const fetchMock = fetchMockFor([
      buildTask(),
      buildTask({ id: 2, name: 'Prepare slides', assigned_user: 43 })
    ])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await rowCheckboxes[2].setValue(true)
    await flushPromises()

    expect(wrapper.text()).toContain('2 tasks selected')
    await buttonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Delete 2 selected tasks? This cannot be undone.')

    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    const deleteCalls = fetchMock.mock.calls.filter(
      ([url, init]) => String(url).includes('/api/v1/admin/task/') && init?.method === 'DELETE'
    )
    expect(deleteCalls.map(([url]) => String(url))).toEqual(
      expect.arrayContaining([
        expect.stringContaining('/api/v1/admin/task/1/'),
        expect.stringContaining('/api/v1/admin/task/2/')
      ])
    )
    expect(wrapper.text()).not.toContain('tasks selected')
  })

  it('clamps to the new last page after bulk deleting final rows on the final page', async () => {
    const fetchMock = fetchMockFor(
      [buildTask({ id: 51 }), buildTask({ id: 52, name: 'Prepare slides', assigned_user: 43 })],
      52,
      { trackDeletedTotal: true }
    )
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    await wrapper.find('button[aria-label="Next page"]').trigger('click')
    await flushPromises()
    expect(lastTaskListUrl(fetchMock).searchParams.get('page')).toBe('3')

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await rowCheckboxes[2].setValue(true)
    await flushPromises()

    await buttonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()
    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    expect(lastTaskListUrl(fetchMock).searchParams.get('page')).toBe('2')
    expect(wrapper.text()).toContain('Page 2 of 2')
    expect(wrapper.text()).not.toContain('Page 3 of 2')
  })

  it('bulk status updates selected tasks and reports partial failures', async () => {
    const fetchMock = fetchMockFor(
      [buildTask(), buildTask({ id: 2, name: 'Prepare slides', assigned_user: 43 })],
      2,
      { failPatchIds: [2] }
    )
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await rowCheckboxes[2].setValue(true)
    await flushPromises()

    await wrapper.find<HTMLSelectElement>('#task-bulk-status').setValue('done')
    await flushPromises()

    const patchCalls = fetchMock.mock.calls.filter(
      ([url, init]) => String(url).includes('/api/v1/admin/task/') && init?.method === 'PATCH'
    )
    expect(patchCalls).toHaveLength(2)
    expect(patchCalls.map(([, init]) => JSON.parse(String(init?.body)).status)).toEqual(['done', 'done'])
    expect(wrapper.text()).toContain('Updated 1, but 1 could not be updated.')
    expect(wrapper.text()).toContain('1 task selected')
  })

  it('disables toolbar controls while a bulk task action is in progress', async () => {
    const fetchMock = fetchMockFor([buildTask()], 1, { patchDelayMs: 50 })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    const rowCheckboxes = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
    await rowCheckboxes[1].setValue(true)
    await flushPromises()

    await wrapper.find<HTMLSelectElement>('#task-bulk-status').setValue('done')

    expect(wrapper.find<HTMLSelectElement>('#task-type-filter').attributes('disabled')).toBeDefined()
    expect(buttonByText(wrapper, 'Add Task')!.attributes('disabled')).toBeDefined()

    await new Promise((resolve) => setTimeout(resolve, 60))
    await flushPromises()
  })

  it('shows empty and error states', async () => {
    const emptyFetch = fetchMockFor([])
    vi.stubGlobal('fetch', emptyFetch)
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No tasks found.')
    wrapper.unmount()

    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const errorFetch = vi.fn().mockResolvedValue(new Response('boom', { status: 500 }))
    vi.stubGlobal('fetch', errorFetch)
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    consoleSpy.mockRestore()
  })

  it('creates a group task and refreshes the task list', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Review group plan')
    await wrapper.find<HTMLSelectElement>('#task-group').setValue('7')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      task_type: 'group',
      group: 7,
      assigned_user: null,
      assigned_role: null,
      name: 'Review group plan',
      description: '',
      due_date: null,
      status: 'todo',
      parent: null
    })
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/v1/admin/task/')).length)
      .toBeGreaterThan(1)
  })

  it('creates a task with the selected due date at midnight UTC', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Review group plan')
    await wrapper.find<HTMLSelectElement>('#task-group').setValue('7')
    await wrapper.find<HTMLInputElement>('#task-due-date').setValue('2026-10-04')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toMatchObject({
      name: 'Review group plan',
      due_date: '2026-10-04T00:00:00Z'
    })
  })

  it('disables Save until the task form has valid required fields and assignment', async () => {
    const fetchMock = fetchMockFor([buildTask()], 1, { roleRecipientCount: 0 })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeDefined()

    await wrapper.find<HTMLInputElement>('#task-name').setValue('Review group plan')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeDefined()

    await wrapper.find<HTMLSelectElement>('#task-group').setValue('7')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeUndefined()

    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeDefined()

    await wrapper.find<HTMLSelectElement>('#task-assign-mode').setValue('role')
    await wrapper.find<HTMLSelectElement>('#task-role').setValue('mentor')
    await flushPromises()

    expect(wrapper.text()).toContain('No active users currently have this role.')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeDefined()
  })

  it('shows a retryable error when role recipient lookup fails', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const fetchMock = fetchMockFor([buildTask()], 1, { roleRecipientCounts: ['error', 3] })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    await wrapper.find<HTMLSelectElement>('#task-assign-mode').setValue('role')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Send mentor update')
    await wrapper.find<HTMLSelectElement>('#task-role').setValue('mentor')
    await flushPromises()

    expect(wrapper.text()).toContain('Recipient count could not be loaded. Try again.')
    expect(wrapper.text()).not.toContain('Creates a separate task for every mentor.')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeDefined()

    const lookupCallsBeforeRetry = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('/api/v1/admin/task/role-recipients/')
    )
    expect(lookupCallsBeforeRetry).toHaveLength(1)

    await buttonByText(wrapper, 'Retry')!.trigger('click')
    await flushPromises()

    const lookupCallsAfterRetry = fetchMock.mock.calls.filter(([url]) =>
      String(url).includes('/api/v1/admin/task/role-recipients/')
    )
    expect(lookupCallsAfterRetry).toHaveLength(2)
    expect(wrapper.text()).not.toContain('Recipient count could not be loaded. Try again.')
    expect(wrapper.text()).toContain('Creates 3 separate tasks')
    expect(submitButton(wrapper)!.attributes('disabled')).toBeUndefined()

    consoleSpy.mockRestore()
  })

  it('renders duplicate role names without changing role assignment behavior', async () => {
    const fetchMock = fetchMockFor([buildTask()], 1, {
      roles: [
        { id: 2, roleName: 'mentor' },
        { id: 3, roleName: 'mentor' }
      ]
    })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    await wrapper.find<HTMLSelectElement>('#task-assign-mode').setValue('role')

    const roleOptions = wrapper.findAll<HTMLOptionElement>('#task-role option')
    expect(roleOptions.filter((option) => option.element.value === 'mentor')).toHaveLength(2)

    await wrapper.find<HTMLInputElement>('#task-name').setValue('Send mentor update')
    await wrapper.find<HTMLSelectElement>('#task-role').setValue('mentor')
    await flushPromises()
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()
    await buttonByText(wrapper, 'Create tasks')!.trigger('click')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body)).assigned_role).toBe('mentor')
  })

  it('creates an individual task for a selected user', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Message mentor')
    await wrapper.find<HTMLSelectElement>('#task-user').setValue('42')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toMatchObject({
      task_type: 'individual',
      group: null,
      assigned_user: 42,
      assigned_role: null,
      name: 'Message mentor'
    })
  })

  it('previews role recipient counts and creates role fan-out tasks after confirmation', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    await wrapper.find<HTMLSelectElement>('#task-assign-mode').setValue('role')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Send mentor update')
    await wrapper.find<HTMLSelectElement>('#task-role').setValue('mentor')
    await flushPromises()

    expect(wrapper.text()).toContain('Creates 2 separate tasks')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    expect(wrapper.text()).toContain('Create role tasks')
    expect(wrapper.text()).toContain(
      'Create a separate task for every user with the mentor role? 2 recipients will each receive a separate task. There is no single action to undo this assignment.'
    )
    await buttonByText(wrapper, 'Create tasks')!.trigger('click')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toMatchObject({
      task_type: 'individual',
      group: null,
      assigned_user: null,
      assigned_role: 'mentor',
      name: 'Send mentor update'
    })
  })

  it('keeps the role fan-out form open with values intact when confirmation is cancelled', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    await wrapper.find<HTMLSelectElement>('#task-assign-mode').setValue('role')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Send mentor update')
    await wrapper.find<HTMLSelectElement>('#task-role').setValue('mentor')
    await flushPromises()

    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Create role tasks')

    const cancelButtons = wrapper.findAll('button').filter((button) => button.text().trim() === 'Cancel')
    await cancelButtons[cancelButtons.length - 1].trigger('click')
    await flushPromises()

    expect(lastTaskMutation(fetchMock, 'POST')).toBeUndefined()
    expect(wrapper.find<HTMLInputElement>('#task-name').element.value).toBe('Send mentor update')
    expect(wrapper.find<HTMLSelectElement>('#task-role').element.value).toBe('mentor')
    expect(wrapper.text()).not.toContain('Create role tasks')
  })

  it('clears stale assignment values when switching task type and individual assignment mode', async () => {
    const fetchMock = fetchMockFor([buildTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text().includes('Add Task'))!.trigger('click')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Notify participants')
    await wrapper.find<HTMLSelectElement>('#task-group').setValue('7')
    await wrapper.find<HTMLSelectElement>('#task-type').setValue('individual')
    await wrapper.find<HTMLSelectElement>('#task-user').setValue('42')
    await wrapper.find<HTMLSelectElement>('#task-assign-mode').setValue('role')
    await wrapper.find<HTMLSelectElement>('#task-role').setValue('mentor')
    await flushPromises()

    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()
    await buttonByText(wrapper, 'Create tasks')!.trigger('click')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toMatchObject({
      task_type: 'individual',
      group: null,
      assigned_user: null,
      assigned_role: 'mentor',
      name: 'Notify participants'
    })
  })

  it('edits child task details without changing assignment fields, due datetime, or parent', async () => {
    const originalDueDate = '2026-09-15T14:30:00+00:00'
    const fetchMock = fetchMockFor([buildTask({ parent: 99, due_date: originalDueDate })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')
    await wrapper.find<HTMLInputElement>('#task-name').setValue('Updated reflection')
    await wrapper.find<HTMLSelectElement>('#task-status').setValue('in_progress')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'PATCH') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      name: 'Updated reflection',
      description: 'Write a short weekly update',
      due_date: originalDueDate,
      status: 'in_progress',
      parent: 99
    })
  })

  it('sends midnight UTC when an edited task due date is changed', async () => {
    const fetchMock = fetchMockFor([buildTask({ due_date: '2026-09-15T14:30:00+00:00' })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')
    await wrapper.find<HTMLInputElement>('#task-due-date').setValue('2026-09-20')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'PATCH') as [string, RequestInit]
    expect(JSON.parse(String(init.body)).due_date).toBe('2026-09-20T00:00:00Z')
  })

  it('sends null when an edited task due date is cleared', async () => {
    const fetchMock = fetchMockFor([buildTask({ due_date: '2026-09-15T14:30:00+00:00' })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')
    await wrapper.find<HTMLInputElement>('#task-due-date').setValue('')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastTaskMutation(fetchMock, 'PATCH') as [string, RequestInit]
    expect(JSON.parse(String(init.body)).due_date).toBeNull()
  })
})
