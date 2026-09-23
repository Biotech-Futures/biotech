import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref, computed } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
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

const resolveIdMock = vi.fn<() => number | null>()
const GroupSearchInputStub = defineComponent({
  name: 'GroupSearchInput',
  props: { modelValue: { type: String, default: '' }, showSuggestions: { type: Boolean, default: true } },
  emits: ['update:modelValue', 'select'],
  methods: {
    resolveId(): number | null {
      return resolveIdMock()
    }
  },
  template:
    '<input class="picker" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
})

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
        GroupSearchInput: GroupSearchInputStub,
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
      }
    }
  })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  rowsMock.mockReset()
  pushMock.mockReset()
  resolveIdMock.mockReset()
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
    const row = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-1'))!
    // 2 SAQ + 1 POSTER graded of 3 criteria across the components that loaded.
    expect(row.text()).toContain('3/3')
    expect(row.find('.by-group__done').exists()).toBe(true)
  })

  it('keeps rendering when some components have no rubric yet', async () => {
    const wrapper = await mountPage()
    // REPORT and PROTOTYPE threw — the table still shows all three groups.
    expect(wrapper.findAll('tbody tr')).toHaveLength(3)
  })

  it('reports the cohort stats above the table', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.by-group__stats').text()).toContain('2/3 Submitted')
    expect(wrapper.find('.by-group__stats').text()).toContain('1/2 Fully Marked')
  })

  it('shows lateness by its label and dashes for unsubmitted rows', async () => {
    const wrapper = await mountPage()
    const alphaRow = wrapper.findAll('tbody tr').find((r) => r.text().includes('Alpha Team'))!
    expect(alphaRow.find('.by-group__late').text()).toBe('3h 12m')
    const unsubmitted = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-2'))!
    expect(unsubmitted.text()).toContain('No sub.')
    expect(unsubmitted.find('a').exists()).toBe(false)
  })

  it('names the first marker with a group icon when several marked, tooltip per part', async () => {
    const wrapper = await mountPage()
    const row = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-1'))!
    const marker = row.find('.by-group__marker')
    expect(marker.text()).toContain('Ada Grader')
    expect(row.find('.by-group__marker-icon').exists()).toBe(true) // Ada + Bob
    expect(marker.attributes('title')).toContain('SAQ 1: Ada Grader')
  })

  it('links each submitted group to its marking page', async () => {
    const wrapper = await mountPage()
    const row = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-1'))!
    expect(row.find('a').attributes('href')).toBe('/grading/groups/1')
  })

  it('reports a total failure instead of an empty table', async () => {
    rowsMock.mockRejectedValue(new Error('down'))
    const wrapper = await mountPage()
    expect(wrapper.find('.by-group__error').text()).toContain('Could not load the group list.')
    expect(wrapper.find('.by-group__empty').text()).toBe('No groups.')
  })
})

describe('search and sorting', () => {
  it('live-filters by name or id, and says when nothing matches', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.picker').setValue('alpha')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    await wrapper.find('.picker').setValue('999')
    expect(wrapper.find('.by-group__empty').text()).toBe('No groups match your search.')
  })

  it('defaults to newest submission first, with unsubmitted rows last', async () => {
    const wrapper = await mountPage()
    const names = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[1]!.text())
    expect(names).toEqual(['Alpha Team', 'BTF-1', 'BTF-2'])
  })

  it('sorting by id starts ascending and toggles', async () => {
    const wrapper = await mountPage()
    const idSort = wrapper.findAll('.by-group__sort').find((b) => b.text().includes('ID'))!
    await idSort.trigger('click')
    let ids = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[0]!.text())
    expect(ids).toEqual(['#1', '#2', '#3'])
    await idSort.trigger('click')
    ids = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[0]!.text())
    expect(ids).toEqual(['#3', '#2', '#1'])
  })

  it('sorting by progress pins unsubmitted rows to the bottom either way', async () => {
    const wrapper = await mountPage()
    const progressSort = wrapper.findAll('.by-group__sort').find((b) => b.text().includes('Progress'))!
    await progressSort.trigger('click')
    let names = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[1]!.text())
    expect(names[names.length - 1]).toBe('BTF-2')
    await progressSort.trigger('click')
    names = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[1]!.text())
    expect(names[names.length - 1]).toBe('BTF-2')
  })
})

describe('jumping to a group', () => {
  it('submitting the search opens the resolved group', async () => {
    resolveIdMock.mockReturnValue(3)
    const wrapper = await mountPage()
    await wrapper.find('form').trigger('submit')
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/3')
  })

  it('an unresolvable query is told so instead of navigating', async () => {
    resolveIdMock.mockReturnValue(null)
    const wrapper = await mountPage()
    await wrapper.find('form').trigger('submit')
    expect(wrapper.find('.by-group__error').text()).toBe('No group matches that name or ID.')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('picking a suggestion navigates straight there', async () => {
    const wrapper = await mountPage()
    wrapper.findComponent(GroupSearchInputStub).vm.$emit('select', { id: 5, name: 'X' })
    expect(pushMock).toHaveBeenCalledWith('/grading/groups/5')
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
