import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import ProfilePage from '@/views/ProfilePage.vue'
import { useAuthStore } from '@/stores/auth'
import { formatDayMonthTime } from '@/utils/date'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'

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

  it('needs a state in Australia, with no Not set to pick', async () => {
    Object.assign(useAuthStore().user!, { country: { id: 1, countryName: 'Australia' }, state: null })
    const wrapper = mount(ProfilePage)
    await flushPromises()
    // Country and region are edited under Personal Information.
    await wrapper.get('[data-test="place-edit"]').trigger('click')
    await flushPromises()

    expect(await appSelectLabels(wrapper, '[data-test="student-region"]')).toEqual(['NSW'])
    await wrapper.get('[data-test="place-edit-form"]').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Choose your state or territory.')
    wrapper.unmount()
  })

  it('loads edit choices: geography under Personal Information, interests under Student Details', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('[data-test="place-edit"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-test="place-edit-form"]').text()).toContain('Australia')
    await wrapper.get('[data-test="place-edit-form"]').findAll('button').find((b) => b.text() === 'Cancel')!.trigger('click')

    const details = wrapper.find('[data-test="student-details-edit"]')
    await details.trigger('click')
    await flushPromises()
    const form = wrapper.get('.student-edit-form')
    expect(form.text()).toContain('Biology')
    expect(form.text()).not.toContain('Country')
    expect(form.findAll('input[type="checkbox"]')).toHaveLength(1)
    wrapper.unmount()
  })

  it('lists interests as text with pronouns after, and the supervisor in a section of its own', async () => {
    Object.assign(useAuthStore().user!, {
      interests: ['Genomics', 'Molecular Biology'], pronouns: 'She/her',
      supervisor_name: 'Grace Green', supervisor_email: 'grace@school.edu',
    })
    const wrapper = mount(ProfilePage)
    await flushPromises()

    expect(wrapper.get('[data-test="student-interests"]').text()).toContain('Genomics, Molecular Biology')
    expect(wrapper.find('.profile-interest').exists()).toBe(false)
    expect(wrapper.get('[data-test="student-pronouns"]').text()).toContain('She/her')
    const fields = wrapper.findAll('.profile-field-label').map((label) => label.text())
    expect(fields.indexOf('Pronouns:')).toBe(fields.indexOf('Areas of Interest:') + 1)

    const supervisor = wrapper.get('[data-test="student-supervisor"]')
    expect(supervisor.get('.profile-section-title').text()).toBe('Supervisor Details')
    expect(supervisor.text()).toContain('Grace Green')
    expect(supervisor.get('a').attributes('href')).toBe('mailto:grace@school.edu')
    // No longer among the student's own details.
    expect(wrapper.get('[data-test="student-interests"]').element.parentElement!.textContent).not.toContain('Supervisor Email:')
    wrapper.unmount()
  })

  it('edits pronouns as registering offers them, bringing their own back under Other', async () => {
    Object.assign(useAuthStore().user!, { pronouns: 'Xe/xem' })
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('[data-test="student-details-edit"]').trigger('click')
    await flushPromises()

    expect(appSelectText(wrapper, '[data-test="student-pronouns-select"]')).toBe('Other')
    expect((wrapper.get('[data-test="student-pronouns-other"]').element as HTMLInputElement).value).toBe('Xe/xem')
    expect(await appSelectLabels(wrapper, '[data-test="student-pronouns-select"]')).toEqual([
      'Not set', 'She/her', 'He/him', 'They/them', 'Prefer not to say', 'Other',
    ])

    await pickAppSelect(wrapper, '[data-test="student-pronouns-select"]', 'They/them')
    expect(wrapper.find('[data-test="student-pronouns-other"]').exists()).toBe(false)
    await wrapper.get('.student-edit-form').trigger('submit')
    await flushPromises()
    const patch = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'PATCH')!
    expect(JSON.parse(String(patch[1]!.body)).pronouns).toBe('They/them')
    wrapper.unmount()
  })

  it('asks for their pronouns when Other is left empty', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('[data-test="student-details-edit"]').trigger('click')
    await flushPromises()

    await pickAppSelect(wrapper, '[data-test="student-pronouns-select"]', 'Other')
    await wrapper.get('.student-edit-form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Enter your pronouns.')
    expect(vi.mocked(fetch).mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false)
    wrapper.unmount()
  })

  it('locks a student their supervisor registered or edited, naming the supervisor', async () => {
    Object.assign(useAuthStore().user!, {
      supervisor_id: 9, details_locked: true, supervisor_name: 'Grace Green', supervisor_email: 'grace@school.edu',
    })
    const wrapper = mount(ProfilePage)
    await flushPromises()
    // Their details and their country and region are their supervisor's to change.
    expect(wrapper.find('[data-test="student-details-edit"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="place-edit"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="details-lock"]').attributes('data-tooltip')).toBe(
      'Your supervisor, Grace Green (grace@school.edu), manages these details. Contact them to make changes.'
    )
    // Guardian details stay the student's to change.
    expect(wrapper.find('[data-test="guardian-edit"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('leaves a student who registered themselves free to edit, supervisor or not', async () => {
    Object.assign(useAuthStore().user!, { supervisor_id: 9, details_locked: false })
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('.profile-edit-button').exists()).toBe(true)
    expect(wrapper.find('[data-test="details-lock"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('explains why sending is unavailable and does not invent reminder dates', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe('Not received, Invitations are not configured.')
    expect(wrapper.find('[data-test="guardian-send"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="guardian-reminders"]').text()).toBe('Not emailed yet.')
    wrapper.unmount()
  })

  it('sends the consent email from the link, then says when it can be sent again', async () => {
    const auth = useAuthStore()
    auth.user!.guardian_reminder = { last_sent_at: null, next_due_at: null, can_send: true, unavailable_reason: '' }
    const student = { ...auth.user! }
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await wrapper.find('[data-test="guardian-send"]').trigger('click')
    await flushPromises()
    expect(vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes('/users/me/guardian-invitation/'))).toBe(true)

    // The profile as the server returns it after sending, two and a half minutes on.
    auth.user = {
      ...student,
      guardian_reminder: {
        last_sent_at: new Date(Date.now() - 2.5 * 60 * 1000).toISOString(), next_due_at: null, can_send: false,
        unavailable_reason: 'An invitation was sent recently. Please wait 10 minutes before resending.',
      },
    }
    await flushPromises()
    expect(wrapper.find('[data-test="guardian-consent"]').text()).toBe(
      'Not received, emailed guardian@example.org, you can send it again in 8 minutes'
    )
    wrapper.unmount()
  })

  it('shows what went wrong with a send at the bottom of Guardian Details', async () => {
    const auth = useAuthStore()
    auth.user!.guardian_reminder = { last_sent_at: null, next_due_at: null, can_send: true, unavailable_reason: '' }
    const message = "The mail server didn't accept the email. Try again shortly."
    const fallback = vi.mocked(fetch).getMockImplementation()!
    vi.mocked(fetch).mockImplementation(async (input, init) =>
      String(input).includes('guardian-invitation')
        // As the server's error handler sends it.
        ? new Response(JSON.stringify({ error: message, code: 'invalid' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
        : fallback(input, init)
    )
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await wrapper.find('[data-test="guardian-send"]').trigger('click')
    await flushPromises()

    const section = wrapper.find('[data-test="guardian-details"]')
    const notice = section.find('[data-test="guardian-notice"]')
    expect(notice.text()).toBe(message)
    expect(notice.classes()).toContain('guardian-notice--error')
    // The last thing in the section, not the top of the page.
    expect(section.element.lastElementChild).toBe(notice.element)
    expect(wrapper.text().indexOf(message)).toBe(wrapper.text().lastIndexOf(message))
    wrapper.unmount()
  })

  it('folds the reminders into one line under Permission', async () => {
    const auth = useAuthStore()
    const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
    auth.user!.guardian_reminder = {
      last_sent_at: '2026-09-14T03:00:00Z', next_due_at: tomorrow, can_send: true, unavailable_reason: '',
    }
    const wrapper = mount(ProfilePage)
    await flushPromises()

    expect(wrapper.find('[data-test="guardian-reminders"]').text()).toBe(
      `Last emailed ${formatDayMonthTime('2026-09-14T03:00:00Z')}. They'll be emailed again tomorrow.`
    )
    expect(wrapper.text()).not.toContain('Last reminder email sent')
    wrapper.unmount()
  })
})

describe('Supervisor profile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 9, email: 'grace@school.edu', first_name: 'Grace', last_name: 'Green',
      current_role_name: 'supervisor', supervisor_school_name: 'Test High', pronouns: 'She/her',
    }
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn(async (_input: string, init?: RequestInit) =>
      new Response(JSON.stringify(init?.method === 'PATCH' ? { ...auth.user, ...JSON.parse(String(init.body)) } : [])),
    ))
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('shows their pronouns after their school, and edits them with their name', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.get('[data-test="supervisor-pronouns"]').text()).toContain('She/her')

    await wrapper.findAll('button').find((button) => button.text() === 'Edit')!.trigger('click')
    await pickAppSelect(wrapper, '[data-test="supervisor-pronouns-select"]', 'They/them')
    await wrapper.get('.student-edit-form').trigger('submit')
    await flushPromises()

    const patch = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'PATCH')!
    expect(JSON.parse(String(patch[1]!.body))).toMatchObject({ first_name: 'Grace', last_name: 'Green', pronouns: 'They/them' })
    wrapper.unmount()
  })
})
