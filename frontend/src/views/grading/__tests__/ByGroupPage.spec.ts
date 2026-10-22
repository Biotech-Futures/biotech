import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, computed } from 'vue'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ByGroupPage from '@/views/grading/ByGroupPage.vue'
import { fetchComponentRows } from '@/utils/gradingAPI'
import { useJobPolling } from '@/composables/useJobPolling'

vi.mock('@/utils/gradingAPI', () => ({
  fetchComponentRows: vi.fn()
}))
const rowsMock = vi.mocked(fetchComponentRows)

const pushMock = vi.fn()
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock })
}))

const jobState = vi.hoisted(() => ({
  phase: { value: 'idle' as string },
  error: { value: '' },
  startAll: undefined as unknown
}))
vi.mock('@/composables/useJobPolling', () => ({
  useJobPolling: vi.fn()
}))
const jobMock = vi.mocked(useJobPolling)

const componentRow = (over: Record<string, unknown> = {}) => ({
  group_id: 1,
  group_name: 'BTF-1',
  submission_id: 11,
  submitted_at: '2026-09-01T10:00:00Z',
  is_late: false,
  late_by: null,
  criteria_graded: 0,
  marks_total: null,
  last_grader_name: null,
  grader_names: [],
  criterion_markers: [],
  ...over
})

const payload = (code: string, criteriaTotal: number, rows: unknown[]) => ({
  component: { id: 1, code, name: code, is_optional: false, accepts_file: true, accepts_text: false, accepts_link: false, order: 1 },
  year: 2026,
  criteria_total: criteriaTotal,
  rows
})

const mountPage = async () => {
  const wrapper = mount(ByGroupPage, {
    global: {
      stubs: {
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
      }
    }
  })
  await flushPromises()
  return wrapper
}

// The table's group rows, its search box, and typing into it.
const bodyRows = (wrapper: VueWrapper) => wrapper.findAll('tbody tr.data-table-row')
const searchBox = (wrapper: VueWrapper) => wrapper.find('.data-table-search-input')
const search = async (wrapper: VueWrapper, text: string) => {
  await searchBox(wrapper).setValue(text)
  await flushPromises()
}

beforeEach(() => {
  rowsMock.mockReset()
  pushMock.mockReset()
  jobState.phase = ref('idle') as never
  jobState.error = ref('') as never
  const startAll = vi.fn()
  jobState.startAll = startAll
  jobMock.mockReturnValue({
    phase: jobState.phase as never,
    error: jobState.error as never,
    isBusy: computed(() => false),
    start: vi.fn(),
    startAll
  } as never)

  // SAQ carries the graded work; the other three components 404-free but empty.
  rowsMock.mockImplementation(async (code: string) => {
    if (code === 'SAQ') {
      return payload('SAQ', 2, [
        componentRow({
          criteria_graded: 2,
          grader_names: ['Ada Grader'],
          criterion_markers: [{ n: 1, marker: 'Ada Grader' }]
        }),
        componentRow({
          group_id: 2,
          group_name: 'BTF-2',
          submission_id: null,
          submitted_at: null
        }),
        componentRow({
          group_id: 3,
          group_name: 'Alpha Team',
          submission_id: 13,
          submitted_at: '2026-09-02T09:00:00Z',
          is_late: true,
          late_by: '3h 12m',
          criteria_graded: 1,
          last_grader_name: 'Bob Marker'
        })
      ]) as never
    }
    if (code === 'POSTER') {
      return payload('POSTER', 1, [
        componentRow({ criteria_graded: 1, grader_names: ['Bob Marker'] })
      ]) as never
    }
    throw new Error(`no rubric for ${code}`)
  })
})

describe('the aggregated group table', () => {
  it('merges every component into one row per group with combined progress', async () => {
    const wrapper = await mountPage()
    const row = bodyRows(wrapper).find((r) => r.text().includes('BTF-1'))!
    // 2 SAQ + 1 POSTER graded of 3 criteria across the components that loaded.
    expect(row.text()).toContain('3/3')
    expect(row.find('.by-group__done').exists()).toBe(true)
  })

  it("counts only the components a team submitted towards its progress total", async () => {
    // Every component has criteria (4 SAQ, 10 poster, 13 report, 5 prototype
    // = 32); BTF-1 submitted SAQ and poster only, Alpha Team a poster only.
    const totals: Record<string, number> = { SAQ: 4, POSTER: 10, REPORT: 13, PROTOTYPE: 5 }
    rowsMock.mockImplementation(async (code: string) =>
      payload(code, totals[code]!, [
        componentRow({
          submission_id: code === 'SAQ' || code === 'POSTER' ? 11 : null,
          criteria_graded: code === 'SAQ' ? 4 : code === 'POSTER' ? 3 : 0
        }),
        componentRow({
          group_id: 3,
          group_name: 'Alpha Team',
          submission_id: code === 'POSTER' ? 13 : null,
          submitted_at: code === 'POSTER' ? '2026-09-02T09:00:00Z' : null,
          criteria_graded: code === 'POSTER' ? 10 : 0
        })
      ]) as never
    )
    const wrapper = await mountPage()
    const rowNamed = (name: string) =>
      bodyRows(wrapper).find((r) => r.text().includes(name))!

    expect(rowNamed('BTF-1').text()).toContain('7/14') // not 7/32
    // No SAQ answers, but the poster is in: submitted, fully marked, openable.
    const alpha = rowNamed('Alpha Team')
    expect(alpha.text()).toContain('10/10')
    expect(alpha.find('.by-group__done').exists()).toBe(true)
    expect(alpha.find('a').attributes('href')).toBe('/grading/groups/3')
  })

  it('keeps rendering when some components have no rubric yet', async () => {
    const wrapper = await mountPage()
    // REPORT and PROTOTYPE threw — the table still shows all three groups.
    expect(bodyRows(wrapper)).toHaveLength(3)
  })

  it('reports the cohort stats above the table', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.by-group__stats').text()).toContain('2/3 Submitted')
    expect(wrapper.find('.by-group__stats').text()).toContain('1/2 Fully Marked')
  })

  it('shows lateness by its label and dashes for unsubmitted rows', async () => {
    const wrapper = await mountPage()
    const alphaRow = bodyRows(wrapper).find((r) => r.text().includes('Alpha Team'))!
    expect(alphaRow.find('.by-group__late').text()).toBe('3h 12m')
    const unsubmitted = bodyRows(wrapper).find((r) => r.text().includes('BTF-2'))!
    expect(unsubmitted.text()).toContain('No sub.')
    expect(unsubmitted.find('a').exists()).toBe(false)
  })

  it('names the first marker with a group icon when several marked, tooltip per part', async () => {
    const wrapper = await mountPage()
    const row = bodyRows(wrapper).find((r) => r.text().includes('BTF-1'))!
    const marker = row.find('.by-group__marker')
    expect(marker.text()).toContain('Ada Grader')
    expect(row.find('.by-group__marker-icon').exists()).toBe(true) // Ada + Bob
    expect(marker.attributes('title')).toContain('SAQ 1: Ada Grader')
  })

  it('links each submitted group to its marking page', async () => {
    const wrapper = await mountPage()
    const row = bodyRows(wrapper).find((r) => r.text().includes('BTF-1'))!
    expect(row.find('a').attributes('href')).toBe('/grading/groups/1')
  })

  it('reports a total failure instead of an empty table', async () => {
    rowsMock.mockRejectedValue(new Error('down'))
    const wrapper = await mountPage()
    expect(wrapper.find('.by-group__error').text()).toContain('Could not load the group list.')
    expect(wrapper.find('.data-table-empty').text()).toBe('No groups.')
  })
})

describe('search and sorting', () => {
  it('live-filters by name, and says when nothing matches', async () => {
    const wrapper = await mountPage()
    await search(wrapper, 'alpha')
    expect(bodyRows(wrapper)).toHaveLength(1)
    await search(wrapper, '999')
    expect(wrapper.find('.data-table-empty').text()).toBe('No groups match your search.')
  })

  it('defaults to newest submission first, with unsubmitted rows last', async () => {
    const wrapper = await mountPage()
    const names = bodyRows(wrapper).map((r) => r.findAll('td')[0]!.text())
    expect(names).toEqual(['Alpha Team', 'BTF-1', 'BTF-2'])
  })

  it('sorting by group name starts ascending and toggles', async () => {
    const wrapper = await mountPage()
    const groupSort = wrapper.findAll('.data-table-sort-btn').find((b) => b.text().includes('Group'))!
    await groupSort.trigger('click')
    let names = bodyRows(wrapper).map((r) => r.findAll('td')[0]!.text())
    expect(names).toEqual(['Alpha Team', 'BTF-1', 'BTF-2'])
    await groupSort.trigger('click')
    names = bodyRows(wrapper).map((r) => r.findAll('td')[0]!.text())
    expect(names).toEqual(['BTF-2', 'BTF-1', 'Alpha Team'])
  })

  it('exposes no group ids anywhere in the table', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('thead').text()).not.toContain('ID')
    expect(wrapper.find('tbody').text()).not.toMatch(/#\d/)
  })

  it('sorting by progress pins unsubmitted rows to the bottom either way', async () => {
    const wrapper = await mountPage()
    const progressSort = wrapper.findAll('.data-table-sort-btn').find((b) => b.text().includes('Progress'))!
    await progressSort.trigger('click')
    let names = bodyRows(wrapper).map((r) => r.findAll('td')[0]!.text())
    expect(names[names.length - 1]).toBe('BTF-2')
    await progressSort.trigger('click')
    names = bodyRows(wrapper).map((r) => r.findAll('td')[0]!.text())
    expect(names[names.length - 1]).toBe('BTF-2')
  })
})

describe('jumping to a group', () => {
  it('Enter in the search opens the one group it names', async () => {
    const wrapper = await mountPage()
    await search(wrapper, 'alpha')
    await searchBox(wrapper).trigger('keydown', { key: 'Enter' })
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/3')
  })

  it('an unresolvable query is told so instead of navigating', async () => {
    const wrapper = await mountPage()
    await search(wrapper, 'BTF') // BTF-1 and BTF-2: no single group
    await searchBox(wrapper).trigger('keydown', { key: 'Enter' })
    expect(wrapper.find('.by-group__error').text()).toBe('No group matches that name.')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('an exact name wins over longer names that contain it', async () => {
    rowsMock.mockImplementation(async (code: string) => {
      if (code !== 'SAQ') throw new Error(`no rubric for ${code}`)
      return payload('SAQ', 1, [
        componentRow(),
        componentRow({ group_id: 10, group_name: 'BTF-10' })
      ]) as never
    })
    const wrapper = await mountPage()
    await search(wrapper, 'btf-1')
    await searchBox(wrapper).trigger('keydown', { key: 'Enter' })
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/1')
  })
})

describe('the everything zip', () => {
  it('Download All starts the all-submissions job', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /Download All/.test(b.text()))!.trigger('click')
    expect(jobState.startAll).toHaveBeenCalled()
  })

  it('a failed job shows its error banner', async () => {
    ;(jobState.phase as { value: string }).value = 'failed'
    ;(jobState.error as { value: string }).value = 'disk full'
    const wrapper = await mountPage()
    expect(wrapper.find('.by-group__banner--error').text()).toBe('disk full')
  })
})
