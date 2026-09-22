import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import * as vueRouter from 'vue-router'
import ComponentTablePage from '@/views/grading/ComponentTablePage.vue'
import { fetchComponentRows } from '@/utils/gradingAPI'
import { useJobPolling } from '@/composables/useJobPolling'

vi.mock('@/utils/gradingAPI', () => ({
  fetchComponentRows: vi.fn()
}))
const rowsMock = vi.mocked(fetchComponentRows)

const pushMock = vi.hoisted(() => vi.fn())
vi.mock('vue-router', async () => {
  const { reactive } = await import('vue')
  const route = reactive({ params: { code: 'SAQ' } as Record<string, string> })
  return {
    useRoute: () => route,
    useRouter: () => ({ push: pushMock }),
    __route: route
  }
})
const routeState = (vueRouter as unknown as { __route: { params: Record<string, string> } }).__route

vi.mock('@/composables/useJobPolling', () => ({ useJobPolling: vi.fn() }))
const jobMock = vi.mocked(useJobPolling)
let jobPhase: { value: string }
let jobError: { value: string }
let startJob: ReturnType<typeof vi.fn>

const row = (over: Record<string, unknown> = {}) => ({
  group_id: 1,
  group_name: 'BTF-1',
  submission_id: 11,
  submitted_at: '2026-09-01T10:00:00Z',
  is_late: false,
  late_by: null,
  criteria_graded: 2,
  marks_total: '12.50',
  last_grader_name: 'Ada Grader',
  grader_names: ['Ada Grader', 'Bob Marker'],
  criterion_markers: [
    { n: 1, marker: 'Ada Grader' },
    { n: 2, marker: 'Bob Marker' }
  ],
  ...over
})

const payload = (over: Record<string, unknown> = {}) => ({
  component: {
    id: 1, code: 'SAQ', name: 'Short Answer Questions', is_optional: false,
    accepts_file: false, accepts_text: true, accepts_link: false, order: 10
  },
  year: 2026,
  criteria_total: 2,
  rows: [
    row(),
    row({
      group_id: 2, group_name: 'BTF-2', submission_id: null, submitted_at: null,
      criteria_graded: 0, marks_total: null, last_grader_name: null,
      grader_names: [], criterion_markers: []
    }),
    row({
      group_id: 3, group_name: 'Alpha Team', submission_id: 13,
      submitted_at: '2026-09-02T09:00:00Z', is_late: true, late_by: '3h 12m',
      criteria_graded: 1, marks_total: '4.00',
      grader_names: ['Ada Grader'], criterion_markers: []
    })
  ],
  ...over
})

const mountPage = async () => {
  const wrapper = mount(ComponentTablePage, {
    global: {
      stubs: {
        BulkUploadDialog: {
          props: ['code'],
          emits: ['applied'],
          template: '<button class="bulk-stub" @click="$emit(\'applied\', 3)">Upload marks</button>'
        },
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
      }
    }
  })
  await flushPromises()
  return wrapper
}

const rowByName = (wrapper: Awaited<ReturnType<typeof mountPage>>, name: string) =>
  wrapper.findAll('tbody tr').find((r) => r.text().includes(name))!

beforeEach(() => {
  routeState.params.code = 'SAQ'
  pushMock.mockReset()
  rowsMock.mockReset().mockResolvedValue(payload() as never)
  jobPhase = ref('idle')
  jobError = ref('')
  startJob = vi.fn()
  jobMock.mockReturnValue({
    phase: jobPhase as never,
    error: jobError as never,
    isBusy: computed(() => false),
    start: startJob,
    startAll: vi.fn()
  } as never)
})

describe('the component switcher', () => {
  it('offers all four components with the routed one active', async () => {
    const wrapper = await mountPage()
    const tabs = wrapper.findAll('[role="tab"]')
    expect(tabs.map((t) => t.text())).toEqual([
      'Short Answer Questions', 'A2 Poster', 'Scientific Report', 'Prototype'
    ])
    expect(tabs[0]!.attributes('aria-selected')).toBe('true')
  })

  it('switching navigates; re-clicking the active tab does not', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('[role="tab"]')[1]!.trigger('click')
    expect(pushMock).toHaveBeenCalledWith('/grading/components/POSTER')
    pushMock.mockClear()
    await wrapper.findAll('[role="tab"]')[0]!.trigger('click')
    expect(pushMock).not.toHaveBeenCalled()
  })

  it('a route change reloads the table and clears search and banners', async () => {
    const wrapper = await mountPage()
    await wrapper.find('input[type="search"]').setValue('alpha')
    routeState.params.code = 'POSTER'
    await flushPromises()
    expect(rowsMock).toHaveBeenLastCalledWith('POSTER')
    expect((wrapper.find('input[type="search"]').element as HTMLInputElement).value).toBe('')
  })
})

describe('the table', () => {
  it('shows progress, marks, lateness and markers per row', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.component-table__stats').text()).toContain('2/3 Submitted')
    expect(wrapper.find('.component-table__stats').text()).toContain('1/2 Fully Marked')

    const done = rowByName(wrapper, 'BTF-1')
    expect(done.text()).toContain('2/2')
    expect(done.find('.component-table__done').exists()).toBe(true)
    expect(done.text()).toContain('12.50')
    expect(done.find('.component-table__marker').attributes('title')).toBe(
      '1: Ada Grader\n2: Bob Marker'
    )
    expect(done.find('.component-table__marker-icon').exists()).toBe(true)
    expect(done.find('a').attributes('href')).toBe('/grading/components/SAQ/1')

    const late = rowByName(wrapper, 'Alpha Team')
    expect(late.find('.component-table__late').text()).toBe('3h 12m')
    // No per-criterion data → flat marked-by fallback.
    expect(late.find('.component-table__marker').attributes('title')).toBe('Marked by: Ada Grader')

    const unsubmitted = rowByName(wrapper, 'BTF-2')
    expect(unsubmitted.text()).toContain('No submission')
  })

  it('shows a dash progress when the component has no rubric yet', async () => {
    rowsMock.mockResolvedValue(payload({ criteria_total: 0 }) as never)
    const wrapper = await mountPage()
    expect(rowByName(wrapper, 'BTF-1').find('.component-table__progress').text()).toContain('—')
  })

  it('live-filters and reports an empty search honestly', async () => {
    const wrapper = await mountPage()
    await wrapper.find('input[type="search"]').setValue('alpha')
    expect(wrapper.findAll('tbody tr')).toHaveLength(1)
    await wrapper.find('input[type="search"]').setValue('zzz')
    expect(wrapper.find('.component-table__empty').text()).toBe('No groups match your search.')
  })

  it('progress sort pins unsubmitted rows last in both directions', async () => {
    const wrapper = await mountPage()
    const progressSort = wrapper
      .findAll('.component-table__sort')
      .find((b) => b.text().includes('Progress'))!
    await progressSort.trigger('click')
    let names = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[1]!.text())
    expect(names[names.length - 1]).toBe('BTF-2')
    await progressSort.trigger('click')
    names = wrapper.findAll('tbody tr').map((r) => r.findAll('td')[1]!.text())
    expect(names[names.length - 1]).toBe('BTF-2')
  })

  it('offers a retry when the component fails to load', async () => {
    rowsMock.mockRejectedValueOnce(new Error('no such component'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load component "SAQ".')
    await wrapper.findAll('button').find((b) => /Try again/.test(b.text()))!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.component-table__stats').exists()).toBe(true)
  })
})

describe('exports and uploads', () => {
  it('offers the XLSX export only for SAQ', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll('button').some((b) => /XLSX/.test(b.text()))).toBe(true)

    rowsMock.mockResolvedValue(
      payload({ component: { ...payload().component, code: 'POSTER' } }) as never
    )
    routeState.params.code = 'POSTER'
    await flushPromises()
    expect(wrapper.findAll('button').some((b) => /XLSX/.test(b.text()))).toBe(false)
  })

  it('starts the export job for the routed component', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /XLSX/.test(b.text()))!.trigger('click')
    expect(startJob).toHaveBeenCalledWith('SAQ', 'xlsx')
    await wrapper.findAll('button').find((b) => /Download/.test(b.text()))!.trigger('click')
    expect(startJob).toHaveBeenCalledWith('SAQ', 'zip')
  })

  it('a failed export shows the job error banner', async () => {
    jobPhase.value = 'failed'
    jobError.value = 'disk full'
    const wrapper = await mountPage()
    expect(wrapper.find('.component-table__banner--error').text()).toBe('disk full')
  })

  it('an applied upload reports the rows written and refreshes the table', async () => {
    const wrapper = await mountPage()
    // The dialog child announces how much it wrote.
    await wrapper.find('.bulk-stub').trigger('click')
    await flushPromises()
    expect(wrapper.find('.component-table__banner--ok').text()).toBe('Marks applied - wrote 3 rows.')
    expect(rowsMock).toHaveBeenCalledTimes(2)
  })
})
