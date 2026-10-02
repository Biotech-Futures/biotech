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

const GroupSearchInputStub = defineComponent({
  name: 'GroupSearchInput',
  props: { modelValue: { type: String, default: '' }, showSuggestions: { type: Boolean, default: true } },
  emits: ['update:modelValue'],
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
  project_title: '',
  project_category: 'Health and Medicine, Wearables',
  solution_category: 'App',
  is_finalist: false,
  has_submission: true,
  incomplete: [],
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
        has_submission: false,
        incomplete: []
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
    ] })
})

describe('the group marks ranking', () => {
  it('stars a report or prototype not marked completely, with the reason on hover', async () => {
    candidatesMock.mockResolvedValue({
      components: ['SAQ', 'POSTER', 'REPORT', 'PROTOTYPE'].map((code) => ({ code, name: code })),
      rows: [
        // Report half marked, prototype never sent.
        candidate({
          marks: { SAQ: '12.50', POSTER: '7.00', REPORT: '2.92', PROTOTYPE: null },
          incomplete: ['REPORT']
        }),
        // Report fully marked, prototype sent but not marked at all.
        candidate({
          group_id: 3,
          group_name: 'BTF-3',
          marks: { SAQ: '10.00', POSTER: '6.00', REPORT: '3.00', PROTOTYPE: null },
          incomplete: ['PROTOTYPE']
        }),
        // Only SAQ/poster incomplete: those columns are left as they are.
        candidate({
          group_id: 4,
          group_name: 'BTF-4',
          marks: { SAQ: '4.00', POSTER: null, REPORT: null, PROTOTYPE: null },
          incomplete: ['SAQ', 'POSTER']
        })
      ]
    })
    const wrapper = await mountPage()
    const cells = (name: string) =>
      wrapper
        .findAll('tbody tr')
        .find((r) => r.text().includes(name))!
        .findAll('td')
        .slice(2, 7) // SAQ, POSTER, SAQ&P., REPORT, PRO.
    const hover = (cell: ReturnType<typeof cells>[number]) =>
      cell.find('[title]').exists() ? cell.find('[title]').attributes('title') : null

    const [, , , report1, prototype1] = cells('BTF-1')
    expect(report1!.text()).toBe('2.92*')
    expect(hover(report1!)).toBe('Not Marked Completely')
    expect(prototype1!.text()).toBe('—')
    expect(hover(prototype1!)).toBeNull()

    const [, , , report3, prototype3] = cells('BTF-3')
    expect(report3!.text()).toBe('3.00')
    expect(prototype3!.text()).toBe('*')
    expect(hover(prototype3!)).toBe('Not Marked Completely')

    const [saq4, poster4] = cells('BTF-4')
    expect(saq4!.text()).toBe('4.00')
    expect(poster4!.text()).toBe('—')

    // The key above the table explains the asterisk.
    expect(wrapper.find('.finalists__legend').text()).toBe('* Not Marked Completely')
  })

  it('adds SAQ and Poster together in a column after the poster', async () => {
    const wrapper = await mountPage()
    const headers = wrapper.findAll('thead th').map((h) => h.text())
    expect(headers.slice(0, 6)).toEqual(['Group', 'Late', 'SAQ', 'POSTER', 'SAQ&P.', 'Total'])
    const cells = (name: string) =>
      wrapper.findAll('tbody tr').find((r) => r.text().includes(name))!.findAll('td')
    expect(cells('BTF-1')[4]!.text()).toBe('19.50') // 12.50 + 7.00
    expect(cells('BTF-2')[4]!.text()).toBe('—')
  })

  it('sorts by a header, again to reverse; a missing mark always sinks', async () => {
    candidatesMock.mockResolvedValue({
      components: [
        { code: 'SAQ', name: 'Short Answer Questions' },
        { code: 'POSTER', name: 'Poster' }
      ],
      rows: [
        candidate({ group_id: 10, group_name: 'BTF10', marks: { SAQ: '5.00', POSTER: '9.00' }, total: '14.00' }),
        candidate({ group_id: 2, group_name: 'BTF2', marks: { SAQ: '12.00', POSTER: '1.00' }, total: '13.00' }),
        candidate({ group_id: 3, group_name: 'BTF3', marks: { SAQ: null, POSTER: null }, total: null })
      ]
    })
    const wrapper = await mountPage()
    // The Group Marks table's rows, not the finalists' below it.
    const order = () => wrapper.findAll('table')[0]!.findAll('tbody tr').map((r) => r.find('td').text())
    const header = (label: string) =>
      wrapper.findAll('thead th').find((h) => h.text() === label)!.find('button')

    // The server's order to begin with.
    expect(order()).toEqual(['BTF10', 'BTF2', 'BTF3'])
    // Group names as numbers: BTF2 before BTF10, then reversed.
    await header('Group').trigger('click')
    expect(order()).toEqual(['BTF2', 'BTF3', 'BTF10'])
    expect(wrapper.findAll('thead th')[0]!.attributes('aria-sort')).toBe('ascending')
    await header('Group').trigger('click')
    expect(order()).toEqual(['BTF10', 'BTF3', 'BTF2'])
    // A mark starts highest first; the unmarked group stays last either way.
    await header('SAQ').trigger('click')
    expect(order()).toEqual(['BTF2', 'BTF10', 'BTF3'])
    await header('SAQ').trigger('click')
    expect(order()).toEqual(['BTF10', 'BTF2', 'BTF3'])
    await header('SAQ&P.').trigger('click')
    expect(order()).toEqual(['BTF10', 'BTF2', 'BTF3'])
    await header('Total').trigger('click')
    await header('Total').trigger('click')
    expect(order()).toEqual(['BTF2', 'BTF10', 'BTF3'])
  })

  it('leaves out the asterisk key when there is no report or prototype column', async () => {
    const wrapper = await mountPage() // SAQ and POSTER columns only
    expect(wrapper.find('.finalists__legend').exists()).toBe(false)
  })

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

  it('shows the title and categories on a row of their own under each group', async () => {
    const wrapper = await mountPage()
    // Hidden until Show Details is pressed, which then reads Hide Details.
    expect(wrapper.find('.finalists__details-row').exists()).toBe(false)
    const toggle = wrapper.find('.finalists__search-side button')
    expect(toggle.text()).toBe('Show Details')
    await toggle.trigger('click')
    expect(toggle.text()).toBe('Hide Details')
    const details = wrapper.findAll('.finalists__details-row')
    expect(details).toHaveLength(2)
    // Title on its line; the categories on the next.
    expect(details[0]!.find('div').text()).toBe('Title: —')
    const text = details[0]!.text().replace(/\s+/g, ' ')
    expect(text).toContain('Category: Health and Medicine, Wearables Solution Category: App')
    // Spans the whole table, like the extensions' reason row.
    expect(details[0]!.find('td').attributes('colspan')).toBe('8')

    await toggle.trigger('click')
    expect(wrapper.find('.finalists__details-row').exists()).toBe(false)
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

  it('pressing Enter in the search only filters, never flags', async () => {
    const wrapper = await mountPage()
    await wrapper.find('.picker').setValue('BTF-1')
    await wrapper.find('.picker').trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(wrapper.find('form').exists()).toBe(false)
    expect(addMock).not.toHaveBeenCalled()
    expect((wrapper.find('.picker').element as HTMLInputElement).value).toBe('BTF-1')
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

  it('Remove asks first, naming the group', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /^Remove$/.test(b.text()))!.trigger('click')
    const dialog = wrapper.find('.finalists__dialog')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('Remove this finalist?')
    expect(dialog.text()).toContain('BTF-2')
    expect(dialog.text()).not.toContain('already been emailed')
    expect(removeMock).not.toHaveBeenCalled()
  })

  it('confirming unflags and refreshes', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /^Remove$/.test(b.text()))!.trigger('click')
    await wrapper.find('.finalists__dialog').findAll('button').at(-1)!.trigger('click')
    await flushPromises()
    expect(removeMock).toHaveBeenCalledWith(2)
    expect(finalistsMock).toHaveBeenCalledTimes(2)
    expect(wrapper.find('.finalists__dialog').exists()).toBe(false)
    // The refreshed tables are the confirmation; no success banner.
    expect(wrapper.text()).not.toContain('Finalist removed.')
  })

  it('cancelling removes nothing', async () => {
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /^Remove$/.test(b.text()))!.trigger('click')
    await wrapper.find('.finalists__dialog button').trigger('click') // Cancel
    expect(wrapper.find('.finalists__dialog').exists()).toBe(false)
    expect(removeMock).not.toHaveBeenCalled()
  })

  it('warns when the team was already emailed that they are a finalist', async () => {
    finalistsMock.mockResolvedValue({
      finalists: [
        {
          group_id: 2, group_name: 'BTF-2', flagged_at: '2026-09-20T00:00:00Z',
          flagged_by: 'Ada Admin', notified: true, notified_at: '2026-09-21T00:00:00Z',
          notified_by: 'Ada Admin'
        }
      ] })
    const wrapper = await mountPage()
    await wrapper.findAll('button').find((b) => /^Remove$/.test(b.text()))!.trigger('click')
    expect(wrapper.find('.finalists__dialog').text()).toContain(
      'Their team has already been emailed that they are a finalist.'
    )
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
