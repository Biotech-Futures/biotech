import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createRouter, createWebHashHistory, type Router, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { GroupPlanList, GroupPlanTask } from '@/utils/plansAPI'

// The real GroupPlanSection inside the section switcher: only the plan API
// and the other sections are replaced. `__esModule` is required or
// defineAsyncComponent will not unwrap the mock.
vi.mock('@/views/GroupSubmissionPage.vue', () => ({
  __esModule: true,
  default: { name: 'GroupSubmissionPageStub', template: '<div />' },
}))
vi.mock('@/views/FinalistPage.vue', () => ({
  __esModule: true,
  default: { name: 'FinalistPageStub', template: '<div />' },
}))
vi.mock('../GroupResults.vue', () => ({
  __esModule: true,
  default: { name: 'GroupResultsStub', template: '<div />' },
}))
vi.mock('@/utils/managementAPI', () => ({
  fetchGroupResults: vi.fn(async () => ({ marks_released: false, certificates_released: false })),
}))
vi.mock('@/utils/finalistAPI', () => ({
  fetchFinalist: vi.fn(async () => {
    throw new Error('not a finalist')
  }),
}))
const planApi = vi.hoisted(() => ({
  list: vi.fn<(groupId: string) => Promise<GroupPlanList>>(),
  toggle: vi.fn<(groupId: string, taskId: number, completed?: boolean) => Promise<GroupPlanTask>>(),
}))
vi.mock('@/utils/plansAPI', () => ({
  listGroupPlanTasks: planApi.list,
  toggleGroupPlanTask: planApi.toggle,
}))

const GroupSubmissionSection = (await import('../GroupSubmissionSection.vue')).default

const Host = {
  components: { GroupSubmissionSection },
  template: '<GroupSubmissionSection><div>tasks and discussion</div></GroupSubmissionSection>',
}
const ROUTES: RouteRecordRaw[] = [
  { path: '/groups/:id', name: 'group-detail', component: Host },
  { path: '/groups/:id/plan', name: 'group-plan', component: Host },
]

// Every group's plan has the same shared task (task ids are shared across groups).
const task = (completed: boolean): GroupPlanTask => ({
  id: 5, stage_id: 1, position: 0, name: 'Agree a meeting time', description: '', resource_url: '',
  resource_label: '', due_date: null, audience_role: 'student', completion_mode: 'per_group', completed,
  can_toggle: true,
})
const plan = (completed: boolean): GroupPlanList => ({
  year: 2026,
  stages: [{ id: 1, name: 'Getting started', description: '', position: 0 }],
  items: [task(completed)],
})

/** A request the test settles itself. */
function held<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

let wrapper: VueWrapper
let router: Router

/** Let requests answer and the lazily imported Plan section load. */
async function settle() {
  await flushPromises()
  await vi.dynamicImportSettled()
  await flushPromises()
}

async function mountAt(path: string) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const auth = useAuthStore()
  auth.user = { id: 1, current_role_name: 'student' } as never
  auth.initialized = true
  router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
  await router.push(path)
  await router.isReady()
  wrapper = mount(Host, { global: { plugins: [router, pinia] } })
  await settle()
}

const box = () => wrapper.find<HTMLInputElement>('[data-testid="plan-task-5"] input[type="checkbox"]')
const tab = (name: string) => wrapper.find(`[data-testid="section-tab-${name}"]`)

/** Tick the box with the save held, then leave Plan for Tasks and Chat and come back. */
async function tickThenLeaveAndReturn(reload: Promise<GroupPlanList>) {
  const save = held<GroupPlanTask>()
  planApi.toggle.mockReturnValueOnce(save.promise)
  await box().setValue(true)
  expect(planApi.toggle).toHaveBeenCalledWith('1', 5, true)

  await tab('tasks').trigger('click')
  await flushPromises()
  planApi.list.mockReturnValueOnce(reload)
  await tab('plan').trigger('click')
  await flushPromises()
  return save
}

beforeEach(() => {
  planApi.list.mockReset()
  planApi.toggle.mockReset()
  planApi.list.mockResolvedValue(plan(false))
})

describe('a tick still saving when the viewer leaves Plan', () => {
  it('shows the saved value once it answers, after coming back', async () => {
    await mountAt('/groups/1/plan')
    // Coming back reloads the plan, which answers with what it read before the tick.
    const save = await tickThenLeaveAndReturn(Promise.resolve(plan(false)))

    // Still saving: the saved state, locked, with nothing sent twice.
    expect(box().element.checked).toBe(false)
    expect(box().attributes('disabled')).toBeDefined()
    expect(planApi.toggle).toHaveBeenCalledTimes(1)

    save.resolve(task(true))
    await flushPromises()
    expect(box().element.checked).toBe(true)
    expect(box().attributes('disabled')).toBeUndefined()

    // The page kept it: leaving and coming back again, with the reload held, still shows it.
    await tab('tasks').trigger('click')
    await flushPromises()
    planApi.list.mockReturnValueOnce(held<GroupPlanList>().promise)
    await tab('plan').trigger('click')
    await flushPromises()
    expect(box().element.checked).toBe(true)
    expect(planApi.toggle).toHaveBeenCalledTimes(1)
  })

  it('is not undone by the reload when that answers after the save', async () => {
    await mountAt('/groups/1/plan')
    const reload = held<GroupPlanList>()
    const save = await tickThenLeaveAndReturn(reload.promise)

    save.resolve(task(true))
    await flushPromises()
    reload.resolve(plan(false))
    await flushPromises()

    expect(box().element.checked).toBe(true)
    expect(box().attributes('disabled')).toBeUndefined()
  })

  it('keeps the previous value and explains when the save fails', async () => {
    await mountAt('/groups/1/plan')
    const save = await tickThenLeaveAndReturn(Promise.resolve(plan(false)))

    save.reject(new Error('Network down'))
    await flushPromises()

    expect(box().element.checked).toBe(false)
    expect(box().attributes('disabled')).toBeUndefined()
    expect(wrapper.find('[data-testid="plan-task-5"] [role="alert"]').text()).toContain("Your tick wasn't saved")
  })

  it('never lands on another group switched to meanwhile', async () => {
    await mountAt('/groups/1/plan')
    const save = held<GroupPlanTask>()
    planApi.toggle.mockReturnValueOnce(save.promise)
    await box().setValue(true)

    // Group 2's plan has the same task, unticked.
    await router.push('/groups/2/plan')
    await flushPromises()
    expect(planApi.list).toHaveBeenLastCalledWith('2')

    save.resolve(task(true))
    await flushPromises()

    expect(box().element.checked).toBe(false)
    expect(box().attributes('disabled')).toBeUndefined()
    expect(planApi.toggle).toHaveBeenCalledTimes(1)
  })
})
