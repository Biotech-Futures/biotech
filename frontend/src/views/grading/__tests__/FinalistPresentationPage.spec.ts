import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import FinalistPresentationPage from '@/views/grading/FinalistPresentationPage.vue'
import {
  addPresentationSlot,
  allocatePresentationSlot,
  deletePresentationSlot,
  fetchPresentationResponses,
  fetchPresentationSlides,
  fetchPresentationSlots,
  updatePresentationSlot,
  type PresentationResponseTeam,
  type PresentationSlots
} from '@/utils/gradingAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/gradingAPI', () => ({
  allocatePresentationSlot: vi.fn(),
  fetchPresentationResponses: vi.fn(),
  fetchPresentationSlides: vi.fn(),
  fetchPresentationSlots: vi.fn(),
  addPresentationSlot: vi.fn(),
  updatePresentationSlot: vi.fn(),
  deletePresentationSlot: vi.fn(),
  presentationSlidesUrl: (groupId: number) => `/slides/${groupId}/file/`
}))
const fetchMock = vi.mocked(fetchPresentationSlots)
const addMock = vi.mocked(addPresentationSlot)
const updateMock = vi.mocked(updatePresentationSlot)
const deleteMock = vi.mocked(deletePresentationSlot)
const responsesMock = vi.mocked(fetchPresentationResponses)
const slidesMock = vi.mocked(fetchPresentationSlides)
const allocateMock = vi.mocked(allocatePresentationSlot)

// BTF2: Zoe answered (the morning only), Amy hasn't, and the team has the
// morning; BTF10 has no students.
const TEAMS: PresentationResponseTeam[] = [
  {
    group_id: 2,
    group_name: 'BTF2',
    allocated_slot_id: 1,
    students: [
      { user_id: 11, name: 'Amy Chen', responded: false, slot_ids: [], updated_at: null },
      { user_id: 12, name: 'Zoe Lee', responded: true, slot_ids: [1], updated_at: '2026-09-29T05:10:00Z' }
    ]
  },
  { group_id: 10, group_name: 'BTF10', allocated_slot_id: null, students: [] }
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
  // A fresh copy each time: the page updates a team it allocates.
  responsesMock.mockReset().mockImplementation(async () => ({ teams: structuredClone(TEAMS) }))
  allocateMock.mockReset()
  slidesMock.mockReset().mockResolvedValue({
    slides_due: '2026-10-16',
    teams: [
      {
        group_id: 2,
        group_name: 'BTF2',
        submitted: true,
        file_name: 'BTF2 slides.pptx',
        submitted_by: 'Zoe Lee',
        submitted_at: '2026-10-10T03:05:00Z'
      },
      {
        group_id: 10,
        group_name: 'BTF10',
        submitted: false,
        file_name: '',
        submitted_by: null,
        submitted_at: null
      }
    ]
  })
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
    expect(headers).toEqual(['Group', 'Student', 'Answered', '9:30 – 10:00', '13:00 – 13:30'])

    const [amy, zoe, btf10] = table.findAll('tbody tr')
    // The group's name spans its students.
    expect(amy!.find('td').text()).toBe('BTF2')
    expect(amy!.find('td').attributes('rowspan')).toBe('2')
    expect(amy!.text()).toContain('No response')
    expect(amy!.text()).not.toContain('yet')
    const zoeCells = zoe!.findAll('td')
    expect(zoeCells[0]!.text()).toBe('Zoe Lee')
    // When they answered, in 24 hour time as the times are, then their ticks.
    expect(zoeCells[1]!.text()).toMatch(/^29 Sept, \d{1,2}:10$/)
    expect(zoeCells[2]!.find('.fa-check').exists()).toBe(true)
    expect(zoeCells[3]!.text()).toBe('—')
    expect(btf10!.text()).toContain('No students')
  })

  it('says when there are no finalist teams yet', async () => {
    responsesMock.mockResolvedValue({ teams: [] })
    const wrapper = await mountPage()
    expect(responses(wrapper).find('.finalist-presentation__empty').text()).toBe('No finalist teams yet.')
  })

  it('Allocate Slot counts who can make each time, after Finalist Response', async () => {
    responsesMock.mockImplementation(async () => ({
      teams: [
        {
          ...structuredClone(TEAMS[0]!),
          students: [
            { user_id: 11, name: 'Amy Chen', responded: true, slot_ids: [1, 2], updated_at: null },
            { user_id: 12, name: 'Zoe Lee', responded: true, slot_ids: [1], updated_at: null }
          ]
        },
        structuredClone(TEAMS[1]!)
      ]
    }))
    const wrapper = await mountPage()
    const titles = wrapper.findAll('.finalist-presentation__section-title').map((h) => h.text())
    expect(titles).toEqual([
      'Presentation Times',
      'Finalist Response',
      'Allocate Slot',
      'Finalist Submission'
    ])
    const table = wrapper.find('.finalist-presentation__allocate')
    expect(table.findAll('thead th').map((h) => h.text())).toEqual([
      'Group',
      'Allocate',
      '9:30 – 10:00',
      '13:00 – 13:30'
    ])
    const [btf2] = table.findAll('tbody tr')
    const cells = btf2!.findAll('td')
    expect(cells[0]!.text()).toBe('BTF2')
    expect((cells[1]!.find('select').element as HTMLSelectElement).value).toBe('1')
    expect(cells[1]!.findAll('option').map((o) => o.text())).toEqual([
      'Not allocated',
      '9:30 – 10:00',
      '13:00 – 13:30'
    ])
    // Both students can make the morning (the time it has); one the afternoon.
    expect([cells[2]!.text(), cells[3]!.text()]).toEqual(['2', '1'])
    expect(cells[2]!.classes()).toEqual(expect.arrayContaining(['is-allocated', 'is-everyone']))
    expect(cells[3]!.classes()).not.toContain('is-everyone')
  })

  it('choosing a time gives it to the team, and Not allocated takes it away', async () => {
    allocateMock.mockResolvedValueOnce({ group_id: 2, slot_id: 2 })
    allocateMock.mockResolvedValueOnce({ group_id: 2, slot_id: null })
    const wrapper = await mountPage()
    const select = wrapper.find('.finalist-presentation__allocate select')
    await select.setValue('2')
    await flushPromises()
    expect(allocateMock).toHaveBeenLastCalledWith(2, 2)
    const cells = wrapper.find('.finalist-presentation__allocate tbody tr').findAll('td')
    expect(cells[3]!.classes()).toContain('is-allocated')

    await select.setValue('')
    await flushPromises()
    expect(allocateMock).toHaveBeenLastCalledWith(2, null)
    expect(cells[2]!.classes()).not.toContain('is-allocated')
    expect(cells[3]!.classes()).not.toContain('is-allocated')
  })

  it("keeps the team's time and says why when giving it another fails", async () => {
    allocateMock.mockRejectedValueOnce(
      new ApiError({ error: "That time isn't one of this year's.", code: 'x', request_id: 'x' })
    )
    const wrapper = await mountPage()
    const select = wrapper.find('.finalist-presentation__allocate select')
    await select.setValue('2')
    await flushPromises()
    expect((select.element as HTMLSelectElement).value).toBe('1')
    expect(wrapper.find('.finalist-presentation__allocate [role="alert"]').text()).toBe(
      "BTF2: That time isn't one of this year's."
    )
  })

  it("Finalist Submission lists each finalist team's slides and when they're due", async () => {
    const wrapper = await mountPage()
    const table = wrapper.find('.finalist-presentation__submissions')
    expect(table.find('h3').text()).toBe('Finalist Submission')
    expect(table.text()).toContain("Each finalist team's presentation slides, due Friday 16 October 2026")
    expect(table.findAll('thead th').map((h) => h.text())).toEqual(['Group', 'Submitted', ''])
    const [btf2, btf10] = table.findAll('tbody tr')
    const cells = btf2!.findAll('td')
    expect(cells[0]!.text()).toBe('BTF2')
    expect(cells[1]!.text()).toMatch(/^10\/10\/2026 \d{2}:05$/)
    // Open takes the slides to a new tab; their name is on hover.
    const open = cells[2]!.find('a')
    expect(open.text()).toBe('Open')
    expect(open.attributes('href')).toBe('/slides/2/file/')
    expect(open.attributes('target')).toBe('_blank')
    expect(open.attributes('title')).toBe('BTF2 slides.pptx')
    expect(btf10!.text()).toBe('BTF10Not submitted yet')
    expect(btf10!.find('a').exists()).toBe(false)
  })

  it('asks for the slides due date while it is not set', async () => {
    slidesMock.mockResolvedValue({ slides_due: null, teams: [] })
    const wrapper = await mountPage()
    const table = wrapper.find('.finalist-presentation__submissions')
    expect(table.text()).toContain("Set the date they're due on Notify Finalists.")
    expect(table.find('.finalist-presentation__empty').text()).toBe('No finalist teams yet.')
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
