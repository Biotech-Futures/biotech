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
      due_date: '2026-10-01',
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
    {
      id: 11,
      name: 'BTF11',
      cells: { '11': { completed: 3, total: 3 }, '12': { completed: 1, total: 1 } },
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

const rows = (page: VueWrapper) => page.findAll('tbody tr.data-table-row')
// A row's own cells, without the table's expand-button cell.
const cells = (page: VueWrapper, index: number) =>
  rows(page)[index].findAll('td:not(.data-table-expand-col)').map((cell) => cell.text())
const names = (page: VueWrapper) => rows(page).map((row) => row.find('td:not(.data-table-expand-col)').text())
const buttonByText = (page: VueWrapper, text: string) =>
  page.findAll('button').find((button) => button.text().trim() === text)!

beforeEach(() => {
  // Only the clock is faked, so promises and timers still run normally.
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-10-22T12:00:00'))
  fetchProgress.mockReset().mockResolvedValue(fixture())
})
afterEach(() => {
  wrapper?.unmount()
  wrapper = undefined
  vi.useRealTimers()
})

describe('admin plan progress', () => {
  it('leads with cohort health: groups behind, overdue tasks and overall completion', async () => {
    const page = await mountPage()
    expect(page.text()).toContain('2026 cohort · as of 22/10/26')
    const health = page.get('[aria-label="Cohort health"]').text()
    expect(health).toContain('1 of 3 groups have overdue tasks')
    expect(health).toContain('2 on track')
    expect(health).toContain('1 behind · 1 overdue task in total')
    // (1 + 0 + 2) done of (2 + 1 + 2) applicable; 0/0 cells are left out.
    expect(health).toContain('60% of all applicable tasks done')
    expect(page.text()).not.toMatch(/NaN|Infinity/)
  })

  it('lists behind groups first, then natural order, with status, progress and what needs doing', async () => {
    const page = await mountPage()
    expect(names(page)).toEqual(['BTF2', 'BTF10', 'BTF11'])
    expect(cells(page, 0)).toEqual([
      'BTF2',
      '1 overdue',
      '1 of 2 tasks',
      'Oldest overdue: Introduce yourself (due 01/10/26)',
    ])
    expect(cells(page, 1)).toEqual(['BTF10', 'On track', '0 of 1 tasks', 'Next: Agree a meeting time · due 05/11/26'])
    expect(cells(page, 2)).toEqual(['BTF11', 'All done', '2 of 2 tasks', 'All tasks done'])
    expect(page.find('a[href="/groups/2"]').exists()).toBe(true)
    expect(page.get('a[href="/admin/plan"]').text()).toBe('Back to plan builder')
  })

  it('opens a group to show its tasks by stage, with overdue, done and 0/0 states', async () => {
    const page = await mountPage()
    await rows(page)[0].get('.data-table-expand-btn').trigger('click')
    const detail = page.get('tr.data-table-detail-row').text()
    expect(detail).toContain('Getting started')
    expect(detail).toContain('Introduce yourself')
    expect(detail).toContain('2/3 · was due 01/10/26')
    expect(detail).toContain('Project work')
    expect(detail).toContain('done')
    expect(page.find('tr.data-table-detail-row .plan-progress__item--overdue .fa-clock').exists()).toBe(true)
    expect(page.find('tr.data-table-detail-row .plan-progress__item--done .fa-check').exists()).toBe(true)

    await rows(page)[1].get('.data-table-expand-btn').trigger('click')
    expect(page.findAll('tr.data-table-detail-row')[1].text()).toContain('nobody to tick')
  })

  it('shows a group with nobody in any audience as having nothing to tick', async () => {
    const data = fixture()
    data.groups[1].cells['12'] = { completed: 0, total: 0 }
    fetchProgress.mockResolvedValue(data)
    const page = await mountPage()
    expect(cells(page, 1).slice(0, 3)).toEqual(['BTF10', 'Nothing to tick', '0 of 0 tasks'])
    expect(page.text()).not.toMatch(/NaN|Infinity/)
  })

  it('filters to behind or on-track groups', async () => {
    const page = await mountPage()
    await buttonByText(page, 'Behind 1').trigger('click')
    expect(names(page)).toEqual(['BTF2'])
    await buttonByText(page, 'On track 2').trigger('click')
    expect(names(page)).toEqual(['BTF10', 'BTF11'])
    await buttonByText(page, 'All 3').trigger('click')
    expect(names(page)).toHaveLength(3)
  })

  it('filters by group name only, without matching task names or statuses', async () => {
    const page = await mountPage()
    const search = page.get('input[type="search"]')
    await search.setValue('btf10')
    expect(names(page)).toEqual(['BTF10'])
    for (const text of ['Introduce yourself', 'overdue', 'missing']) {
      await search.setValue(text)
      expect(rows(page)).toHaveLength(0)
      expect(page.text()).toContain('No groups match.')
    }
    await search.setValue('')
    expect(rows(page)).toHaveLength(3)
    expect(fetchProgress).toHaveBeenCalledOnce()
  })

  it('shows each task once by task, with groups done and groups overdue', async () => {
    const page = await mountPage()
    await buttonByText(page, 'By task').trigger('click')
    expect(page.findAll('th').map((head) => head.text())).toEqual([
      'Task',
      'Stage',
      'Due',
      'Groups done',
      'Overdue',
    ])
    expect(cells(page, 0)).toEqual([
      'Introduce yourself Students · each person',
      'Getting started',
      '01/10/26',
      '1 of 2 groups',
      '1 group overdue',
    ])
    expect(cells(page, 1)).toEqual([
      'Agree a meeting time Mentors · one tick per group',
      'Project work',
      '05/11/26',
      '2 of 3 groups',
      'Not due yet',
    ])
    expect(rows(page)[1].find('.fa-users').exists()).toBe(true)
    await buttonByText(page, 'By group').trigger('click')
    expect(names(page)).toEqual(['BTF2', 'BTF10', 'BTF11'])
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
    expect(page.find('[aria-label="Cohort health"]').exists()).toBe(false)
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
    expect(buttonByText(page, 'Refresh progress').attributes('disabled')).toBeDefined()
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
    const refresh = buttonByText(page, 'Refresh progress')
    await refresh.trigger('click')
    await flushPromises()
    expect(page.get('[aria-label="Cohort health"]').text()).toContain('0 of 3 groups have overdue tasks')
    expect(cells(page, 0).slice(0, 2)).toEqual(['BTF2', 'All done'])
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
    expect(page.findComponent(AppDataTable).props('rows')).toHaveLength(250)
    expect(rows(page).length).toBeLessThan(250)
    expect(page.get('[aria-label="Cohort health"]').text()).toContain('250 of 250 groups have overdue tasks')
    await page.get('input[type="search"]').setValue('BTF250')
    expect(names(page)).toEqual(['BTF250'])
  })
})
