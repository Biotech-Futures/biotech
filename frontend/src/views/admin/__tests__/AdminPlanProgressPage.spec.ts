import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import AppDataTable from '@/components/AppDataTable.vue'
import AdminPlanProgressPage from '@/views/admin/AdminPlanProgressPage.vue'
import { fetchAdminPlanProgress, type AdminPlanProgress } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', () => ({ fetchAdminPlanProgress: vi.fn() }))
const fetchProgress = vi.mocked(fetchAdminPlanProgress)

const fixture = (): AdminPlanProgress => ({
  year: 2026,
  stages: [
    { id: 1, name: 'Getting started', description: '', position: 0 },
    { id: 2, name: 'Project work', description: '', position: 1 },
  ],
  tasks: [
    {
      id: 11,
      stage_id: 1,
      position: 0,
      name: 'Introduce yourself',
      audience_role: 'student',
      completion_mode: 'per_person',
      due_date: null,
    },
    {
      id: 12,
      stage_id: 2,
      position: 0,
      name: 'Agree a meeting time',
      audience_role: 'mentor',
      completion_mode: 'per_group',
      due_date: '2026-11-05',
    },
  ],
  groups: [
    {
      id: 2,
      name: 'BTF2',
      cells: { '11': { completed: 2, total: 3 }, '12': { completed: 1, total: 1 } },
    },
    {
      id: 10,
      name: 'BTF10',
      cells: { '11': { completed: 0, total: 0 }, '12': { completed: 0, total: 1 } },
    },
  ],
})

let wrapper: VueWrapper | undefined
async function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/admin/plan/progress', component: { template: '<div />' } },
      { path: '/admin/plan', component: { template: '<div />' } },
      { path: '/groups/:id', component: { template: '<div />' } },
    ],
  })
  await router.push('/admin/plan/progress')
  await router.isReady()
  wrapper = mount(AdminPlanProgressPage, { attachTo: document.body, global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  fetchProgress.mockReset().mockResolvedValue(fixture())
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
})

describe('admin plan progress', () => {
  it('shows the cohort, ordered stage/task headings, audiences and date-only due date', async () => {
    const page = await mountPage()
    expect(page.text()).toContain('2026 cohort')
    const headings = page.findAll('th').map((head) => head.text())
    expect(headings).toHaveLength(3)
    expect(headings[0]).toBe('Group')
    expect(headings[1]).toContain('Getting started')
    expect(headings[1]).toContain('Introduce yourself')
    expect(headings[1]).toContain('Students · Each person')
    expect(headings[2]).toContain('Project work')
    expect(headings[2]).toContain('Mentors · Whole group')
    expect(headings[2]).toContain('05/11/26')
  })

  it('preserves natural group order and renders raw counts including 0/0', async () => {
    const page = await mountPage()
    const rows = page.findAll('tbody tr.data-table-row')
    expect(rows.map((row) => row.find('td').text())).toEqual(['BTF2', 'BTF10'])
    expect(rows[0].findAll('td').map((cell) => cell.text())).toEqual(['BTF2', '2/3', '1/1'])
    expect(rows[1].findAll('td').map((cell) => cell.text())).toEqual(['BTF10', '0/0', '0/1'])
    expect(page.text()).not.toMatch(/NaN|Infinity/)
    expect(page.find('a[href="/groups/2"]').exists()).toBe(true)
    expect(page.get('a[href="/admin/plan"]').text()).toBe('Back to plan builder')
  })

  it('filters by group name only, without matching task names or cell counts', async () => {
    const page = await mountPage()
    const search = page.get('input[type="search"]')
    await search.setValue('btf10')
    expect(page.findAll('tbody tr.data-table-row').map((row) => row.text())).toHaveLength(1)
    expect(page.find('tbody').text()).toContain('BTF10')
    for (const text of ['Introduce yourself', '2/3', 'missing']) {
      await search.setValue(text)
      expect(page.findAll('tbody tr.data-table-row')).toHaveLength(0)
      expect(page.text()).toContain('No groups match this name.')
    }
    await search.setValue('')
    expect(page.findAll('tbody tr.data-table-row')).toHaveLength(2)
    expect(fetchProgress).toHaveBeenCalledOnce()
  })

  it.each(['tasks', 'groups'] as const)('shows an explicit empty state for no %s', async (key) => {
    const data = fixture()
    data[key] = []
    fetchProgress.mockResolvedValue(data)
    const page = await mountPage()
    expect(page.text()).toContain(
      key === 'tasks' ? 'No plan tasks yet.' : 'No groups in the 2026 cohort yet.',
    )
    expect(page.find('table').exists()).toBe(false)
  })

  it('shows loading, then the result', async () => {
    let finish!: (value: AdminPlanProgress) => void
    fetchProgress.mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const page = await mountPage()
    expect(page.get('[role="status"]').text()).toContain('Loading')
    expect(page.get('button').attributes('disabled')).toBeDefined()
    finish(fixture())
    await flushPromises()
    expect(page.find('[role="status"]').exists()).toBe(false)
    expect(page.find('table').exists()).toBe(true)
  })

  it('shows denied or failed requests as errors and supports retry', async () => {
    fetchProgress.mockRejectedValueOnce(new Error('You do not have admin privileges.'))
    const page = await mountPage()
    expect(page.get('[role="alert"]').text()).toContain('You do not have admin privileges.')
    expect(page.find('table').exists()).toBe(false)
    await page.get('[role="alert"] button').trigger('click')
    await flushPromises()
    expect(fetchProgress).toHaveBeenCalledTimes(2)
    expect(page.find('[role="alert"]').exists()).toBe(false)
    expect(page.find('table').exists()).toBe(true)
  })

  it('refreshes counts and removes cached data if access is subsequently denied', async () => {
    const page = await mountPage()
    const fresh = fixture()
    fresh.groups[0].cells['11'].completed = 3
    fetchProgress.mockResolvedValueOnce(fresh)
    const refresh = page.findAll('button').find((button) => button.text() === 'Refresh progress')!
    await refresh.trigger('click')
    await flushPromises()
    expect(page.find('tbody').text()).toContain('3/3')
    fetchProgress.mockRejectedValueOnce(new Error('Access denied'))
    await refresh.trigger('click')
    await flushPromises()
    expect(page.find('table').exists()).toBe(false)
    expect(page.get('[role="alert"]').text()).toContain('Access denied')
  })

  it('handles 250 groups by 60 tasks with paged rendering and group filtering', async () => {
    const data = fixture()
    data.tasks = Array.from({ length: 60 }, (_, index) => ({
      ...data.tasks[0],
      id: index + 1,
      name: `Task ${index + 1}`,
    }))
    data.groups = Array.from({ length: 250 }, (_, index) => ({
      id: index + 1,
      name: `BTF${index + 1}`,
      cells: Object.fromEntries(
        data.tasks.map((task) => [String(task.id), { completed: 1, total: 2 }]),
      ),
    }))
    fetchProgress.mockResolvedValueOnce(data)
    const page = await mountPage()
    expect(page.findAll('th')).toHaveLength(61)
    expect(page.findComponent(AppDataTable).props('rows')).toHaveLength(250)
    expect(page.findAll('tbody tr.data-table-row').length).toBeLessThan(250)
    await page.get('input[type="search"]').setValue('BTF250')
    expect(page.findAll('tbody tr.data-table-row')).toHaveLength(1)
    expect(page.find('tbody').text()).toContain('BTF250')
  })
})
