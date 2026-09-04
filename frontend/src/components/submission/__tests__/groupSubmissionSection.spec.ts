import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * Behaviour tests for the group page's section switcher.
 *
 * Three things here are load-bearing and easy to break silently, so each has
 * its own spec: that mentors and supervisors are never offered the tab, that
 * the host page's own content is hidden rather than destroyed when the tab
 * changes, and that the Submission tab actually lands on the group page's own
 * route rather than the standalone portal.
 */

// The portal is a large component that fetches on mount. None of these specs
// are about what it renders, only about whether it is mounted at all.
//
// `__esModule` matters: defineAsyncComponent unwraps `.default` only from
// something it recognises as a module. Without it Vue passes the namespace
// object itself along as the component, and the first unknown property read
// off a mocked module throws.
vi.mock('@/views/GroupSubmissionPage.vue', () => ({
  __esModule: true,
  default: { name: 'GroupSubmissionPageStub', template: '<div data-testid="portal-stub" />' },
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

// Mirrors the real records, including the redirect that keeps already-delivered
// email links working.
const ROUTES: RouteRecordRaw[] = [
  { path: '/groups/:id', name: 'group-detail', component: Host },
  { path: '/groups/:id/submission', name: 'group-submission', component: Host },
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
  // The specs below declare their own routes, so they cannot notice a name
  // colliding in the application's actual table. This one can, and that is the
  // mistake worth guarding: vue-router does not warn on a duplicate name, it
  // deletes the earlier record, and the tab's path then matches nothing.
  //
  // Read as text rather than imported. Importing it would pull every view in
  // the application into the Vitest TypeScript project, which compiles with
  // Node's types rather than the DOM's — and two unrelated pages then fail to
  // typecheck on their timer declarations. Reading the source keeps this guard
  // from making the whole suite's typecheck depend on files we do not own.
  const source = readFileSync(resolve(process.cwd(), 'src/router/routes.ts'), 'utf8')
  const records = [...source.matchAll(/path:\s*'([^']*)',\s*name:\s*'([^']+)'/g)]
  const names = records.map(([, , name]) => name)

  it('found the route records it means to check', () => {
    // Guards the regex above: if the table is ever reformatted so these stop
    // matching, this fails loudly rather than leaving the checks below passing
    // over an empty list.
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
    // Both submission emails send students to '/#/submission/{group.id}', and
    // reminders already delivered cannot be changed. The path has to keep
    // resolving even though the page behind it is gone.
    expect(source).toMatch(/path:\s*'\/submission\/:id'/)
    expect(source).toMatch(/\/groups\/\$\{to\.params\.id\}\/submission/)
  })
})

describe('who is offered the Submission tab', () => {
  it('offers it to a student', async () => {
    const { wrapper } = await mountAt('/groups/1', 'student')

    expect(wrapper.find('[data-testid="section-tab-tasks"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="section-tab-submission"]').exists()).toBe(true)
  })

  it.each(['mentor', 'supervisor'])('hides the whole strip from a %s', async (role) => {
    // The server refuses them, so nothing leaks either way. A visible tab that
    // 403s is simply a dead end, and for these roles the page should look
    // exactly as it did before the tab existed.
    const { wrapper } = await mountAt('/groups/1', role)

    expect(wrapper.find('[data-testid="section-tab-submission"]').exists()).toBe(false)
    expect(wrapper.find('nav.group-sections').exists()).toBe(false)
    expect(wrapper.find('[data-testid="host-content"]').exists()).toBe(true)
  })

  it('shows a mentor the tasks view even on the submission URL', async () => {
    // Typed by hand, or followed from a student's link. Falling back to tasks
    // is friendlier than rendering an empty page.
    const { wrapper } = await mountAt('/groups/1/submission', 'mentor')

    expect(wrapper.find('[data-testid="portal-stub"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="section-body-tasks"]').classes()).not.toContain('is-hidden')
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
    // The group page keeps live task and chat state. A v-if here would tear it
    // down and rebuild it on every tab press.
    const { wrapper } = await mountAt('/groups/1/submission', 'student')

    expect(wrapper.find('[data-testid="host-content"]').exists()).toBe(true)
  })

  it('lands on the group page route', async () => {
    // The regression this pins: this route once shared its name with the old
    // standalone portal route, and registering the second deleted the first,
    // so pressing the tab navigated away to /submission/1 instead.
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
