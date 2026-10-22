import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ApiError } from '@/utils/apiError'


// `__esModule` is required or defineAsyncComponent will not unwrap the mock.
vi.mock('@/views/GroupSubmissionPage.vue', () => ({
  __esModule: true,
  default: { name: 'GroupSubmissionPageStub', template: '<div data-testid="portal-stub" />' },
}))

// What's out for the group; nothing, unless a test says otherwise.
const results = vi.hoisted(() => ({
  current: {
    marks_released: false,
    certificates_released: false,
    certificates_withheld: false,
    has_submission: true,
    year: 2026,
    components: [],
    summary: null,
    summary_file_name: '',
    certificates: []
  } as Record<string, unknown>
}))
vi.mock('@/utils/managementAPI', () => ({
  fetchGroupResults: vi.fn(async () => results.current)
}))
// Whether the group is a finalist: the server answers, or refuses.
const finalist = vi.hoisted(() => ({ is: false }))
vi.mock('@/utils/finalistAPI', () => ({
  fetchFinalist: vi.fn(async () => {
    if (!finalist.is) throw new Error('not a finalist')
    return {}
  })
}))
vi.mock('@/views/FinalistPage.vue', () => ({
  __esModule: true,
  default: { name: 'FinalistPageStub', template: '<div data-testid="finalist-stub" />' }
}))
// The group's plan: empty unless a test says otherwise; a test may answer
// each group's request itself to control timing.
const planApi = vi.hoisted(() => ({
  list: vi.fn<(groupId: string) => Promise<unknown>>(async () => ({ year: 2026, stages: [], items: [] })),
}))
vi.mock('@/utils/plansAPI', () => ({ listGroupPlanTasks: planApi.list }))
vi.mock('@/components/plans/GroupPlanSection.vue', () => ({
  __esModule: true,
  default: {
    name: 'GroupPlanSectionStub',
    props: ['groupId', 'stages', 'items'],
    template: '<div data-testid="plan-stub">{{ groupId }}:{{ items.map((i) => i.name).join(",") }}</div>',
  },
}))
vi.mock('../GroupResults.vue', () => ({
  __esModule: true,
  default: { name: 'GroupResultsStub', props: ['groupId', 'results'], template: '<div data-testid="results-stub" />' }
}))

const GroupSubmissionSection = (await import('../GroupSubmissionSection.vue')).default

const Host = {
  components: { GroupSubmissionSection },
  template: `
    <GroupSubmissionSection>
      <div data-testid="host-content">tasks and discussion</div>
    </GroupSubmissionSection>
  `,
}

// Includes the redirect that keeps links in sent emails working.
const ROUTES: RouteRecordRaw[] = [
  { path: '/groups/:id', name: 'group-detail', component: Host },
  { path: '/groups/:id/submission', name: 'group-submission', component: Host },
  { path: '/groups/:id/finalist', name: 'group-finalist', component: Host },
  { path: '/groups/:id/results', name: 'group-results', component: Host },
  { path: '/groups/:id/plan', name: 'group-plan', component: Host },
  { path: '/submission/:id', redirect: (to) => `/groups/${to.params.id}/submission` },
]

const mountAt = async (path: string, role: string | null = null) => {
  const pinia = createPinia()
  setActivePinia(pinia)

  const auth = useAuthStore()
  auth.user = { id: 1, current_role_name: role } as never
  auth.initialized = true

  const router = createRouter({ history: createWebHashHistory(), routes: ROUTES })
  await router.push(path)
  await router.isReady()

  const wrapper = mount(Host, { global: { plugins: [router, pinia] } })
  await flushPromises()
  return { wrapper, router }
}

describe('the real route table', () => {
  // Read as text: importing the table would pull every view into the Vitest TS project.
  const source = readFileSync(resolve(process.cwd(), 'src/router/routes.ts'), 'utf8')
  const records = [...source.matchAll(/path:\s*'([^']*)',\s*name:\s*'([^']+)'/g)]
  const names = records.map(([, , name]) => name)

  it('found the route records it means to check', () => {
    expect(names.length).toBeGreaterThanOrEqual(15)
  })

  it('gives every named route a distinct name', () => {
    const duplicates = names.filter((name, i) => names.indexOf(name) !== i)

    expect(duplicates).toEqual([])
  })

  it('points the submission route at the group page', () => {
    const pathFor = (name: string) => records.find(([, , n]) => n === name)?.[1]

    expect(pathFor('group-submission')).toBe('/groups/:id/submission')
  })

  it('still answers the old path the emails link to', () => {
    // Emails already sent link to /#/submission/{id}.
    expect(source).toMatch(/path:\s*'\/submission\/:id'/)
    expect(source).toMatch(/\/groups\/\$\{to\.params\.id\}\/submission/)
  })
})

describe('the Finalist tab', () => {
  it('is only there for a finalist group', async () => {
    finalist.is = false
    const notFinalist = await mountAt('/groups/1', 'student')
    expect(notFinalist.wrapper.find('[data-testid="section-tab-finalist"]').exists()).toBe(false)

    finalist.is = true
    const { wrapper } = await mountAt('/groups/1', 'student')
    const tabs = wrapper.findAll('nav.group-sections button').map((b) => b.text())
    expect(tabs).toEqual(['Tasks and Chat', 'Submission', 'Finalist'])
    finalist.is = false
  })

  it('opens the finalist round on its own route', async () => {
    finalist.is = true
    const { wrapper, router } = await mountAt('/groups/1', 'mentor')

    await wrapper.find('[data-testid="section-tab-finalist"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('group-finalist')
    expect(wrapper.find('[data-testid="finalist-stub"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="section-tab-finalist"]').classes()).toContain('active')
    finalist.is = false
  })
})

describe('the Results tab', () => {
  const release = (fields: Record<string, unknown>) => {
    results.current = { ...results.current, ...fields }
  }

  it('stays hidden until marks or certificates are released', async () => {
    release({ marks_released: false, certificates_released: false })
    const { wrapper } = await mountAt('/groups/1', 'student')

    expect(wrapper.find('[data-testid="section-tab-results"]').exists()).toBe(false)
  })

  it.each([
    ['marks', { marks_released: true, certificates_released: false }],
    ['certificates', { marks_released: false, certificates_released: true }]
  ])('shows after Submission once %s are released', async (_what, fields) => {
    release(fields)
    const { wrapper } = await mountAt('/groups/1', 'mentor')

    const tabs = wrapper.findAll('nav.group-sections button').map((b) => b.text())
    expect(tabs).toEqual(['Tasks and Chat', 'Submission', 'Results'])
  })

  it('comes after Finalist for a finalist group', async () => {
    release({ marks_released: true })
    finalist.is = true
    const { wrapper } = await mountAt('/groups/1', 'student')

    const tabs = wrapper.findAll('nav.group-sections button').map((b) => b.text())
    expect(tabs).toEqual(['Tasks and Chat', 'Submission', 'Finalist', 'Results'])
    finalist.is = false
  })

  it('opens the results on its own route', async () => {
    release({ marks_released: true })
    const { wrapper, router } = await mountAt('/groups/1', 'student')

    await wrapper.find('[data-testid="section-tab-results"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('group-results')
    expect(wrapper.find('[data-testid="results-stub"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="section-tab-results"]').classes()).toContain('active')
  })

  it('falls back to tasks on the results route while nothing is released', async () => {
    release({ marks_released: false, certificates_released: false })
    const { wrapper } = await mountAt('/groups/1/results', 'student')

    expect(wrapper.find('[data-testid="results-stub"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="section-tab-tasks"]').classes()).toContain('active')
  })
})

describe('who is offered the Submission tab', () => {
  it.each(['student', 'mentor', 'supervisor', 'admin'])('offers it to a %s', async (role) => {
    const { wrapper } = await mountAt('/groups/1', role)

    expect(wrapper.find('[data-testid="section-tab-tasks"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="section-tab-submission"]').exists()).toBe(true)
  })

  it.each(['mentor', 'supervisor'])('opens the portal for a %s on the submission URL', async (role) => {
    const { wrapper } = await mountAt('/groups/1/submission', role)

    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(true)
  })

  it('opens the portal for an admin on the submission URL, to edit for the team', async () => {
    const { wrapper } = await mountAt('/groups/1/submission', 'admin')

    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(true)
  })
})

describe('switching between the sections', () => {
  it('shows the host page content and no portal on the group route', async () => {
    const { wrapper } = await mountAt('/groups/1', 'student')

    expect(wrapper.find('[data-testid="section-body-tasks"]').classes()).not.toContain('is-hidden')
    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(false)
  })

  it('mounts the portal and hides the host content on the submission route', async () => {
    const { wrapper } = await mountAt('/groups/1/submission', 'student')

    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="section-body-tasks"]').classes()).toContain('is-hidden')
  })

  it('hides the host content rather than destroying it', async () => {
    const { wrapper } = await mountAt('/groups/1/submission', 'student')

    expect(wrapper.find('[data-testid="host-content"]').exists()).toBe(true)
  })

  it('keeps the portal mounted after leaving, so returning does not refetch', async () => {
    const { wrapper } = await mountAt('/groups/1/submission', 'student')
    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(true)

    await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
    await flushPromises()

    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="section-body-submission"]').isVisible()).toBe(false)
  })

  it('lands on the group page route', async () => {
    const { wrapper, router } = await mountAt('/groups/1', 'student')

    await wrapper.find('[data-testid="section-tab-submission"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/groups/1/submission')
    expect(router.currentRoute.value.name).toBe('group-submission')
  })

  it('forwards the old emailed link to the tab', async () => {
    const { router } = await mountAt('/submission/1', 'student')

    expect(router.currentRoute.value.fullPath).toBe('/groups/1/submission')
  })

  it('goes back to the group route from the Tasks tab', async () => {
    const { wrapper, router } = await mountAt('/groups/1/submission', 'student')

    await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/groups/1')
  })

  it('keeps the group id when switching', async () => {
    const { wrapper, router } = await mountAt('/groups/42', 'student')

    await wrapper.find('[data-testid="section-tab-submission"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/groups/42/submission')
  })
})

describe('the Plan tab', () => {
  const stage = { id: 1, name: 'Getting started', description: '', position: 0 }
  const planWith = (...names: string[]) => ({
    year: 2026,
    stages: [stage],
    items: names.map((name, i) => ({
      id: i + 1, stage_id: 1, position: i, name, description: '', resource_url: '', resource_label: '',
      due_date: null, audience_role: 'student', completion_mode: 'per_person', completed: false, can_toggle: true,
    })),
  })
  const emptyPlan = { year: 2026, stages: [], items: [] }
  const tabs = (wrapper: { findAll: (s: string) => { text: () => string }[] }) =>
    wrapper.findAll('nav.group-sections button').map((b) => b.text())
  const apiError = (status: number) =>
    new ApiError({ error: 'Nope', code: 'x', request_id: 'r' }, status)

  /** Hand each request a promise the test settles, recording the group asked for. */
  const controlled = () => {
    const pending: Record<string, { resolve: (v: unknown) => void; reject: (e: unknown) => void }> = {}
    planApi.list.mockImplementation(
      (groupId: string) => new Promise((resolve, reject) => { pending[groupId] = { resolve, reject } }),
    )
    return pending
  }

  beforeEach(() => {
    planApi.list.mockReset()
    planApi.list.mockImplementation(async () => emptyPlan)
  })

  it('is shown, after Tasks and Chat, when the plan has tasks', async () => {
    planApi.list.mockResolvedValue(planWith('Introduce yourself'))
    const { wrapper } = await mountAt('/groups/1', 'student')
    expect(tabs(wrapper)).toEqual(['Tasks and Chat', 'Plan', 'Submission'])
    expect(planApi.list).toHaveBeenCalledWith('1')
  })

  it('is hidden for an empty plan, without any error', async () => {
    const { wrapper } = await mountAt('/groups/1', 'student')
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="section-plan-retry"]').exists()).toBe(false)
  })

  it.each([404, 403])('is hidden, without an error, when the plan answers %i', async (status) => {
    planApi.list.mockRejectedValue(apiError(status))
    const { wrapper } = await mountAt('/groups/1', 'student')
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="section-plan-retry"]').exists()).toBe(false)
  })

  it('opens the plan on its own route with the group, stages and tasks', async () => {
    planApi.list.mockResolvedValue(planWith('Introduce yourself', 'Agree a time'))
    const { wrapper, router } = await mountAt('/groups/1', 'mentor')

    await wrapper.find('[data-testid="section-tab-plan"]').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/groups/1/plan')
    expect(wrapper.find('[data-testid="section-tab-plan"]').classes()).toContain('active')
    expect(wrapper.find('[data-testid="section-body-tasks"]').classes()).toContain('is-hidden')
    const stub = wrapper.findComponent({ name: 'GroupPlanSectionStub' })
    expect(stub.props('groupId')).toBe('1')
    expect(stub.props('stages')).toEqual([stage])
    expect(stub.props('items')).toEqual(planWith('Introduce yourself', 'Agree a time').items)
  })

  it('opens directly on the plan URL, with one request', async () => {
    planApi.list.mockResolvedValue(planWith('Introduce yourself'))
    const { wrapper } = await mountAt('/groups/1/plan', 'student')
    expect(wrapper.find('[data-testid="plan-stub"]').text()).toBe('1:Introduce yourself')
    expect(planApi.list).toHaveBeenCalledTimes(1)
  })

  it('shows loading on the plan URL, not Tasks and Chat, until the plan arrives', async () => {
    const pending = controlled()
    const { wrapper } = await mountAt('/groups/1/plan', 'student')
    expect(wrapper.find('[data-testid="section-body-plan"]').text()).toContain('Loading the plan')
    expect(wrapper.find('[data-testid="section-body-tasks"]').classes()).toContain('is-hidden')

    pending['1'].resolve(planWith('Introduce yourself'))
    await flushPromises()
    expect(wrapper.find('[data-testid="plan-stub"]').exists()).toBe(true)
  })

  it.each([
    ['an empty plan', () => Promise.resolve(emptyPlan)],
    ['a hidden plan', () => Promise.reject(apiError(404))],
  ])('leaves the plan URL for the group page with %s', async (_label, answer) => {
    planApi.list.mockImplementation(answer)
    const { wrapper, router } = await mountAt('/groups/1/plan', 'student')
    expect(router.currentRoute.value.fullPath).toBe('/groups/1')
    expect(wrapper.find('[data-testid="section-tab-tasks"]').classes()).toContain('active')
    expect(wrapper.find('[data-testid="section-body-plan"]').exists()).toBe(false)
  })

  it('clears the previous group’s plan at once on switching group', async () => {
    const pending = controlled()
    const { wrapper, router } = await mountAt('/groups/1', 'student')
    pending['1'].resolve(planWith('Group one task'))
    await flushPromises()
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(true)

    await router.push('/groups/2')
    await wrapper.vm.$nextTick()
    // Group 2's plan hasn't answered: nothing of group 1's remains.
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)
    expect(planApi.list).toHaveBeenLastCalledWith('2')
  })

  it('ignores a late answer for the previous group', async () => {
    const pending = controlled()
    const { wrapper, router } = await mountAt('/groups/1/plan', 'student')
    await router.push('/groups/2/plan')
    await flushPromises()

    // Group 2 answers first, then group 1's stale answer arrives.
    pending['2'].resolve(planWith('Group two task'))
    await flushPromises()
    pending['1'].resolve(planWith('Group one task'))
    await flushPromises()

    expect(wrapper.find('[data-testid="plan-stub"]').text()).toBe('2:Group two task')
  })

  it('does not let a late answer for the previous group open a Plan tab', async () => {
    const pending = controlled()
    const { wrapper, router } = await mountAt('/groups/1', 'student')
    await router.push('/groups/2')
    await flushPromises()

    pending['1'].resolve(planWith('Group one task'))
    await flushPromises()
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)

    pending['2'].resolve(emptyPlan)
    await flushPromises()
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)
  })

  it('offers a retry for a failed load, and retries only the plan', async () => {
    planApi.list.mockRejectedValueOnce(new Error('Network down'))
    const { wrapper } = await mountAt('/groups/1', 'student')

    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)
    const retry = wrapper.find('[data-testid="section-plan-retry"]')
    expect(retry.exists()).toBe(true)
    // The rest of the page is still there.
    expect(wrapper.find('[data-testid="section-tab-submission"]').exists()).toBe(true)

    planApi.list.mockResolvedValueOnce(planWith('Introduce yourself'))
    await retry.trigger('click')
    await flushPromises()
    expect(planApi.list).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="section-plan-retry"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(true)
  })

  it('shows the error and a retry on the plan URL, and stays there', async () => {
    planApi.list.mockRejectedValueOnce(new Error('Network down'))
    const { wrapper, router } = await mountAt('/groups/1/plan', 'student')
    expect(router.currentRoute.value.fullPath).toBe('/groups/1/plan')
    const body = wrapper.find('[data-testid="section-body-plan"]')
    expect(body.find('[role="alert"]').text()).toContain("The plan couldn't be loaded.")

    planApi.list.mockResolvedValueOnce(planWith('Introduce yourself'))
    await body.find('button').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="plan-stub"]').exists()).toBe(true)
  })

  it('reloads when coming back to the plan from another section', async () => {
    planApi.list.mockResolvedValue(planWith('Introduce yourself'))
    const { wrapper } = await mountAt('/groups/1/plan', 'student')
    await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
    await flushPromises()
    expect(planApi.list).toHaveBeenCalledTimes(1)

    planApi.list.mockResolvedValue(planWith('Introduce yourself', 'New task from admin'))
    await wrapper.find('[data-testid="section-tab-plan"]').trigger('click')
    await flushPromises()
    expect(planApi.list).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="plan-stub"]').text()).toBe('1:Introduce yourself,New task from admin')
  })

  describe('a saved tick', () => {
    type Mounted = Awaited<ReturnType<typeof mountAt>>['wrapper']
    const stub = (wrapper: Mounted) => wrapper.findComponent({ name: 'GroupPlanSectionStub' })
    const ticked = () => ({ ...planWith('Introduce yourself', 'Agree a time').items[0], completed: true })
    const completions = (wrapper: Mounted) =>
      (stub(wrapper).props('items') as { completed: boolean }[]).map((item) => item.completed)

    it('is not undone by a reload that started before it and answers after', async () => {
      planApi.list.mockResolvedValue(planWith('Introduce yourself', 'Agree a time'))
      const { wrapper } = await mountAt('/groups/1/plan', 'student')
      await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
      await flushPromises()

      // 1. Coming back to Plan starts a reload, which the test holds.
      const pending = controlled()
      await wrapper.find('[data-testid="section-tab-plan"]').trigger('click')
      await flushPromises()
      expect(planApi.list).toHaveBeenCalledTimes(2)

      // 2. The viewer ticks a task and the server saves it.
      stub(wrapper).vm.$emit('taskUpdated', '1', ticked())
      await flushPromises()
      expect(completions(wrapper)).toEqual([true, false])

      // 3. The reload answers with what it read before the tick.
      pending['1'].resolve(planWith('Introduce yourself', 'Agree a time'))
      await flushPromises()

      // 4. The saved tick still shows, and nothing was asked again.
      expect(completions(wrapper)).toEqual([true, false])
      expect(planApi.list).toHaveBeenCalledTimes(2)
      expect(wrapper.find('[data-testid="section-tab-plan"]').classes()).toContain('active')
    })

    it('is kept by the page, so coming back to Plan shows it before the reload answers', async () => {
      planApi.list.mockResolvedValue(planWith('Introduce yourself', 'Agree a time'))
      const { wrapper } = await mountAt('/groups/1/plan', 'student')
      stub(wrapper).vm.$emit('taskUpdated', '1', ticked())
      await flushPromises()

      await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
      await flushPromises()
      const pending = controlled()
      await wrapper.find('[data-testid="section-tab-plan"]').trigger('click')
      await flushPromises()

      // The reload hasn't answered: the tick shows, not the first load's value.
      expect(completions(wrapper)).toEqual([true, false])

      pending['1'].resolve({
        ...planWith('Introduce yourself', 'Agree a time'),
        items: [ticked(), planWith('Introduce yourself', 'Agree a time').items[1]],
      })
      await flushPromises()
      expect(completions(wrapper)).toEqual([true, false])
    })

    it('is ignored when it was saved for another group', async () => {
      planApi.list.mockResolvedValue(planWith('Introduce yourself', 'Agree a time'))
      const { wrapper } = await mountAt('/groups/1/plan', 'student')
      // Task ids are shared by every group's plan; only group 1's tick counts here.
      stub(wrapper).vm.$emit('taskUpdated', '2', ticked())
      await flushPromises()
      expect(completions(wrapper)).toEqual([false, false])
    })

    it('still lets a reload that starts after it land', async () => {
      planApi.list.mockResolvedValue(planWith('Introduce yourself', 'Agree a time'))
      const { wrapper } = await mountAt('/groups/1/plan', 'student')
      stub(wrapper).vm.$emit('taskUpdated', '1', ticked())
      await flushPromises()

      await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
      await flushPromises()
      // The server's newer answer (here, the tick since undone elsewhere) wins.
      planApi.list.mockResolvedValue(planWith('Introduce yourself', 'Agree a time', 'New task from admin'))
      await wrapper.find('[data-testid="section-tab-plan"]').trigger('click')
      await flushPromises()
      expect(completions(wrapper)).toEqual([false, false, false])
    })
  })

  describe('a reload that fails', () => {
    type Mounted = Awaited<ReturnType<typeof mountAt>>['wrapper']
    const stub = (wrapper: Mounted) => wrapper.findComponent({ name: 'GroupPlanSectionStub' })
    const loaded = () => planWith('Introduce yourself', 'Agree a time')
    const ticked = () => ({ ...loaded().items[0], completed: true })

    /** A plan on screen with a saved tick, then a revisit whose reload the test holds. */
    const revisitWithPendingReload = async () => {
      planApi.list.mockResolvedValue(loaded())
      const { wrapper, router } = await mountAt('/groups/1/plan', 'student')
      stub(wrapper).vm.$emit('taskUpdated', '1', ticked())
      await flushPromises()
      await wrapper.find('[data-testid="section-tab-tasks"]').trigger('click')
      await flushPromises()

      const pending = controlled()
      await wrapper.find('[data-testid="section-tab-plan"]').trigger('click')
      await flushPromises()
      expect(planApi.list).toHaveBeenCalledTimes(2)
      return { wrapper, router, pending }
    }

    it.each([
      ['a network error', () => new Error('Network down')],
      ['a server error', () => apiError(500)],
    ])('keeps the plan already on screen after %s', async (_label, failure) => {
      const { wrapper, router, pending } = await revisitWithPendingReload()

      pending['1'].reject(failure())
      await flushPromises()

      // Same tasks and ticks, still open and usable; no error view or retry pill.
      expect(stub(wrapper).props('items')).toEqual([ticked(), loaded().items[1]])
      expect(router.currentRoute.value.fullPath).toBe('/groups/1/plan')
      expect(wrapper.find('[data-testid="section-tab-plan"]').classes()).toContain('active')
      expect(wrapper.find('[data-testid="section-body-plan"] [role="alert"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="section-plan-retry"]').exists()).toBe(false)
      expect(planApi.list).toHaveBeenCalledTimes(2)

      // A tick saved afterwards still lands.
      stub(wrapper).vm.$emit('taskUpdated', '1', { ...loaded().items[1], completed: true })
      await flushPromises()
      expect((stub(wrapper).props('items') as { completed: boolean }[]).map((i) => i.completed)).toEqual([true, true])
    })

    it.each([404, 403])('still leaves the plan when the reload answers %i', async (status) => {
      const { wrapper, router, pending } = await revisitWithPendingReload()

      pending['1'].reject(apiError(status))
      await flushPromises()

      expect(router.currentRoute.value.fullPath).toBe('/groups/1')
      expect(wrapper.find('[data-testid="section-tab-plan"]').exists()).toBe(false)
      expect(wrapper.find('[data-testid="section-body-plan"]').exists()).toBe(false)
    })
  })

  it('keeps the other tabs working alongside it', async () => {
    planApi.list.mockResolvedValue(planWith('Introduce yourself'))
    const { wrapper, router } = await mountAt('/groups/1/plan', 'student')
    await wrapper.find('[data-testid="section-tab-submission"]').trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.fullPath).toBe('/groups/1/submission')
    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(true)
    // Hidden, not destroyed, so a tick still saving can land.
    expect(wrapper.find('[data-testid="section-body-plan"]').isVisible()).toBe(false)
    expect(wrapper.find('[data-testid="plan-stub"]').exists()).toBe(true)
  })
})
