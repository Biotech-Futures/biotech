import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import ChallengeStartPage from '@/views/management/ChallengeStartPage.vue'
import { pickerText, pickerValue, setPicker } from '@/__tests__/appPicker'
import { fetchChallengeStart, saveChallengeStart } from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchChallengeStart: vi.fn(),
  saveChallengeStart: vi.fn(),
  // Pages Visibility, the page's second card.
  fetchSupervisorPages: vi.fn().mockResolvedValue({ shown: true, shown_from: '2026-07-27T00:00:00Z' }),
  saveSupervisorPages: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Challenge Start', () => {
  it('shows the date and who set it, and saves or clears it', async () => {
    vi.mocked(fetchChallengeStart).mockResolvedValue({
      year: 2026,
      starts_on: '2026-07-27',
      set_by: 'Test Admin',
      updated_at: '2026-10-04T01:25:00Z',
    })
    vi.mocked(saveChallengeStart)
      .mockResolvedValueOnce({ year: 2026, starts_on: '2026-08-03', set_by: 'Test Admin', updated_at: null })
      .mockResolvedValueOnce({ year: 2026, starts_on: null, set_by: 'Test Admin', updated_at: null })
    const wrapper = mount(ChallengeStartPage)
    await flushPromises()

    expect(wrapper.get('.card-title').text()).toBe('Challenge Start')
    // Then what supervisors see, moved here from Late Registration.
    expect(wrapper.get('.supervisor-pages__title').text()).toBe('Pages Visibility')
    expect(wrapper.get('[data-test="challenge-start-state"]').text()).toContain('27 July 2026')
    expect(wrapper.get('[data-test="challenge-start-set-by"]').text()).toMatch(/^Set by Test Admin on /)
    expect(pickerValue(wrapper, '[data-test="challenge-start-date"]')).toBe('2026-07-27')
    expect(pickerText(wrapper, '[data-test="challenge-start-date"]')).toBe('27 Jul 2026')

    await setPicker(wrapper, '[data-test="challenge-start-date"]', '2026-08-03')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(saveChallengeStart).toHaveBeenLastCalledWith('2026-08-03')

    await wrapper.findAll('button').find((button) => button.text() === 'Clear Date')!.trigger('click')
    await flushPromises()
    expect(saveChallengeStart).toHaveBeenLastCalledWith(null)
    expect(wrapper.get('[data-test="challenge-start-state"]').text()).toContain('Not set')
  })
})
