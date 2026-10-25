import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { listGroupPlanTasks, toggleGroupPlanTask, type GroupPlanList, type GroupPlanTask } from '@/utils/plansAPI'
import { ApiError } from '@/utils/apiError'
import { ensureCsrfCookie } from '@/utils/csrf'

// The CSRF layer is mocked, as in managementAPI.spec.ts, so requests need no
// /services/csrf/ round-trip; the real shared requestJson runs underneath.
vi.mock('@/utils/csrf', () => ({
  ensureCsrfCookie: vi.fn(async () => true),
  buildSessionHeaders: ({
    includeCSRF,
    headers
  }: {
    includeCSRF?: boolean
    headers?: Record<string, string>
  }) => ({ ...(headers || {}), ...(includeCSRF ? { 'X-CSRFToken': 'csrf-test' } : {}) })
}))
const csrfMock = vi.mocked(ensureCsrfCookie)

const fetchMock = vi.fn()

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

const lastCall = () => {
  const call = fetchMock.mock.calls.at(-1)!
  return {
    url: String(call[0]),
    init: (call[1] ?? {}) as RequestInit,
    headers: ((call[1] ?? {}) as RequestInit).headers as Record<string, string>
  }
}

const task = (overrides: Partial<GroupPlanTask> = {}): GroupPlanTask => ({
  id: 11,
  stage_id: 3,
  position: 0,
  name: 'Meet your mentor',
  description: 'Say hello.',
  resource_url: '',
  resource_label: '',
  due_date: null,
  audience_role: 'student',
  completion_mode: 'per_person',
  completed: false,
  can_toggle: true,
  ...overrides
})

beforeEach(() => {
  fetchMock.mockReset()
  csrfMock.mockReset()
  csrfMock.mockResolvedValue(true)
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('listGroupPlanTasks', () => {
  it('GETs the group plan with the session and no CSRF round-trip', async () => {
    const plan: GroupPlanList = {
      year: 2026,
      stages: [{ id: 3, name: 'Getting started', description: '', position: 0 }],
      items: [
        task(),
        // An admin's view of someone's individual task, and a shared task.
        task({ id: 12, completed: null, can_toggle: false, due_date: '2026-11-05' }),
        task({ id: 13, completion_mode: 'per_group', completed: true })
      ]
    }
    fetchMock.mockResolvedValueOnce(jsonResponse(plan))

    const result = await listGroupPlanTasks(7)

    const { url, init, headers } = lastCall()
    expect(url).toMatch(/\/api\/v1\/plans\/groups\/7\/tasks\/$/)
    expect(init.method ?? 'GET').toBe('GET')
    expect(init.credentials).toBe('include')
    expect(headers['X-CSRFToken']).toBeUndefined()
    expect(csrfMock).not.toHaveBeenCalled()
    expect(result).toEqual(plan)
    expect(result.items.map((item) => item.completed)).toEqual([false, null, true])
  })

  it('passes through an empty plan for a group outside the current cohort', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ year: 2026, stages: [], items: [] }))
    await expect(listGroupPlanTasks('7')).resolves.toEqual({ year: 2026, stages: [], items: [] })
  })
})

describe('toggleGroupPlanTask', () => {
  it.each([
    ['ticks', true, { completed: true }],
    ['unticks', false, { completed: false }],
    ['flips when completed is omitted', undefined, {}]
  ])('%s', async (_label, completed, body) => {
    fetchMock.mockResolvedValueOnce(jsonResponse(task({ completed: completed ?? true })))

    await toggleGroupPlanTask(7, 11, completed)

    const { url, init, headers } = lastCall()
    expect(url).toMatch(/\/api\/v1\/plans\/groups\/7\/tasks\/11\/check\/$/)
    expect(init.method).toBe('POST')
    expect(init.credentials).toBe('include')
    expect(headers['X-CSRFToken']).toBe('csrf-test')
    expect(csrfMock).toHaveBeenCalledTimes(1)
    // Exactly the documented body: never a user id or any other field.
    expect(JSON.parse(String(init.body))).toEqual(body)
  })

  it('resolves to the updated task', async () => {
    const updated = task({ completion_mode: 'per_group', completed: true })
    fetchMock.mockResolvedValueOnce(jsonResponse(updated))
    await expect(toggleGroupPlanTask(7, 11, true)).resolves.toEqual(updated)
  })

  it.each([
    [403, "You can't tick this task."],
    [404, 'Task not found.'],
    [400, "'completed' must be true or false."]
  ])('turns a %i into an ApiError with the server message', async (status, error) => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ error, code: 'x', request_id: 'r' }, status))

    const failure = await toggleGroupPlanTask(7, 11, true).catch((err: unknown) => err)

    expect(failure).toBeInstanceOf(ApiError)
    expect((failure as ApiError).status).toBe(status)
    expect((failure as ApiError).message).toBe(error)
  })

  it('does not send the request when the secure session cannot be set up', async () => {
    csrfMock.mockResolvedValueOnce(false)
    await expect(toggleGroupPlanTask(7, 11, true)).rejects.toThrow('Could not initialize a secure session')
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
