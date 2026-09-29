import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import FinalistPresentationPage from '@/views/grading/FinalistPresentationPage.vue'
import {
  addPresentationSlot,
  deletePresentationSlot,
  fetchPresentationResponses,
  fetchPresentationSlots,
  updatePresentationSlot,
  type PresentationResponseTeam,
  type PresentationSlots
} from '@/utils/gradingAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/gradingAPI', () => ({
  fetchPresentationResponses: vi.fn(),
  fetchPresentationSlots: vi.fn(),
  addPresentationSlot: vi.fn(),
  updatePresentationSlot: vi.fn(),
  deletePresentationSlot: vi.fn()
}))
const fetchMock = vi.mocked(fetchPresentationSlots)
const addMock = vi.mocked(addPresentationSlot)
const updateMock = vi.mocked(updatePresentationSlot)
const deleteMock = vi.mocked(deletePresentationSlot)
const responsesMock = vi.mocked(fetchPresentationResponses)

// BTF2: Zoe answered (the morning only), Amy hasn't; BTF10 has no students.
const TEAMS: PresentationResponseTeam[] = [
  {
    group_id: 2,
    group_name: 'BTF2',
    students: [
      { user_id: 11, name: 'Amy Chen', responded: false, slot_ids: [], updated_at: null },
      { user_id: 12, name: 'Zoe Lee', responded: true, slot_ids: [1], updated_at: '2026-09-29T05:10:00Z' }
    ]
  },
  { group_id: 10, group_name: 'BTF10', students: [] }
]

const slots = (over: Partial<PresentationSlots> = {}): PresentationSlots => ({
  year: 2026,
  symposium_date: '2026-10-23',
  slots: [
    { id: 1, starts_at: '09:30', ends_at: '10:00' },
    { id: 2, starts_at: '13:00', ends_at: '13:30' }
  ],
  ...over
})

const mountPage = async () => {
  const wrapper = mount(FinalistPresentationPage, {
    global: { stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } } }
  })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: string) =>
  wrapper.findAll('button').find((b) => b.text().trim() === label)!

// The times table's rows, as their start and end.
const rows = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper
    .findAll('.finalist-presentation__setup tbody tr')
    .map((r) => r.findAll('td').slice(0, 2).map((c) => c.text()))

const responses = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper.find('.finalist-presentation__responses')

beforeEach(() => {
  fetchMock.mockReset().mockResolvedValue(slots())
  addMock.mockReset()
  updateMock.mockReset()
  deleteMock.mockReset()
  responsesMock.mockReset().mockResolvedValue({ teams: TEAMS })
})

describe('Finalist Presentation', () => {
  it("lists this year's times on the Symposium day", async () => {
    const wrapper = await mountPage()
    expect(rows(wrapper)).toEqual([
      ['9:30', '10:00'],
      ['13:00', '13:30']
    ])
    expect(wrapper.text()).toContain("They're on the Symposium day, Friday 23 October 2026")
    expect(wrapper.find('a').attributes('href')).toBe('/management/notify-finalists')
  })

  it('asks for the Symposium date while it is not set, and says when there are no times', async () => {
    fetchMock.mockResolvedValue(slots({ symposium_date: null, slots: [] }))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain("They're on the Symposium day. Set its date on Notify Finalists.")
    expect(wrapper.find('.finalist-presentation__empty').text()).toBe('No times yet.')
  })

  it('adds a time, then offers the next one straight after it', async () => {
    addMock.mockResolvedValue(slots())
    const wrapper = await mountPage()
    const [start, end] = wrapper.findAll('.finalist-presentation__add input')
    await start!.setValue('10:00')
    await end!.setValue('10:30')
    await buttonNamed(wrapper, 'Add Time').trigger('click')
    await flushPromises()
    expect(addMock).toHaveBeenCalledWith({ starts_at: '10:00', ends_at: '10:30' })
    expect((start!.element as HTMLInputElement).value).toBe('10:30')
    expect((end!.element as HTMLInputElement).value).toBe('11:00')
  })

  it("shows why a time wasn't added", async () => {
    addMock.mockRejectedValue(
      new ApiError({ error: 'The end time must be after the start time.', code: 'invalid', request_id: 'x' })
    )
    const wrapper = await mountPage()
    const [start, end] = wrapper.findAll('.finalist-presentation__add input')
    await start!.setValue('10:00')
    await end!.setValue('09:00')
    await buttonNamed(wrapper, 'Add Time').trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').text()).toBe('The end time must be after the start time.')
  })

  it('changes a time in its row, and removes one', async () => {
    updateMock.mockResolvedValue(slots({ slots: [{ id: 1, starts_at: '09:30', ends_at: '10:15' }] }))
    deleteMock.mockResolvedValue(slots({ slots: [] }))
    const wrapper = await mountPage()
    await wrapper.findAll('tbody tr')[0]!.findAll('button')[0]!.trigger('click') // Edit
    const inputs = wrapper.findAll('tbody tr')[0]!.findAll('input')
    expect(inputs.map((i) => (i.element as HTMLInputElement).value)).toEqual(['09:30', '10:00'])
    await inputs[1]!.setValue('10:15')
    await buttonNamed(wrapper, 'Save').trigger('click')
    await flushPromises()
    expect(updateMock).toHaveBeenCalledWith(1, { starts_at: '09:30', ends_at: '10:15' })
    expect(rows(wrapper)).toEqual([['9:30', '10:15']])

    await buttonNamed(wrapper, 'Remove').trigger('click')
    await flushPromises()
    expect(deleteMock).toHaveBeenCalledWith(1)
    expect(wrapper.find('.finalist-presentation__empty').exists()).toBe(true)
  })

  it("Finalist Response has a column for each time and each student's answer", async () => {
    const wrapper = await mountPage()
    const table = responses(wrapper)
    expect(table.find('h3').text()).toBe('Finalist Response')
    const headers = table.findAll('thead th').map((h) => h.text().replace(/\s+/g, ' '))
    expect(headers).toEqual(['Group', 'Student', '9:30 – 10:00', '13:00 – 13:30', 'Answered'])

    const [amy, zoe, btf10] = table.findAll('tbody tr')
    // The group's name spans its students.
    expect(amy!.find('td').text()).toBe('BTF2')
    expect(amy!.find('td').attributes('rowspan')).toBe('2')
    expect(amy!.text()).toContain('No response yet')
    const zoeCells = zoe!.findAll('td')
    expect(zoeCells[0]!.text()).toBe('Zoe Lee')
    expect(zoeCells[1]!.find('.fa-check').exists()).toBe(true)
    expect(zoeCells[2]!.text()).toBe('—')
    // In 24 hour time, as the times are.
    expect(zoeCells[3]!.text()).toMatch(/^29 Sept, \d{1,2}:10$/)
    expect(btf10!.text()).toContain('No students')
  })

  it('says when there are no finalist teams yet', async () => {
    responsesMock.mockResolvedValue({ teams: [] })
    const wrapper = await mountPage()
    expect(responses(wrapper).find('.finalist-presentation__empty').text()).toBe('No finalist teams yet.')
  })

  it('offers a retry when the times fail to load', async () => {
    fetchMock.mockRejectedValueOnce(new Error('Server down'))
    const wrapper = await mountPage()
    expect(wrapper.find('.finalist-presentation__load-error').text()).toContain('Server down')
    await buttonNamed(wrapper, 'Try again').trigger('click')
    await flushPromises()
    expect(rows(wrapper)).toHaveLength(2)
  })
})
