import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount, flushPromises, type VueWrapper } from '@vue/test-utils'
import AdminPlanTasksPage from '@/views/admin/AdminPlanTasksPage.vue'

const stage = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  name: 'Getting started',
  description: 'Read this first',
  position: 0,
  ...overrides
})

const task = (overrides: Record<string, unknown> = {}) => ({
  id: 10,
  stage_id: 1,
  position: 0,
  name: 'Read the guide',
  description: 'A short read',
  resource_url: '',
  resource_label: '',
  due_date: null,
  audience_role: 'student',
  completion_mode: 'per_person',
  has_completions: false,
  created_by: { id: 99, name: 'Admin User' },
  created_at: '2026-09-01T00:00:00+00:00',
  updated_at: '2026-09-01T00:00:00+00:00',
  ...overrides
})

const fetchMockFor = (
  stages: unknown[],
  tasks: unknown[],
  options: {
    total?: number
    failStageDeleteIds?: number[]
    failTaskDeleteIds?: number[]
    stageDeleteMessage?: string
  } = {}
) => {
  const deletedStageIds = new Set<number>()
  const deletedTaskIds = new Set<number>()
  return vi.fn().mockImplementation((url: string, init?: RequestInit) => {
    const path = String(url)
    const method = init?.method ?? 'GET'
    const stageMatch = path.match(/\/api\/v1\/admin\/plan-stage\/(\d+)\//)
    const taskMatch = path.match(/\/api\/v1\/admin\/plan-task\/(\d+)\//)
    let payload: unknown
    let status = 200

    if (path.includes('/services/csrf/')) {
      payload = { csrfToken: 'test-token' }
    } else if (path.includes('/api/v1/admin/plan-stage/') && method === 'GET') {
      payload = {
        msg: 'Stages retrieved successfully',
        data: { items: stages.filter((s) => !deletedStageIds.has((s as { id: number }).id)) }
      }
    } else if (path.includes('/api/v1/admin/plan-stage/') && method === 'POST') {
      payload = { msg: 'Stage created successfully', data: stage({ id: 7 }) }
      status = 201
    } else if (stageMatch && method === 'PATCH') {
      payload = { msg: 'Stage updated successfully', data: stage({ id: Number(stageMatch[1]) }) }
    } else if (stageMatch && method === 'DELETE') {
      const id = Number(stageMatch[1])
      if (options.failStageDeleteIds?.includes(id)) {
        status = 400
        payload = {
          msg: options.stageDeleteMessage ?? 'This stage still contains tasks. Remove or delete them first.',
          data: null
        }
      } else {
        status = 204
        payload = null
        deletedStageIds.add(id)
      }
    } else if (path.includes('/api/v1/admin/plan-task/') && method === 'GET' && !taskMatch) {
      const visible = tasks.filter((t) => !deletedTaskIds.has((t as { id: number }).id))
      payload = {
        msg: 'Tasks retrieved successfully',
        data: {
          items: visible,
          total: options.total ?? visible.length,
          page: 1,
          limit: 25,
          has_more: false
        }
      }
    } else if (path.includes('/api/v1/admin/plan-task/') && method === 'POST') {
      payload = { msg: 'Task created successfully', data: task({ id: 11 }) }
      status = 201
    } else if (taskMatch && method === 'PATCH') {
      payload = { msg: 'Task updated successfully', data: task({ id: Number(taskMatch[1]) }) }
    } else if (taskMatch && method === 'DELETE') {
      const id = Number(taskMatch[1])
      if (options.failTaskDeleteIds?.includes(id)) {
        status = 500
        payload = { msg: 'Task delete failed', data: null }
      } else {
        status = 204
        payload = null
        deletedTaskIds.add(id)
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

const mountPage = () => mount(AdminPlanTasksPage, { global: { stubs: { Teleport: true } } })

const buttonByText = (wrapper: VueWrapper, text: string) =>
  wrapper.findAll('button').find((button) => button.text().trim() === text)

const submitForm = async (wrapper: VueWrapper) => {
  await wrapper.find('form').trigger('submit')
  await flushPromises()
}

const dialogConfirm = (wrapper: VueWrapper) =>
  wrapper.findAll('.admin-modal__footer button').find((button) => button.text().includes('Delete'))

const taskRowButton = (wrapper: VueWrapper, text: string) =>
  wrapper
    .findAll('.data-table-actions-col button')
    .find((b) => b.text().trim() === text)

const lastMutation = (fetchMock: ReturnType<typeof vi.fn>, path: string, method: string) =>
  [...fetchMock.mock.calls]
    .reverse()
    .find(([url, init]) => String(url).includes(path) && init?.method === method)

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

describe('AdminPlanTasksPage', () => {
  it('loads stages and tasks, rendering a stage rail and the task table', async () => {
    const fetchMock = fetchMockFor(
      [stage(), stage({ id: 2, name: 'Next step', position: 1 })],
      [task(), task({ id: 11, stage_id: 2, name: 'Second task' })]
    )
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    expect(wrapper.text()).toContain('Group Plans')
    expect(wrapper.text()).toContain('Getting started')
    expect(wrapper.text()).toContain('Next step')
    expect(wrapper.find('.data-table').exists()).toBe(true)
    expect(wrapper.text()).toContain('Read the guide')
    expect(wrapper.text()).toContain('Second task')
  })

  it('creates a stage through the sheet', async () => {
    const fetchMock = fetchMockFor([stage()], [task()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await buttonByText(wrapper, 'Add Stage')!.trigger('click')
    await flushPromises()
    await wrapper.find('#plan-stage-name').setValue('Wrap up')
    await submitForm(wrapper)

    const post = lastMutation(fetchMock, '/api/v1/admin/plan-stage/', 'POST')
    expect(post).toBeTruthy()
    const body = JSON.parse((post![1] as RequestInit).body as string)
    expect(body).toMatchObject({ name: 'Wrap up', description: '', position: 1 })
  })

  it('creates a task defaulting to the selected stage', async () => {
    const fetchMock = fetchMockFor([stage(), stage({ id: 2, name: 'Second', position: 1 })], [task()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.findAll('.admin-plan__stage-select')[1].trigger('click')
    await flushPromises()
    await buttonByText(wrapper, 'Add Task')!.trigger('click')
    await flushPromises()
    await wrapper.find('#plan-task-name').setValue('Do the thing')
    await submitForm(wrapper)

    const post = lastMutation(fetchMock, '/api/v1/admin/plan-task/', 'POST')
    expect(post).toBeTruthy()
    const body = JSON.parse((post![1] as RequestInit).body as string)
    expect(body).toMatchObject({
      name: 'Do the thing',
      stage_id: 2,
      audience_role: 'student',
      completion_mode: 'per_person'
    })
  })

  it('locks audience and completion mode when the task has completions', async () => {
    const fetchMock = fetchMockFor([stage()], [task({ has_completions: true })])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await taskRowButton(wrapper, 'Edit')!.trigger('click')
    await flushPromises()

    const audience = wrapper.find('#plan-task-audience')
    expect(audience.attributes('disabled')).toBeDefined()
    expect(wrapper.find('.app-select.is-disabled').exists()).toBe(true)
    const radios = wrapper.findAll('.admin-plan-task-form__radio input')
    expect(radios.length).toBeGreaterThan(0)
    expect(radios.every((radio) => radio.attributes('disabled') !== undefined)).toBe(true)
    expect(wrapper.text()).toContain('locked')
  })

  it('refuses to delete a stage still holding tasks and shows the reason', async () => {
    const fetchMock = fetchMockFor([stage()], [task()], { failStageDeleteIds: [1] })
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await wrapper.find('.admin-plan__stage-actions button:last-child').trigger('click')
    await flushPromises()
    await dialogConfirm(wrapper)!.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('still contains tasks')
  })

  it('deletes a task after confirming', async () => {
    const fetchMock = fetchMockFor([stage()], [task()])
    vi.stubGlobal('fetch', fetchMock)
    wrapper = mountPage()
    await flushPromises()

    await taskRowButton(wrapper, 'Delete')!.trigger('click')
    await flushPromises()
    await dialogConfirm(wrapper)!.trigger('click')
    await flushPromises()

    const del = lastMutation(fetchMock, '/api/v1/admin/plan-task/10/', 'DELETE')
    expect(del).toBeTruthy()
  })
})
