import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ProfilePage from '@/views/ProfilePage.vue'
import { useAuthStore } from '@/stores/auth'

vi.mock('@/utils/csrf', () => ({
  buildSessionHeaders: () => ({ 'Content-Type': 'application/json' }),
  ensureCsrfCookie: async () => true,
}))

describe('Student profile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 1, email: 'student@example.org', first_name: 'Hiro', last_name: 'Bianchi',
      current_role_name: 'student', school_name: 'Test High', year_lvl: '10',
      pg_firstname: 'Pat', pg_lastname: 'Bianchi', pg_email: 'guardian@example.org',
      guardian_reminder: { last_sent_at: null, next_due_at: null, can_send: false, unavailable_reason: 'Invitations are not configured.' },
    }
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn(async (input: string) => {
      if (input.includes('profile-options')) return new Response(JSON.stringify({
        countries: [{ id: 1, country_name: 'Australia' }],
        regions: [{ id: 2, country_id: 1, state_name: 'NSW' }],
        interests: [{ id: 3, interest_desc: 'Biology' }], selected_interest_ids: [],
      }))
      if (input.includes('group-members')) return new Response(JSON.stringify([
        { id: 1, membership_role: 'student', student_details: { first_name: 'Hiro', last_name: 'Bianchi', year_level: '10', school: 'Test High', supervisor: 'Grace Green' } },
        { id: 2, membership_role: 'mentor', student_details: null },
      ]))
      return new Response(JSON.stringify({ results: [{ id: 10, group_name: 'Test Team' }] }))
    }))
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('shows initials, student name and expanded team columns without status', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.get('.profile-avatar-initials').text()).toBe('HB')
    expect(wrapper.get('.team-table').text()).toContain('Grace Green')
    expect(wrapper.findAll('.team-table th').map(cell => cell.text())).toEqual(['First name', 'Last name', 'Year level', 'School', 'Supervisor'])
    expect(wrapper.findAll('.team-table tbody tr')).toHaveLength(1)
    expect(wrapper.text()).toContain('Name:')
    wrapper.unmount()
  })

  it('loads edit choices for geography and interests', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('.profile-edit-button').trigger('click')
    await flushPromises()
    const form = wrapper.get('.student-edit-form')
    expect(form.text()).toContain('Australia')
    expect(form.text()).toContain('Biology')
    expect(form.findAll('input[type="checkbox"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('locks supervisor-linked profiles even when the supervisor email is missing', async () => {
    useAuthStore().user!.supervisor_id = 9
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('.profile-edit-button').exists()).toBe(false)
    expect(wrapper.find('.registration-lock').exists()).toBe(true)
    wrapper.unmount()
  })

  it('explains why sending is unavailable and does not invent reminder dates', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.text()).toContain('Invitations are not configured.')
    expect(wrapper.text()).toContain('No automatic reminder scheduled')
    const resend = wrapper.findAll('button').find(button => button.text() === 'Resend guardian invitation')!
    expect(resend.attributes('disabled')).toBeDefined()
    wrapper.unmount()
  })
})
