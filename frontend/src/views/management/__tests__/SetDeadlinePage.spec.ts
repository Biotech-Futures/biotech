import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import SetDeadlinePage from '@/views/management/SetDeadlinePage.vue'
import { fetchSubmissionDeadline, saveSubmissionDeadline } from '@/utils/managementAPI'
import { dateTimeFieldsValue, setDateTimeFields } from '@/__tests__/appPicker'

vi.mock('@/utils/managementAPI', () => ({
  fetchSubmissionDeadline: vi.fn(),
  saveSubmissionDeadline: vi.fn()
}))
const fetchMock = vi.mocked(fetchSubmissionDeadline)
const saveMock = vi.mocked(saveSubmissionDeadline)

const NOW = new Date('2026-09-23T12:00:00Z')

const deadline = (over: Record<string, unknown> = {}) => ({
  closes_at: '2026-10-30T13:00:00Z',
  grace_hours: 6,
  is_open: true,
  set_by: 'Ada Admin',
  created_at: '2026-09-01T00:00:00Z',
  ...over
})

const mountPage = async () => {
  const wrapper = mount(SetDeadlinePage)
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
  fetchMock.mockReset()
  saveMock.mockReset()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('the current-deadline card', () => {
  it('says submissions are closed when no deadline exists', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: null })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('No deadline set')
    expect(wrapper.text()).toContain('closed')
    expect(wrapper.find('.card-title').text()).toBe('Submission Deadline')
  })

  it('shows an open future deadline with its grace and author', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: deadline() })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Submissions open')
    expect(wrapper.text()).toContain('(+ 6h quiet grace)')
    expect(wrapper.text()).toContain('Set by Ada Admin')
    // The picker is pre-filled with the stored closing time.
    expect(dateTimeFieldsValue(wrapper, '.sydney-date-time')).not.toBe('')
  })

  it('reports the quiet grace period once the announced time has passed', async () => {
    fetchMock.mockResolvedValueOnce({
      deadline: deadline({ closes_at: '2026-09-23T10:00:00Z', grace_hours: 6 })
    })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Submission in grace period')
  })

  it('reports closed once the grace has run out too', async () => {
    fetchMock.mockResolvedValueOnce({
      deadline: deadline({ closes_at: '2026-09-20T10:00:00Z', grace_hours: 6 })
    })
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Submissions closed')
  })

  it('offers a retry when the load fails', async () => {
    fetchMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load.')

    fetchMock.mockResolvedValueOnce({ deadline: deadline() })
    await wrapper.find('button.btn-outline').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Submissions open')
  })
})

describe('setting a deadline', () => {
  const fillAndSubmit = async (wrapper: Awaited<ReturnType<typeof mountPage>>) => {
    await setDateTimeFields(wrapper, '.sydney-date-time', '2026-11-01T09:00')
    await wrapper.find('form').trigger('submit')
  }

  it('asks in-page before saving, naming the picked time', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: null })
    const wrapper = await mountPage()
    await fillAndSubmit(wrapper)
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.exists()).toBe(true)
    expect(dialog.text()).toContain('Set the submission deadline?')
    // Read back in Sydney's time, as it was picked.
    expect(dialog.text()).toContain('01/11/2026 at 09:00 AEDT')
    expect(saveMock).not.toHaveBeenCalled()
  })

  it('cancelling the dialog saves nothing', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: null })
    const wrapper = await mountPage()
    await fillAndSubmit(wrapper)
    await wrapper.find('[role="dialog"] .btn-outline').trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(saveMock).not.toHaveBeenCalled()
  })

  it('confirming saves the UTC instant with the grace hours', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: null })
    saveMock.mockResolvedValueOnce({ deadline: deadline() })
    const wrapper = await mountPage()
    await fillAndSubmit(wrapper)
    await wrapper.find('[role="dialog"] .btn-primary').trigger('click')
    await flushPromises()
    // 09:00 in Sydney (AEDT, UTC+11), whatever the computer's time zone.
    expect(saveMock).toHaveBeenCalledWith('2026-10-31T22:00:00.000Z', 24)
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Submissions open')
    expect(wrapper.text()).toContain('Closes:')
  })

  it('a refused save is reported under the form', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: null })
    saveMock.mockRejectedValueOnce(new Error('closes_at must be in the future'))
    const wrapper = await mountPage()
    await fillAndSubmit(wrapper)
    await wrapper.find('[role="dialog"] .btn-primary').trigger('click')
    await flushPromises()
    expect(wrapper.find('.deadline__banner--error').text()).toContain('closes_at must be in the future')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })

  it('defaults the closing time to today at 23:59, and clearing it blocks submit', async () => {
    fetchMock.mockResolvedValueOnce({ deadline: null })
    const wrapper = await mountPage()
    expect(dateTimeFieldsValue(wrapper, '.sydney-date-time')).toMatch(/T23:59$/)
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined()

    await setDateTimeFields(wrapper, '.sydney-date-time', '')
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })
})
