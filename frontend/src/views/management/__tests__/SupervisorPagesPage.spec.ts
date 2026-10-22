import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

import SupervisorPagesPage from '@/views/management/SupervisorPagesPage.vue'
import { useSupervisorPages } from '@/composables/useSupervisorPages'
import { fetchSupervisorPages, saveSupervisorPages } from '@/utils/managementAPI'

vi.mock('@/utils/managementAPI', () => ({
  fetchSupervisorPages: vi.fn(),
  saveSupervisorPages: vi.fn(),
}))

const later = new Date(Date.now() + 2 * 86_400_000).toISOString()
const earlier = new Date(Date.now() - 86_400_000).toISOString()

beforeEach(() => {
  vi.clearAllMocks()
})

describe('Pages Visibility (Challenge Start)', () => {
  it('says the pages are hidden while no date is set, for students, mentors and supervisors', async () => {
    vi.mocked(fetchSupervisorPages).mockResolvedValue({ shown: false, shown_from: null, set_by: '', updated_at: null })
    const wrapper = mount(SupervisorPagesPage)
    await flushPromises()

    expect(wrapper.get('.supervisor-pages__title').text()).toBe('Pages Visibility')
    expect(wrapper.text()).toContain('for students, supervisors and mentors')
    expect(wrapper.text()).toContain('students and mentors see their profile page')
    expect(wrapper.get('[data-test="pages-visibility-state"]').text()).toBe('Hidden: no date set')
    expect(wrapper.get('[data-test="pages-visibility-saved"]').text()).toContain('Shown from: Not set')
    // A date and time to set, not a switch.
    expect(wrapper.find('[data-test="pages-visibility-date"]').exists()).toBe(true)
    expect(wrapper.find('[role="switch"]').exists()).toBe(false)
  })

  it('saves the date, showing them hidden until then, and the menus follow', async () => {
    vi.mocked(fetchSupervisorPages).mockResolvedValue({ shown: false, shown_from: null })
    vi.mocked(saveSupervisorPages).mockResolvedValue({
      shown: false, shown_from: later, set_by: 'Test Admin', updated_at: earlier,
    })
    const wrapper = mount(SupervisorPagesPage)
    await flushPromises()

    const picker = wrapper.getComponent({ name: 'AppDateTimePicker' })
    picker.vm.$emit('update:modelValue', '2026-11-30T09:00')
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(saveSupervisorPages).toHaveBeenCalledWith({ shown_from: new Date('2026-11-30T09:00').toISOString() })
    expect(wrapper.get('[data-test="pages-visibility-state"]').text()).toMatch(/^Hidden until /)
    expect(wrapper.get('[data-test="pages-visibility-set-by"]').text()).toMatch(/^Set by Test Admin on /)
    expect(useSupervisorPages().shown.value).toBe(false)
  })

  it('shows them once the date has passed, and clears the date', async () => {
    vi.mocked(fetchSupervisorPages).mockResolvedValue({ shown: true, shown_from: earlier })
    vi.mocked(saveSupervisorPages).mockResolvedValue({ shown: false, shown_from: null })
    const wrapper = mount(SupervisorPagesPage)
    await flushPromises()

    expect(wrapper.get('[data-test="pages-visibility-state"]').text()).toBe(
      'Students, mentors and supervisors can see these pages',
    )
    expect(useSupervisorPages().shown.value).toBe(true)

    await wrapper.findAll('button').find((button) => button.text() === 'Clear Date')!.trigger('click')
    await flushPromises()
    expect(saveSupervisorPages).toHaveBeenCalledWith({ shown_from: null })
    expect(wrapper.get('[data-test="pages-visibility-state"]').text()).toBe('Hidden: no date set')
    expect(useSupervisorPages().shown.value).toBe(false)
  })
})
