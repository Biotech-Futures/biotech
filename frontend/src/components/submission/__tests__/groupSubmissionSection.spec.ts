import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'


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
