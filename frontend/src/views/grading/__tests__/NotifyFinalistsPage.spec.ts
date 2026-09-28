import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NotifyFinalistsPage from '@/views/grading/NotifyFinalistsPage.vue'
import {
  fetchFinalistEmailDetails,
  fetchFinalists,
  notifyFinalists,
  previewFinalistEmail,
  updateFinalistEmailDetails
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchFinalists: vi.fn(),
  notifyFinalists: vi.fn(),
  fetchFinalistEmailDetails: vi.fn(),
  updateFinalistEmailDetails: vi.fn(),
  previewFinalistEmail: vi.fn()
}))
const listMock = vi.mocked(fetchFinalists)
const notifyMock = vi.mocked(notifyFinalists)
const detailsMock = vi.mocked(fetchFinalistEmailDetails)
const saveMock = vi.mocked(updateFinalistEmailDetails)
const previewMock = vi.mocked(previewFinalistEmail)

// Every detail set: the email can go out.
const details = (over: Record<string, unknown> = {}) => ({
  symposium_date: '2026-10-23',
  confirm_by: '2026-10-04',
  slides_due: '2026-10-16',
  registration_url: 'https://events.example.com/s',
  complete: true,
  today: '2026-09-27',
  dates_in_past: [] as string[],
  ...over
})

const finalist = (group_id: number, over: Record<string, unknown> = {}) => ({
  group_id,
  group_name: `BTF-${group_id}`,
  flagged_at: '2026-09-01T00:00:00Z',
  flagged_by: 'Ada Admin',
  notified: false,
  notified_at: null,
  notified_by: null,
  students: 3,
  ...over
})

const mountPage = async () => {
  const wrapper = mount(NotifyFinalistsPage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  listMock.mockReset()
  notifyMock.mockReset()
  detailsMock.mockReset().mockResolvedValue(details())
  saveMock.mockReset()
  previewMock.mockReset()
  listMock.mockResolvedValue({
    finalists: [
      finalist(1),
      finalist(2, {
        notified: true,
        notified_at: '2026-09-10T00:00:00Z',
        notified_by: 'Ada Admin'
      })
    ]
  })
})

describe('the finalist roster', () => {
  it('lists teams with their notified stamp, dash when never emailed', async () => {
    const wrapper = await mountPage()
    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]!.text()).toContain('BTF-1')
    expect(rows[0]!.text()).toContain('—')
    expect(rows[1]!.text()).toContain(
      `${new Date('2026-09-10T00:00:00Z').toLocaleDateString('en-GB')} ${new Date('2026-09-10T00:00:00Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
    )
  })

  it('an already-notified team cannot be ticked again', async () => {
    const wrapper = await mountPage()
    const boxes = wrapper.findAll('tbody input[type="checkbox"]')
    expect(boxes[0]!.attributes('disabled')).toBeUndefined()
    expect(boxes[1]!.attributes('disabled')).toBeDefined()
  })

  it('surfaces the most recent send above the actions', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Last Emailed at')
    expect(wrapper.text()).toContain('by Ada Admin')
  })

  it('says so when no finalists exist yet', async () => {
    listMock.mockResolvedValue({ finalists: [] })
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__empty').text()).toBe('No finalists yet.')
    expect(wrapper.find('.notify-finalists__status').exists()).toBe(false)
  })

  it('warns while a team is still to be emailed', async () => {
    const wrapper = await mountPage()
    const status = wrapper.find('.notify-finalists__status')
    expect(status.text()).toBe('Emails are not sent to every group member')
    expect(status.classes()).toContain('notify-finalists__status--warn')
    // One of the two teams (3 students each) is notified.
    expect(wrapper.find('.notify-finalists__counts').text()).toBe('Students: 3 of 6 emailed')
  })

  it('says every member was emailed once all teams are notified', async () => {
    listMock.mockResolvedValue({
      finalists: [finalist(1, { notified: true, notified_at: '2026-09-10T00:00:00Z' })]
    })
    const wrapper = await mountPage()
    const status = wrapper.find('.notify-finalists__status')
    expect(status.text()).toBe('Emails are sent to every group member')
    expect(status.classes()).toContain('notify-finalists__status--ok')
  })

  it('offers a retry when the roster fails to load', async () => {
    listMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load.')
    await buttonNamed(wrapper, /Try again/).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('BTF-1')
  })
})

describe('sending', () => {
  it('sending to all confirms first, then reports how many went out', async () => {
    notifyMock.mockResolvedValueOnce({ sent: 1, pending: 0 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Send Email to All Groups/).trigger('click')
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.text()).toContain('every finalist team that has not been notified yet')

    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(notifyMock).toHaveBeenCalledWith(undefined)
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe('Sent 1 notification email.')
    expect(listMock).toHaveBeenCalledTimes(2) // roster refreshes after a send
  })

  it('the selected-teams button stays off until something is ticked', async () => {
    const wrapper = await mountPage()
    const selectedButton = buttonNamed(wrapper, /Send Email to Selected Groups/)
    expect(selectedButton.attributes('disabled')).toBeDefined()

    await wrapper.find('tbody input[type="checkbox"]').trigger('change')
    expect(selectedButton.attributes('disabled')).toBeUndefined()
  })

  it('sending to selected teams names the count and targets only them', async () => {
    notifyMock.mockResolvedValueOnce({ sent: 1, pending: 0 })
    const wrapper = await mountPage()
    await wrapper.find('tbody input[type="checkbox"]').trigger('change')
    await buttonNamed(wrapper, /Send Email to Selected Groups/).trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain('the 1 selected team.')

    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(notifyMock).toHaveBeenCalledWith([1])
  })

  it('explains a send that had nobody left to email', async () => {
    notifyMock.mockResolvedValueOnce({ sent: 0, pending: 0 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Send Email to All Groups/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toContain('No emails sent')
  })

  it('cancelling the dialog sends nothing', async () => {
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Send Email to All Groups/).trigger('click')
    await buttonNamed(wrapper, /^Cancel$/).trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(notifyMock).not.toHaveBeenCalled()
  })

  it('a refused send is reported and the dialog closes', async () => {
    notifyMock.mockRejectedValueOnce(new Error('email disabled'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Send Email to All Groups/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--error').text()).toContain('email disabled')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
})

describe('the email details', () => {
  it("the date pickers start at the server's today", async () => {
    const wrapper = await mountPage()
    for (const input of wrapper.findAll('input[type="date"]')) {
      expect(input.attributes('min')).toBe('2026-09-27')
    }
  })

  it('a date before today is only pointed out, above Save, once Save is pressed', async () => {
    saveMock.mockResolvedValueOnce(details())
    const wrapper = await mountPage()
    const [symposium] = wrapper.findAll('input[type="date"]')
    await symposium!.setValue('2026-09-26')
    // Nothing flagged while typing, and Save stays available.
    expect(symposium!.classes()).not.toContain('is-invalid')
    expect(wrapper.find('.notify-finalists__field-error').exists()).toBe(false)
    const save = buttonNamed(wrapper, /^Save$/)
    expect(save.attributes('disabled')).toBeUndefined()

    await save.trigger('click')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(symposium!.classes()).toContain('is-invalid')
    const message = wrapper.find('.notify-finalists__field-error')
    expect(message.text()).toBe("Symposium Date can't be before today.")
    // It sits just above the Save button.
    expect(message.element.nextElementSibling?.contains(save.element)).toBe(true)

    await symposium!.setValue('2026-09-27') // today is fine
    expect(wrapper.find('.notify-finalists__field-error').exists()).toBe(false)
    await save.trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledOnce()
  })

  it('a saved date that has since passed is flagged and blocks sending', async () => {
    detailsMock.mockResolvedValue(
      details({ confirm_by: '2025-10-05', dates_in_past: ['confirm_by'] })
    )
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__field-error').exists()).toBe(false)
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(
      'Some email dates are before today. Update and save them before sending.'
    )
    expect(buttonNamed(wrapper, /Send Email to All Groups/).attributes('disabled')).toBeDefined()

    // Saving other details names the passed dates, all of them, and saves nothing.
    await wrapper.findAll('input[type="date"]')[2]!.setValue('2026-09-01')
    await wrapper.find('input[type="url"]').setValue('https://events.example.com/new')
    await buttonNamed(wrapper, /^Save$/).trigger('click')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(wrapper.find('.notify-finalists__field-error').text()).toBe(
      "Confirm Attendance By and Slides Due can't be before today."
    )
  })

  it('shows the saved details, and no leftover under-construction banner', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).not.toContain('still being built')
    expect((wrapper.find('input[type="date"]').element as HTMLInputElement).value).toBe(
      '2026-10-23'
    )
    expect((wrapper.find('input[type="url"]').element as HTMLInputElement).value).toBe(
      'https://events.example.com/s'
    )
  })

  it('Save can always be pressed, and saves blanks as none', async () => {
    saveMock.mockResolvedValueOnce(details({ slides_due: null, complete: false }))
    const wrapper = await mountPage()
    const save = buttonNamed(wrapper, /^Save$/)
    expect(save.attributes('disabled')).toBeUndefined()

    await wrapper.findAll('input[type="date"]')[2]!.setValue('')
    await save.trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith({
      symposium_date: '2026-10-23',
      confirm_by: '2026-10-04',
      slides_due: null,
      registration_url: 'https://events.example.com/s'
    })
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe('Email details saved.')
  })

  it('Send stays off, saying why, while a detail is missing', async () => {
    detailsMock.mockResolvedValue(details({ slides_due: null, complete: false }))
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(
      'Fill in and save every email detail above before sending.'
    )
    expect(buttonNamed(wrapper, /Send Email to All Groups/).attributes('disabled')).toBeDefined()
  })

  it('Send stays off until an edit is saved', async () => {
    const wrapper = await mountPage()
    await wrapper.find('input[type="date"]').setValue('2026-10-30')
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(
      'Save the email details before sending.'
    )
    expect(buttonNamed(wrapper, /Send Email to All Groups/).attributes('disabled')).toBeDefined()
  })

  it('Preview shows the email for the details as typed, sending nothing', async () => {
    previewMock.mockResolvedValueOnce({
      subject: 'Congratulations',
      group_name: 'BTF-1',
      html: '<p>Dear members of BTF-1</p>'
    })
    const wrapper = await mountPage()
    await wrapper.find('input[type="date"]').setValue('2026-10-30')
    await buttonNamed(wrapper, /Preview Email/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith(
      expect.objectContaining({ symposium_date: '2026-10-30' })
    )
    const dialog = wrapper.find('[aria-label="Email preview"]')
    expect(dialog.text()).toContain('As the members of BTF-1 would get it')
    expect(dialog.find('iframe').attributes('srcdoc')).toContain('Dear members of BTF-1')
    expect(notifyMock).not.toHaveBeenCalled()

    await buttonNamed(wrapper, /^Close$/).trigger('click')
    expect(wrapper.find('[aria-label="Email preview"]').exists()).toBe(false)
  })
})
