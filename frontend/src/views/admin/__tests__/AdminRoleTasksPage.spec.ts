import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminRoleTasksPage from '@/views/admin/AdminRoleTasksPage.vue'

const baseRoleTask = {
  id: 3,
  name: 'Mentor onboarding',
  description: 'Complete the onboarding checklist',
  due_date: null,
  role: { id: 2, roleName: 'mentor' },
  created_by: { id: 99, name: 'Admin User' },
  creator_role: 'global_admin',
  deleted_at: null,
  created_at: '2026-09-01T00:00:00+00:00',
  updated_at: '2026-09-01T00:00:00+00:00',
  completed_count: 4,
  holder_count: 12
}

const buildRoleTask = (overrides: Record<string, unknown> = {}) => ({ ...baseRoleTask, ...overrides })

const fetchMockFor = (
  roleTasks: unknown[],
  total = roleTasks.length,
  options: {
    roleRecipientCount?: number
    failDeleteIds?: number[]
  } = {}
) =>
  vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const path = String(url)
    const method = init?.method ?? 'GET'
    const roleTaskId = Number(path.match(/\/api\/v1\/admin\/role-task\/(\d+)\//)?.[1])
    let payload: unknown
    let status = 200

    if (path.includes('/services/csrf/')) {
      payload = { csrfToken: 'test-token' }
    } else if (path.includes('/api/v1/admin/role-task/role-recipients/')) {
      payload = {
        msg: 'Recipient count retrieved successfully',
        data: { role: 'mentor', count: options.roleRecipientCount ?? 5 }
      }
    } else if (path.includes('/api/v1/admin/role-task/') && method === 'POST') {
      payload = { msg: 'Role task created successfully', data: buildRoleTask({ id: 11 }) }
    } else if (path.includes('/api/v1/admin/role-task/') && method === 'DELETE') {
      if (options.failDeleteIds?.includes(roleTaskId)) {
        status = 500
        payload = { msg: 'Role task delete failed', data: null }
      } else {
        status = 204
        payload = null
      }
    } else if (path.includes('/api/v1/admin/role-task/') && method === 'PATCH') {
      payload = { msg: 'Role task updated successfully', data: buildRoleTask({ id: 3, name: 'Updated' }) }
    } else if (path.includes('/api/v1/admin/role-task/')) {
      payload = {
        msg: 'Role tasks retrieved successfully',
        data: { items: roleTasks, total, page: 1, limit: 25, has_more: false }
      }
    } else if (path.includes('/api/v1/admin/event/meta/roles/')) {
      payload = { msg: 'Roles retrieved successfully', data: [{ id: 2, roleName: 'mentor' }] }
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

const mountPage = () =>
  mount(AdminRoleTasksPage, { global: { stubs: { Teleport: true, RouterLink: true } } })

const submitButton = (wrapper: VueWrapper) =>
  wrapper.findAll('button').find((button) => button.text().includes('Save'))

const buttonByText = (wrapper: VueWrapper, text: string) =>
  wrapper.findAll('button').find((button) => button.text().trim() === text)

const lastButtonByText = (wrapper: VueWrapper, text: string) =>
  [...wrapper.findAll('button')].reverse().find((button) => button.text().trim() === text)

const lastRoleTaskMutation = (fetchMock: ReturnType<typeof vi.fn>, method: string) =>
  [...fetchMock.mock.calls]
    .reverse()
    .find(([url, init]) => String(url).includes('/api/v1/admin/role-task/') && init?.method === method)

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('AdminRoleTasksPage', () => {
  it('loads and renders role tasks', async () => {
    const fetchMock = fetchMockFor([buildRoleTask()])
    vi.stubGlobal('fetch', fetchMock)

    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Mentor onboarding')
    expect(wrapper.text()).toContain('mentor')
  })

  it('shows completed-vs-holder progress as a read-only count, not an editable status', async () => {
    const fetchMock = fetchMockFor([buildRoleTask({ completed_count: 4, holder_count: 12 })])
    vi.stubGlobal('fetch', fetchMock)

    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('4/12')
    expect(wrapper.find('select#role-task-status').exists()).toBe(false)
  })

  it('shows zero over zero when the role currently has no holders', async () => {
    const fetchMock = fetchMockFor([buildRoleTask({ completed_count: 0, holder_count: 0 })])
    vi.stubGlobal('fetch', fetchMock)

    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('0/0')
  })

  it('creates a role task for the selected role after a recipient preview', async () => {
    const fetchMock = fetchMockFor([buildRoleTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await buttonByText(wrapper, 'Add Role Task')!.trigger('click')
    await wrapper.find<HTMLSelectElement>('#role-task-role').setValue('mentor')
    await flushPromises()

    expect(wrapper.text()).toContain('5 active users currently have this role')

    await wrapper.find<HTMLInputElement>('#role-task-name').setValue('Send onboarding form')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastRoleTaskMutation(fetchMock, 'POST') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      role: 'mentor',
      name: 'Send onboarding form',
      description: '',
      due_date: null
    })
  })

  it('edits a role task without re-sending the role (bulk-edit in one place)', async () => {
    const fetchMock = fetchMockFor([buildRoleTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await buttonByText(wrapper, 'Edit')!.trigger('click')
    await wrapper.find<HTMLInputElement>('#role-task-name').setValue('Updated name')
    await submitButton(wrapper)!.trigger('submit')
    await flushPromises()

    const [, init] = lastRoleTaskMutation(fetchMock, 'PATCH') as [string, RequestInit]
    expect(JSON.parse(String(init.body))).toEqual({
      name: 'Updated name',
      description: 'Complete the onboarding checklist',
      due_date: null
    })
    expect(wrapper.find('#role-task-role').exists()).toBe(false)
  })

  it('deletes a role task after confirmation', async () => {
    const fetchMock = fetchMockFor([buildRoleTask()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await buttonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Delete role task')

    await lastButtonByText(wrapper, 'Delete')!.trigger('click')
    await flushPromises()

    const deleteCall = lastRoleTaskMutation(fetchMock, 'DELETE') as [string, RequestInit]
    expect(deleteCall[0]).toContain('/api/v1/admin/role-task/3/')
  })

  it('shows an empty state when there are no role tasks', async () => {
    const fetchMock = fetchMockFor([])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('No role tasks found.')
  })
})
