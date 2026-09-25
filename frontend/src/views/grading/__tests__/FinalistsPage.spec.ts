import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import FinalistsPage from '@/views/grading/FinalistsPage.vue'
import {
  addFinalist,
  fetchFinalistCandidates,
  fetchFinalists,
  removeFinalist
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  addFinalist: vi.fn(),
  fetchFinalistCandidates: vi.fn(),
  fetchFinalists: vi.fn(),
  removeFinalist: vi.fn()
}))
const addMock = vi.mocked(addFinalist)
const candidatesMock = vi.mocked(fetchFinalistCandidates)
const finalistsMock = vi.mocked(fetchFinalists)
const removeMock = vi.mocked(removeFinalist)

const resolveIdMock = vi.fn<() => number | null>()
const GroupSearchInputStub = defineComponent({
  name: 'GroupSearchInput',
  props: { modelValue: { type: String, default: '' }, showSuggestions: { type: Boolean, default: true } },
  emits: ['update:modelValue'],
  methods: {
    resolveId(): number | null {
      return resolveIdMock()
    }
  },
  template:
    '<input class="picker" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
})

const candidate = (over: Record<string, unknown> = {}) => ({
  group_id: 1,
  group_name: 'BTF-1',
  is_late: false,
  late_by: null,
  marks: { SAQ: '12.50', POSTER: '7.00' },
  total: '19.50',
  markers: ['Ada Grader', 'Bob Marker'],
  criterion_markers: [{ label: 'SAQ 1', marker: 'Ada Grader' }],
  is_finalist: false,
  has_submission: true,
  ...over
})

const mountPage = async () => {
  const wrapper = mount(FinalistsPage, {
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
  addMock.mockReset().mockResolvedValue(undefined as never)
  removeMock.mockReset().mockResolvedValue(undefined as never)
  resolveIdMock.mockReset()
  candidatesMock.mockReset().mockResolvedValue({
    components: [
      { code: 'SAQ', name: 'Short Answer Questions' },
      { code: 'POSTER', name: 'Poster' }
    ],
    rows: [
      candidate(),
      candidate({
        group_id: 2,
        group_name: 'BTF-2',
        is_late: true,
        late_by: '3h 12m',
        marks: { SAQ: null, POSTER: null },
        total: null,
        markers: [],
        criterion_markers: [],
        is_finalist: true,
        has_submission: false
      })
    ]
  })
  finalistsMock.mockReset().mockResolvedValue({
    finalists: [
      {
        group_id: 2,
        group_name: 'BTF-2',
        flagged_at: '2026-09-10T02:00:00Z',
        flagged_by: 'Ada Admin',
        notified: false,
        notified_at: null,
        notified_by: null
      }
    ]
  })
})

describe('the group marks ranking', () => {
  it('shows per-component columns with marks, dashes and the total', async () => {
    const wrapper = await mountPage()
    const headers = wrapper.findAll('thead th').map((h) => h.text())
    expect(headers).toContain('SAQ')
    expect(headers).toContain('POSTER')

    const graded = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-1'))!
    expect(graded.text()).toContain('12.50')
    expect(graded.text()).toContain('19.50')

    const ungraded = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-2'))!
    expect(ungraded.find('.finalists__late').text()).toBe('3h 12m')
    expect(ungraded.text()).toContain('No sub.')
  })

  it('tooltips the markers per criterion, first name shown with a group icon', async () => {
    const wrapper = await mountPage()
    const marker = wrapper.find('.finalists__marker')
    expect(marker.text()).toContain('Ada Grader')
    expect(marker.attributes('title')).toBe('SAQ 1: Ada Grader')
    expect(wrapper.find('.finalists__marker-icon').exists()).toBe(true)
  })

  it('an existing finalist reads Added instead of offering the button again', async () => {
    const wrapper = await mountPage()
    const finalistRow = wrapper.findAll('tbody tr').find((r) => r.text().includes('BTF-2'))!
    expect(finalistRow.text()).toContain('Added')
    expect(finalistRow.findAll('button').some((b) => b.text().trim() === 'Add')).toBe(false)
  })

  it('live-filters by the search text', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.picker').setValue('BTF-1')
    const rows = wrapper.findAll('.finalists__table')[0]!.findAll('tbody tr')
    expect(rows).toHaveLength(1)
    await wrapper.find('.picker').setValue('nothing')
    expect(wrapper.find('.finalists__empty').text()).toBe('No groups match your search.')
  })

  it('adding from a row flags the group and refreshes both tables', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => b.text().trim() === 'Add')!.trigger('click')
    await flushPromises()
    expect(addMock).toHaveBeenCalledWith(1)
    expect(finalistsMock).toHaveBeenCalledTimes(2)
    expect(candidatesMock).toHaveBeenCalledTimes(2)
  })

  it('adding by search refuses an unresolvable group', async () => {
    resolveIdMock.mockReturnValue(null)
    const wrapper = await mountPage()
    await wrapper.find('form').trigger('submit')
    expect(wrapper.find('.finalists__banner--error').text()).toBe('No group matches that name or ID.')
    expect(addMock).not.toHaveBeenCalled()
  })

  it('adding by search flags the resolved group and clears the query', async () => {
    resolveIdMock.mockReturnValue(1)
    const wrapper = await mountPage()
    await wrapper.find('.picker').setValue('BTF-1')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(addMock).toHaveBeenCalledWith(1)
    expect((wrapper.find('.picker').element as HTMLInputElement).value).toBe('')
  })

  it('a refused add is reported', async () => {
    addMock.mockRejectedValueOnce(new Error('not allowed'))
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => b.text().trim() === 'Add')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('.finalists__banner--error').text()).toContain('not allowed')
  })
})

describe('the current finalists', () => {
  it('lists who was flagged, when and by whom', async () => {
    const wrapper = await mountPage()
    const table = wrapper.findAll('.finalists__table')[1]!
    expect(table.text()).toContain('BTF-2')
    expect(table.text()).toContain('Ada Admin')
  })

  it('removing unflags and refreshes', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /^Remove$/.test(b.text()))!.trigger('click')
    await flushPromises()
    expect(removeMock).toHaveBeenCalledWith(2)
    expect(finalistsMock).toHaveBeenCalledTimes(2)
  })

  it('says so when nobody is flagged yet', async () => {
    finalistsMock.mockResolvedValue({ finalists: [] })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('No finalists yet.')
  })

  it('offers a retry when the list fails', async () => {
    finalistsMock.mockRejectedValueOnce(new Error('down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load.')
    await wrapper.findAll('button').find((b) => /Try again/.test(b.text()))!.trigger('click')
    await flushPromises()
    expect(wrapper.findAll('.finalists__table')[1]!.text()).toContain('BTF-2')
  })
})

describe('collapsing', () => {
  it('each section folds away behind its heading', async () => {
    const wrapper = await mountPage()
    expect(wrapper.findAll('.finalists__table')).toHaveLength(2)

    await wrapper.findAll('.finalists__collapse-btn')[0]!.trigger('click')
    expect(wrapper.findAll('.finalists__table')).toHaveLength(1)

    await wrapper.findAll('.finalists__collapse-btn')[1]!.trigger('click')
    expect(wrapper.findAll('.finalists__table')).toHaveLength(0)
  })
})
