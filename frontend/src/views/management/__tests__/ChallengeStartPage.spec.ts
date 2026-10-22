import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import ChallengeStartPage from '@/views/management/ChallengeStartPage.vue'
import { pickerMax, pickerMin, pickerText, pickerValue, setPicker } from '@/__tests__/appPicker'
import {
  fetchChallengeStart,
  fetchRegistrationOpen,
  fetchSubmissionDeadline,
  saveChallengeStart,
} from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchChallengeStart: vi.fn(),
  saveChallengeStart: vi.fn(),
  // Registration's dates and the deadline, which it must come between.
  fetchRegistrationOpen: vi.fn(),
  fetchSubmissionDeadline: vi.fn(),
  // Release Resources, the page's second card.
  fetchResourceReleases: vi.fn().mockResolvedValue([]),
  saveResourceRelease: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

// Release Resources below it has its own spec (and reads the page's address).
const mountPage = () => mount(ChallengeStartPage, { global: { stubs: { ReleaseResourcesPage: true } } })

describe('Challenge Start', () => {
  it('shows the date and time and who set it, and saves or clears it', async () => {
    // 23:59 on 27 July here, wherever the spec runs.
    vi.mocked(fetchChallengeStart).mockResolvedValue({
      year: 2026,
      starts_at: new Date(2026, 6, 27, 23, 59).toISOString(),
      set_by: 'Test Admin',
      updated_at: '2026-10-04T01:25:00Z',
    })
    vi.mocked(saveChallengeStart)
      .mockResolvedValueOnce({
        year: 2026, starts_at: new Date(2026, 7, 3, 9, 0).toISOString(), set_by: 'Test Admin', updated_at: null,
      })
      .mockResolvedValueOnce({ year: 2026, starts_at: null, set_by: 'Test Admin', updated_at: null })
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('.card-title').text()).toBe('Challenge Start')
    expect(wrapper.get('[data-test="challenge-start-state"]').text()).toContain('27/07/2026 at 23:59')
    expect(wrapper.get('[data-test="challenge-start-set-by"]').text()).toMatch(/^Set by Test Admin on /)
    expect(pickerValue(wrapper, '[data-test="challenge-start-date"]')).toBe('2026-07-27T23:59')
    expect(pickerText(wrapper, '[data-test="challenge-start-date"]')).toBe('27 Jul 2026, 23:59')

    await setPicker(wrapper, '[data-test="challenge-start-date"]', '2026-08-03T09:00')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(saveChallengeStart).toHaveBeenLastCalledWith(new Date(2026, 7, 3, 9, 0).toISOString())

    await wrapper.findAll('button').find((button) => button.text() === 'Clear Date')!.trigger('click')
    await flushPromises()
    expect(saveChallengeStart).toHaveBeenLastCalledWith(null)
    expect(wrapper.get('[data-test="challenge-start-state"]').text()).toContain('Not set')
  })

  it('can only be after registration opens and before the deadline', async () => {
    vi.mocked(fetchChallengeStart).mockResolvedValue({ year: 2026, starts_at: null, set_by: '', updated_at: null })
    vi.mocked(fetchRegistrationOpen).mockResolvedValue({
      open_now: true, opens_at: new Date(2026, 1, 1, 9, 0).toISOString(), closes_at: null,
    })
    vi.mocked(fetchSubmissionDeadline).mockResolvedValue({
      deadline: { closes_at: new Date(2026, 9, 1, 23, 59).toISOString() },
    } as Awaited<ReturnType<typeof fetchSubmissionDeadline>>)
    const wrapper = mountPage()
    await flushPromises()

    // The minute after registration opens, and the minute before the deadline.
    expect(pickerMin(wrapper, '[data-test="challenge-start-date"]')).toBe('2026-02-01T09:01')
    expect(pickerMax(wrapper, '[data-test="challenge-start-date"]')).toBe('2026-10-01T23:58')
  })
})
