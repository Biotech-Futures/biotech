import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NotifyFinalistsPage from '@/views/grading/NotifyFinalistsPage.vue'
import { fetchFinalists, notifyFinalists } from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchFinalists: vi.fn(),
  notifyFinalists: vi.fn()
}))
const listMock = vi.mocked(fetchFinalists)
const notifyMock = vi.mocked(notifyFinalists)

const finalist = (group_id: number, over: Record<string, unknown> = {}) => ({
  group_id,
  group_name: `BTF-${group_id}`,
  flagged_at: '2026-09-01T00:00:00Z',
  flagged_by: 'Ada Admin',
  notified: false,
  notified_at: null,
  notified_by: null,
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
