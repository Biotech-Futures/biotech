import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import ChallengeStartPage from '@/views/management/ChallengeStartPage.vue'
import { dateTimeFieldsLimit, dateTimeFieldsValue, pickerText, pickerValue, setDateTimeFields } from '@/__tests__/appPicker'
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
  // Pages Visibility, the page's second card.
  fetchSupervisorPages: vi.fn().mockResolvedValue({ shown: true, shown_from: '2026-07-27T00:00:00Z' }),
  saveSupervisorPages: vi.fn(),
  // Release Resources, its third.
  fetchResourceReleases: vi.fn().mockResolvedValue([]),
  saveResourceRelease: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

// Release Resources below it has its own spec (and reads the page's address).
const mountPage = () => mount(ChallengeStartPage, { global: { stubs: { ReleaseResourcesPage: true } } })

describe('Challenge Start', () => {
  it('shows the date and time and who set it, and saves it', async () => {
    // 23:59 on 27 July in Sydney (AEST), wherever the spec runs.
    vi.mocked(fetchChallengeStart).mockResolvedValue({
      year: 2026,
      starts_at: '2026-07-27T13:59:00Z',
      set_by: 'Test Admin',
      updated_at: '2026-10-04T01:25:00Z',
    })
    vi.mocked(saveChallengeStart)
      .mockResolvedValueOnce({
        year: 2026, starts_at: '2026-08-02T23:00:00.000Z', set_by: 'Test Admin', updated_at: null,
      })
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('.card-title').text()).toBe('Challenge Start')
    // Then what supervisors see, moved here from Late Registration.
    expect(wrapper.get('.supervisor-pages__title').text()).toBe('Pages Visibility')
<<<<<<< HEAD
    expect(wrapper.get('[data-test="challenge-start-state"]').text()).toContain('27/07/2026 at 23:59')
=======
    expect(wrapper.get('[data-test="challenge-start-state"]').text()).toContain('27/07/2026 at 23:59 AEST')
>>>>>>> admin-management
    expect(wrapper.get('[data-test="challenge-start-set-by"]').text()).toMatch(/^Set by Test Admin on /)
    // Its date and time apart, in Sydney's time, its clock named.
    expect(dateTimeFieldsValue(wrapper, '[data-test="challenge-start-date"]')).toBe('2026-07-27T23:59')
    expect(pickerText(wrapper, '[data-test="challenge-start-date"] .sydney-date-time__date')).toBe('27 Jul 2026')
    expect(pickerText(wrapper, '[data-test="challenge-start-date"] .sydney-date-time__time')).toBe('23:59')
    const labels = wrapper.findAll('[data-test="challenge-start-date"] .sydney-date-time__field > span')
    expect(labels.map((label) => label.text())).toEqual(['Start Date', 'Time (AEST)'])

    await setDateTimeFields(wrapper, '[data-test="challenge-start-date"]', '2026-08-03T09:00')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    // 09:00 in Sydney (AEST, UTC+10), whatever the computer's time zone.
    expect(saveChallengeStart).toHaveBeenLastCalledWith('2026-08-02T23:00:00.000Z')

    // Saved only: there's no clearing it here.
    expect(wrapper.get('.challenge-start').findAll('button').map((button) => button.text())).not.toContain('Clear Date')
  })

  it('can only be after registration opens and before the deadline', async () => {
    vi.mocked(fetchChallengeStart).mockResolvedValue({ year: 2026, starts_at: null, set_by: '', updated_at: null })
    vi.mocked(fetchRegistrationOpen).mockResolvedValue({
      open_now: true, opens_at: '2026-01-31T22:00:00Z', closes_at: null,
    })
    vi.mocked(fetchSubmissionDeadline).mockResolvedValue({
      deadline: { closes_at: '2026-10-01T13:59:00Z' },
    } as Awaited<ReturnType<typeof fetchSubmissionDeadline>>)
    const wrapper = mountPage()
    await flushPromises()

    // Not set yet, its time is the start of the day: 00:01.
    expect(pickerValue(wrapper, '[data-test="challenge-start-date"] .sydney-date-time__time')).toBe('00:01')
    // The minute after registration opens, and the minute before the deadline, in Sydney.
    expect(dateTimeFieldsLimit(wrapper, '[data-test="challenge-start-date"]', 'min')).toBe('2026-02-01T09:01')
    expect(dateTimeFieldsLimit(wrapper, '[data-test="challenge-start-date"]', 'max')).toBe('2026-10-01T23:58')
  })
})
