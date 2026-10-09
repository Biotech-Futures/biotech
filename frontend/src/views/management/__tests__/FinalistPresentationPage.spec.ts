import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import FinalistPresentationPage from '@/views/management/FinalistPresentationPage.vue'
import {
  addPresentationSlot,
  allocatePresentationSlot,
  deletePresentationSlot,
  fetchPresentationResponses,
  fetchPresentationSlides,
  fetchPresentationSlots,
  setPresentationTimesShown,
  updatePresentationSlot,
  type PresentationResponseTeam,
  type PresentationSlots
} from '@/utils/managementAPI'
import { ApiError } from '@/utils/apiError'

vi.mock('@/utils/managementAPI', () => ({
  allocatePresentationSlot: vi.fn(),
  fetchPresentationResponses: vi.fn(),
  fetchPresentationSlides: vi.fn(),
  fetchPresentationSlots: vi.fn(),
  addPresentationSlot: vi.fn(),
  updatePresentationSlot: vi.fn(),
  deletePresentationSlot: vi.fn(),
  setPresentationTimesShown: vi.fn(),
  presentationSlidesUrl: (groupId: number) => `/slides/${groupId}/file/`,
  presentationSlidesDownloadUrl: (groupId: number) => `/slides/${groupId}/file/?download=1`
}))
const fetchMock = vi.mocked(fetchPresentationSlots)
const addMock = vi.mocked(addPresentationSlot)
const updateMock = vi.mocked(updatePresentationSlot)
const deleteMock = vi.mocked(deletePresentationSlot)
const responsesMock = vi.mocked(fetchPresentationResponses)
const slidesMock = vi.mocked(fetchPresentationSlides)
const allocateMock = vi.mocked(allocatePresentationSlot)
const shownMock = vi.mocked(setPresentationTimesShown)

// BTF2: Zoe answered for the team (the morning only), which has the
// morning; BTF10 hasn't answered.
const TEAMS: PresentationResponseTeam[] = [
  {
    group_id: 2,
    group_name: 'BTF2',
    allocated_slot_id: 1,
    slot_ids: [1],
    answered_at: '2026-09-29T05:10:00Z',
    answered_by: 'Zoe Lee'
  },
  {
    group_id: 10,
    group_name: 'BTF10',
    allocated_slot_id: null,
    slot_ids: [],
    answered_at: null,
    answered_by: null
  }
]

const slots = (over: Partial<PresentationSlots> = {}): PresentationSlots => ({
  year: 2026,
  symposium_date: '2026-10-23',
  times_shown: false,
  submissions_open: false,
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

const allocation = (wrapper: Awaited<ReturnType<typeof mountPage>>) =>
  wrapper.find('.finalist-presentation__allocate')

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
    expect(wrapper.text()).toContain("They're for the Symposium day, Friday 23 October 2026")
    // Sydney time, worked out for that day: daylight saving by late October.
    expect(wrapper.find('[data-testid="sydney-time"]').text()).toBe(
      'All times are Sydney time, AEDT (daylight saving, UTC+11) on that day. ' +
        "They're entered and shown in Sydney time, whatever time zone you or the finalists are in."
    )
    expect(wrapper.find('a').attributes('href')).toBe('/management/notify-finalists')
  })

  it('keeps the times hidden from finalists until switched on', async () => {
    shownMock.mockResolvedValueOnce(slots({ times_shown: true }))
    const wrapper = await mountPage()
    const toggle = wrapper.find('input[role="switch"]')
    expect((toggle.element as HTMLInputElement).checked).toBe(false)
    expect(wrapper.find('.finalist-presentation__switch-label').text()).toBe('Hidden from Finalists')

    await toggle.setValue(true)
    await flushPromises()
    expect(shownMock).toHaveBeenCalledWith(true)
    expect(wrapper.find('.finalist-presentation__switch-label').text()).toBe('Displayed to Finalists')
  })

  it("can't be switched on while submissions are open, saying why as Release Marks does", async () => {
    fetchMock.mockResolvedValue(slots({ submissions_open: true }))
    const wrapper = await mountPage()
    expect(wrapper.find('.finalist-presentation__banner--warn').text()).toBe(
      'Submissions are still open (including extensions) - time slots can be shown once the window has closed.'
    )
    expect(wrapper.find('input[role="switch"]').attributes('disabled')).toBeDefined()

    // Already on: no notice, and it can still be hidden.
    fetchMock.mockResolvedValue(slots({ submissions_open: true, times_shown: true }))
    const shown = await mountPage()
    expect(shown.find('.finalist-presentation__banner--warn').exists()).toBe(false)
    expect(shown.find('input[role="switch"]').attributes('disabled')).toBeUndefined()
  })

  it('asks for the Symposium date while it is not set, and says when there are no times', async () => {
    fetchMock.mockResolvedValue(slots({ symposium_date: null, slots: [] }))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain("They're for the Symposium day. Set its date on Notify Finalists.")
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

  it('says when there are no finalist teams yet', async () => {
    responsesMock.mockResolvedValue({ teams: [] })
    const wrapper = await mountPage()
    expect(allocation(wrapper).find('.finalist-presentation__empty').text()).toBe('No finalist teams yet.')
    expect(allocation(wrapper).find('.finalist-presentation__empty').attributes('colspan')).toBe('5')
  })

  it("Allocate Slots shows when each team answered and the times it can make", async () => {
    const wrapper = await mountPage()
    const titles = wrapper.findAll('.finalist-presentation__section-title').map((h) => h.text())
    expect(titles).toEqual(['Presentation Times', 'Show Time Slots', 'Allocate Slots', 'Finalist Submissions'])
    expect(allocation(wrapper).text()).toContain(
      'Give each finalist team a time. Ticks show the times each team said it can make.'
    )
    const table = allocation(wrapper)
    expect(table.findAll('thead th').map((h) => h.text())).toEqual([
      'Group',
      'Answered',
      'Allocate',
      '9:30 – 10:00',
      '13:00 – 13:30'
    ])
    const [btf2, btf10] = table.findAll('tbody tr')
    const cells = btf2!.findAll('td')
    expect(cells[0]!.text()).toBe('BTF2')
    // When it answered, as Finalist Submissions writes it; who, on hover.
    expect(cells[1]!.text()).toMatch(/^29\/09\/26 \d{2}:10$/)
    expect(cells[1]!.attributes('title')).toBe('By Zoe Lee')
    expect((cells[2]!.find('select').element as HTMLSelectElement).value).toBe('1')
    expect(cells[2]!.findAll('option').map((o) => o.text())).toEqual([
      'Not allocated',
      '9:30 – 10:00',
      '13:00 – 13:30'
    ])
    // It can make the morning (the time it has), not the afternoon.
    expect(cells[3]!.find('.fa-check').exists()).toBe(true)
    expect(cells[3]!.classes()).toContain('is-allocated')
    expect(cells[4]!.text()).toBe('—')
    // BTF10 hasn't answered.
    const btf10Cells = btf10!.findAll('td')
    expect(btf10Cells[1]!.text()).toBe('No response')
    expect(btf10Cells.slice(3).map((c) => c.text())).toEqual(['—', '—'])
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
    expect(cells[4]!.classes()).toContain('is-allocated')

    await select.setValue('')
    await flushPromises()
    expect(allocateMock).toHaveBeenLastCalledWith(2, null)
    expect(cells[3]!.classes()).not.toContain('is-allocated')
    expect(cells[4]!.classes()).not.toContain('is-allocated')
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

  it("Finalist Submissions lists each finalist team's slides and when they're due", async () => {
    const wrapper = await mountPage()
    const table = wrapper.find('.finalist-presentation__submissions')
    expect(table.find('h3').text()).toBe('Finalist Submissions')
    expect(table.text()).toContain("Each finalist team's presentation slides, due Friday 16 October 2026")
    expect(table.findAll('thead th').map((h) => h.text())).toEqual(['Group', 'Submitted', 'Type', ''])
    const [btf2, btf10] = table.findAll('tbody tr')
    const cells = btf2!.findAll('td')
    expect(cells[0]!.text()).toBe('BTF2')
    expect(cells[1]!.text()).toMatch(/^10\/10\/26 \d{2}:05$/)
    expect(cells[2]!.text()).toBe('PPTX')
    // PowerPoint can't show in the browser: only Download, its name on hover.
    const links = cells[3]!.findAll('a')
    expect(links.map((a) => a.text())).toEqual(['Download'])
    expect(links[0]!.attributes('href')).toBe('/slides/2/file/?download=1')
    expect(links[0]!.attributes('title')).toBe('BTF2 slides.pptx')
    expect(btf10!.text()).toBe('BTF10Not submitted yet')
    expect(btf10!.find('a').exists()).toBe(false)
  })

  it('a PDF opens in a new tab, with Download to its right', async () => {
    slidesMock.mockResolvedValue({
      slides_due: '2026-10-16',
      teams: [
        {
          group_id: 2, group_name: 'BTF2', submitted: true, file_name: 'BTF2 slides.pdf',
          submitted_by: 'Amy Chen', submitted_at: '2026-10-10T00:05:00Z'
        }
      ]
    })
    const wrapper = await mountPage()
    const row = wrapper.find('.finalist-presentation__submissions tbody tr')
    expect(row.findAll('td')[2]!.text()).toBe('PDF')
    const [open, download] = row.findAll('a')
    expect([open!.text(), download!.text()]).toEqual(['Open', 'Download'])
    expect(open!.attributes('href')).toBe('/slides/2/file/')
    expect(open!.attributes('target')).toBe('_blank')
    expect(download!.attributes('href')).toBe('/slides/2/file/?download=1')
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
