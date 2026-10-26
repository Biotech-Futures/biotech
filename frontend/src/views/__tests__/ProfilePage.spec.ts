import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProfilePage from '@/views/ProfilePage.vue'
import { useAuthStore } from '@/stores/auth'
import { useGroupsStore } from '@/stores/groups'
import { setSupervisorPages } from '@/composables/useSupervisorPages'
import { formatDayMonthTime } from '@/utils/date'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import { setPicker } from '@/__tests__/appPicker'

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
      if (input.includes('supervisor-pages')) return new Response(JSON.stringify({
        shown: true, shown_from: '2020-01-01T00:00:00Z',
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
    expect(fields.indexOf('Pronouns:')).toBe(fields.indexOf('Area(s) of Interest:') + 1)

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
      'She/her', 'He/him', 'They/them', 'Other',
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

describe('Mentor profile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 5, email: 'mia@uni.example', first_name: 'Mia', last_name: 'Ng', current_role_name: 'mentor',
      pronouns: 'She/her', interests: ['Biomedical Innovations'],
      mentor_details: {
        mentorBackground: 'Undergraduate Student', mentorInstitution: 'University of Sydney', mentorCompany: '',
        mentorUniversityYear: '2', mentorFieldOfStudy: 'Biology', mentorMaxGroupCount: 2,
        mentorAvailability: [{ weekday: 0, start: '18:00', end: '19:30' }],
        mentorGroups: [{ id: 1, name: 'BTF1' }, { id: 3, name: 'BTF3' }],
      },
    } as never
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') return new Response(JSON.stringify(auth.user))
      if (String(input).includes('/registration/countries/')) return new Response(JSON.stringify({ countries: ['Australia', 'New Zealand'] }))
      if (String(input).includes('/registration/states/')) return new Response(JSON.stringify({ states: ['NSW', 'VIC'] }))
      if (String(input).includes('/registration/universities/')) {
        return new Response(JSON.stringify({ universities: ['Monash University', 'University of Sydney'] }))
      }
      return new Response(JSON.stringify([]))
    }))
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  const patchBody = () => {
    const call = vi.mocked(fetch).mock.calls.find(([, init]) => init?.method === 'PATCH')!
    expect(String(call[0])).toContain('/api/v1/users/me/mentor/')
    return JSON.parse(String(call[1]!.body))
  }

  it('edits their Mentor Details, clearing what their background no longer asks for', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('[data-test="mentor-details-edit"]').trigger('click')
    // An old typed background picks the list's choice it means.
    expect(appSelectText(wrapper, '[data-test="mentor-background"]')).toBe('Undergraduate')

    // Their name first, edited here too.
    expect((wrapper.get('[data-test="mentor-first-name"]').element as HTMLInputElement).value).toBe('Mia')
    // Their institution offers Management's universities as it's typed.
    await wrapper.get('[data-test="mentor-institution"]').setValue('syd')
    expect(wrapper.findAll('.app-suggest__option').map((option) => option.text())).toEqual(['University of Sydney'])

    await pickAppSelect(wrapper, '[data-test="mentor-background"]', 'Industry')
    await wrapper.get('[data-test="mentor-company"]').setValue('Acme Bio')
    await wrapper.get('[data-test="mentor-details-form"]').trigger('submit')
    await flushPromises()
    expect(patchBody()).toMatchObject({
      firstName: 'Mia', lastName: 'Ng',
      mentorBackground: 'industry', mentorCompany: 'Acme Bio', mentorInstitution: '', mentorUniversityYear: '',
      mentorFieldOfStudy: '', mentorMaxGroupCount: 2, pronouns: 'She/her',
    })
    expect(patchBody()).not.toHaveProperty('mentorWeeklyHours')
    wrapper.unmount()
  })

  it('edits their weekly times and their country and state', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await wrapper.get('[data-test="mentor-availability-edit"]').trigger('click')
    await wrapper.get('[data-test="mentor-add-slot"]').trigger('click')
    const slot = wrapper.find('[data-test="mentor-slot-1"]')
    await pickAppSelect(slot, '[aria-label="Day 2"]', 'Friday')
    await setPicker(wrapper, '[data-test="mentor-slot-1"] [aria-label="From, time 2"]', '09:00')
    await setPicker(wrapper, '[data-test="mentor-slot-1"] [aria-label="To, time 2"]', '10:00')
    await wrapper.get('[data-test="mentor-availability-form"]').trigger('submit')
    await flushPromises()
    expect(patchBody().mentorAvailability).toEqual([
      { weekday: 0, start: '18:00', end: '19:30' },
      { weekday: 4, start: '09:00', end: '10:00' },
    ])

    vi.mocked(fetch).mockClear()
    await wrapper.get('[data-test="mentor-place-edit"]').trigger('click')
    await flushPromises()
    // Country and State shown once: in the form, not also below it.
    expect(wrapper.text()).not.toContain('Country:')
    await pickAppSelect(wrapper, '[data-test="mentor-country"]', 'Australia')
    await flushPromises()
    await wrapper.get('[data-test="mentor-place-form"]').trigger('submit')
    expect(wrapper.text()).toContain('Choose your state or territory.')
    await pickAppSelect(wrapper, '[data-test="mentor-state"]', 'NSW')
    await wrapper.get('[data-test="mentor-place-form"]').trigger('submit')
    await flushPromises()
    expect(patchBody()).toEqual({ country: 'Australia', state: 'NSW' })
    wrapper.unmount()
  })

  it('shows their groups, details and weekly times as the admin panel does, without their answers', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()

    expect(wrapper.get('[data-test="mentor-groups"]').text()).toContain('BTF1, BTF3')
    const details = wrapper.get('[data-test="mentor-details"]').text()
    expect(wrapper.get('[data-test="mentor-name"]').text()).toContain('Mia Ng')
    // An old typed background, read as the list's choice: so its year shows.
    expect(details).toContain('Undergraduate')
    expect(details).toContain('Year 2')
    expect(details).toContain('2 groups')
    expect(details).not.toContain('Hours per week')
    expect(details).toContain('She/her')
    expect(wrapper.get('[data-test="mentor-availability"]').text()).toContain('Monday:18:00 to 19:30')
    expect(wrapper.text()).not.toContain('Mentor Reason')
    wrapper.unmount()
  })
})

describe('Admin profile', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 3, email: 'ada@biotech.example', first_name: 'Ada', last_name: 'Admin', current_role_name: 'admin',
      pronouns: '', country: { id: 2, countryName: 'New Zealand' }, state: null, account_status: 'active',
    } as never
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    vi.stubGlobal('fetch', vi.fn(async (input: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') return new Response(JSON.stringify(auth.user))
      if (String(input).includes('/registration/countries/')) return new Response(JSON.stringify({ countries: ['Australia', 'New Zealand'] }))
      return new Response(JSON.stringify([]))
    }))
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  const patched = () => vi.mocked(fetch).mock.calls.filter(([, init]) => init?.method === 'PATCH')

  it('shows and edits their Admin Details and their country and state', async () => {
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.get('[data-test="admin-name"]').text()).toContain('Ada Admin')

    await wrapper.get('[data-test="admin-details-edit"]').trigger('click')
    await pickAppSelect(wrapper, '[data-test="admin-pronouns"]', 'She/her')
    await wrapper.get('[data-test="admin-details-form"]').trigger('submit')
    await flushPromises()
    const [url, init] = patched()[0]!
    expect(String(url)).toContain('/api/v1/users/me/admin/')
    expect(JSON.parse(String(init!.body))).toEqual({ firstName: 'Ada', lastName: 'Admin', pronouns: 'She/her' })

    await wrapper.get('[data-test="mentor-place-edit"]').trigger('click')
    await flushPromises()
    // Their email and status here too, the rows they edit hidden meanwhile.
    expect(wrapper.text()).not.toContain('Account Status:')
    await wrapper.get('[data-test="admin-email"]').setValue('Adah@Biotech.example')
    await wrapper.get('[data-test="mentor-state-name"]').setValue('Otago')
    await pickAppSelect(wrapper, '[data-test="admin-status"]', 'Inactive')
    expect(wrapper.text()).toContain("you won't be able to sign in until another admin makes you Active again")
    await wrapper.get('[data-test="mentor-place-form"]').trigger('submit')
    await flushPromises()
    expect(JSON.parse(String(patched()[1]![1]!.body))).toEqual({
      email: 'adah@biotech.example', isActive: false, country: 'New Zealand', state: 'Otago',
    })
    wrapper.unmount()
  })
})

describe('Profile photo and timezone', () => {
  // The page's other reads, as for the student above; a test adds the photo
  // requests it answers.
  const stubFetch = (photo?: (init?: RequestInit) => Response) => {
    const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
      if (input.includes('profile-image') && photo) return photo(init)
      if (input.includes('profile-options')) return new Response(JSON.stringify({
        countries: [], regions: [], interests: [], selected_interest_ids: [],
      }))
      if (input.includes('group-members')) return new Response(JSON.stringify([]))
      return new Response(JSON.stringify({ results: [] }))
    })
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  const photoRequests = (fetchMock: ReturnType<typeof stubFetch>) =>
    fetchMock.mock.calls.filter(([input]) => String(input).includes('profile-image'))

  const openMenu = async (wrapper: ReturnType<typeof mount>) => {
    await wrapper.get('[data-test="profile-menu"]').trigger('click')
  }

  const pickFile = async (wrapper: ReturnType<typeof mount>, file: File) => {
    const input = wrapper.get('#profile-avatar')
    Object.defineProperty(input.element, 'files', { value: [file], configurable: true })
    await input.trigger('change')
    await flushPromises()
  }

  const png = () => new File(['png'], 'me.png', { type: 'image/png' })

  const button = (wrapper: ReturnType<typeof mount>, label: string) =>
    wrapper.findAll('button').find((b) => b.text() === label)!

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 1, email: 'student@example.org', first_name: 'Hiro', last_name: 'Bianchi',
      current_role_name: 'student', school_name: 'Test High', year_lvl: '10', timezone: 'Australia/Perth',
    }
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it('uploads a new photo picked from the menu, and shows it', async () => {
    const fetchMock = stubFetch(() => new Response(JSON.stringify({
      ...useAuthStore().user, profile_image_url: '/media/me.png',
    })))
    const changed = vi.fn()
    window.addEventListener('btf-profile-avatar-changed', changed)
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await openMenu(wrapper)
    // Only Change: there's no photo of their own to remove yet.
    expect(wrapper.find('[data-test="profile-photo-remove"]').exists()).toBe(false)
    const click = vi.spyOn(wrapper.get('#profile-avatar').element as HTMLInputElement, 'click')
    await wrapper.get('[data-test="profile-photo-change"]').trigger('click')
    expect(click).toHaveBeenCalled()
    expect(wrapper.find('.profile-menu__list').exists()).toBe(false)

    await pickFile(wrapper, png())
    const [request] = photoRequests(fetchMock)
    expect(request![1]!.method).toBe('POST')
    expect((request![1]!.body as FormData).get('image')).toBeInstanceOf(File)
    expect(wrapper.get('.status-card').text()).toBe('Profile picture uploaded successfully.')
    expect(wrapper.get('.profile-avatar-large').attributes('src')).toBe('/media/me.png')
    expect(changed).toHaveBeenCalled()
    window.removeEventListener('btf-profile-avatar-changed', changed)
    wrapper.unmount()
  })

  it('refuses a file that is not a small enough image, without uploading it', async () => {
    const fetchMock = stubFetch(() => new Response('{}'))
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await pickFile(wrapper, new File(['text'], 'notes.txt', { type: 'text/plain' }))
    expect(wrapper.text()).toContain('Choose a PNG, JPEG, or WebP image smaller than 5 MB.')
    const huge = new File(['x'], 'huge.png', { type: 'image/png' })
    Object.defineProperty(huge, 'size', { value: 6 * 1024 * 1024 })
    await pickFile(wrapper, huge)
    expect(wrapper.text()).toContain('Choose a PNG, JPEG, or WebP image smaller than 5 MB.')
    expect(photoRequests(fetchMock)).toHaveLength(0)
    wrapper.unmount()
  })

  it('says why an upload was refused', async () => {
    stubFetch(() => new Response(JSON.stringify({ image: ['That image is too wide.'] }), { status: 400 }))
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await pickFile(wrapper, png())
    expect(wrapper.text()).toContain('That image is too wide.')
    expect(wrapper.find('.status-card').exists()).toBe(false)

    stubFetch(() => new Response('<html>', { status: 500 }))
    await pickFile(wrapper, png())
    expect(wrapper.text()).toContain('Your profile picture could not be uploaded.')
    wrapper.unmount()
  })

  it('removes their own photo from the menu', async () => {
    Object.assign(useAuthStore().user!, { profile_image_url: '/media/old.png' })
    const fetchMock = stubFetch(() => new Response(JSON.stringify({
      ...useAuthStore().user, profile_image_url: null,
    })))
    const wrapper = mount(ProfilePage)
    await flushPromises()

    await openMenu(wrapper)
    await wrapper.get('[data-test="profile-photo-remove"]').trigger('click')
    await flushPromises()
    expect(photoRequests(fetchMock)[0]![1]!.method).toBe('DELETE')
    expect(wrapper.get('.status-card').text()).toBe('Profile picture removed.')
    // Their initials again.
    expect(wrapper.find('.profile-avatar-initials').exists()).toBe(true)
    wrapper.unmount()
  })

  it('says why a photo could not be removed', async () => {
    Object.assign(useAuthStore().user!, { profile_image_url: '/media/old.png' })
    stubFetch(() => new Response(JSON.stringify({ detail: 'Try again later.' }), { status: 503 }))
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await openMenu(wrapper)
    await wrapper.get('[data-test="profile-photo-remove"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Try again later.')
    expect(wrapper.find('.status-card').exists()).toBe(false)
    wrapper.unmount()
  })

  it("saves this device's timezone", async () => {
    stubFetch()
    const update = vi.spyOn(useAuthStore(), 'updateTimeZone').mockResolvedValue(undefined as never)
    const wrapper = mount(ProfilePage)
    await flushPromises()
    // Nothing to save while it's the one already saved.
    expect(button(wrapper, 'Save timezone').attributes('disabled')).toBeDefined()

    await button(wrapper, 'Use device timezone').trigger('click')
    expect(button(wrapper, 'Save timezone').attributes('disabled')).toBeUndefined()
    await button(wrapper, 'Save timezone').trigger('click')
    await flushPromises()
    expect(update).toHaveBeenCalledTimes(1)
    expect(update.mock.calls[0]![0]).not.toBe('Australia/Perth')
    expect(wrapper.get('.status-card').text()).toBe('Your timezone has been updated.')
    wrapper.unmount()
  })

  it('says why the timezone could not be saved', async () => {
    stubFetch()
    const update = vi.spyOn(useAuthStore(), 'updateTimeZone')
    update.mockRejectedValueOnce(new Error('The server is busy.'))
    const wrapper = mount(ProfilePage)
    await flushPromises()
    await button(wrapper, 'Use device timezone').trigger('click')
    await button(wrapper, 'Save timezone').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('The server is busy.')

    update.mockRejectedValueOnce('offline')
    await button(wrapper, 'Save timezone').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Your timezone could not be updated right now.')
    wrapper.unmount()
  })
})

describe('Supervisor profile: every group they are in (SP1)', () => {
  let myGroups: Response | Promise<Response>
  const fetchMock = vi.fn()
  const groupsRequests = () =>
    fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('page_size=100&mine=true'))
  const page = (...groups: [number, string][]) =>
    new Response(JSON.stringify({ results: groups.map(([id, group_name]) => ({ id, group_name })), next: null }))

  beforeEach(() => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = {
      id: 7, email: 'sam@example.org', first_name: 'Sam', last_name: 'Lee',
      current_role_name: 'supervisor', supervisor_school_name: 'Cardinal College', supervised_students: [],
    } as never
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    setSupervisorPages({ shown: true, shown_from: '2020-01-01T00:00:00Z' })
    myGroups = page()
    fetchMock.mockReset()
    fetchMock.mockImplementation(async (input: string) => {
      if (input.includes('supervisor-pages')) return new Response(JSON.stringify({
        shown: true, shown_from: '2020-01-01T00:00:00Z',
      }))
      if (input.includes('mine=true') && input.includes('page_size=100')) return myGroups
      return new Response(JSON.stringify({ results: [] }))
    })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  const mountProfile = async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/profile', name: 'profile', component: { template: '<div />' } },
        { path: '/groups/:id', name: 'group-detail', component: { template: '<div />' } },
      ],
    })
    await router.push('/profile')
    const wrapper = mount(ProfilePage, { global: { plugins: [router] } })
    await flushPromises()
    return wrapper
  }
  const section = (wrapper: Awaited<ReturnType<typeof mountProfile>>) => wrapper.find('[data-test="supervisor-groups"]')
  const links = (wrapper: Awaited<ReturnType<typeof mountProfile>>) =>
    section(wrapper).findAll('a').map((link) => [link.text(), link.attributes('href')])

  it('lists every group, each linking to its own group page, in natural order', async () => {
    myGroups = page([10, 'BTF10'], [5, 'BTF5'], [9, 'BTF9'])
    const wrapper = await mountProfile()
    expect(links(wrapper)).toEqual([['BTF5', '/groups/5'], ['BTF9', '/groups/9'], ['BTF10', '/groups/10']])
    expect(groupsRequests()).toHaveLength(1)
    wrapper.unmount()
  })

  it('shows a supervisor with one group exactly that group', async () => {
    myGroups = page([3, 'BTF3'])
    const wrapper = await mountProfile()
    expect(links(wrapper)).toEqual([['BTF3', '/groups/3']])
    wrapper.unmount()
  })

  it('says so when they are in no groups', async () => {
    const wrapper = await mountProfile()
    expect(section(wrapper).text()).toContain('You are not in any groups yet.')
    expect(section(wrapper).find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  it('shows loading until the groups arrive', async () => {
    let answer!: (response: Response) => void
    myGroups = new Promise((resolve) => { answer = resolve })
    const wrapper = await mountProfile()
    expect(section(wrapper).text()).toContain('Loading your groups')
    expect(section(wrapper).text()).not.toContain('not in any groups')
    answer(page([4, 'BTF4']))
    await flushPromises()
    expect(links(wrapper)).toEqual([['BTF4', '/groups/4']])
    wrapper.unmount()
  })

  it('says the groups could not be loaded, rather than that there are none', async () => {
    myGroups = new Response(JSON.stringify({ error: 'Server error', code: 'x', request_id: 'r' }), { status: 500 })
    const wrapper = await mountProfile()
    expect(section(wrapper).text()).toContain('Your groups could not be loaded.')
    expect(section(wrapper).text()).not.toContain('not in any groups')
    expect(section(wrapper).find('a').exists()).toBe(false)
    wrapper.unmount()
  })

  it('reuses groups already loaded this session', async () => {
    const groups = useGroupsStore()
    groups.groups = [
      { id: '12', name: 'BTF12', memberCount: 4, createdAt: '' },
      { id: '2', name: 'BTF2', memberCount: 3, createdAt: '' },
    ]
    groups.loaded = true
    const wrapper = await mountProfile()
    expect(links(wrapper)).toEqual([['BTF2', '/groups/2'], ['BTF12', '/groups/12']])
    expect(groupsRequests()).toEqual([])
    wrapper.unmount()
  })

  it('loads them once the profile turns out to be a supervisor', async () => {
    const auth = useAuthStore()
    const supervisor = auth.user
    auth.user = null
    myGroups = page([6, 'BTF6'])
    const wrapper = await mountProfile()
    expect(groupsRequests()).toEqual([])
    auth.user = supervisor
    await flushPromises()
    expect(links(wrapper)).toEqual([['BTF6', '/groups/6']])
    wrapper.unmount()
  })

  it('gives a supervisor no student Team members section', async () => {
    myGroups = page([5, 'BTF5'])
    const wrapper = await mountProfile()
    expect(wrapper.text()).not.toContain('Team members')
    expect(wrapper.find('.team-table').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('Groups on other profiles', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

  it.each(['student', 'mentor'])('a %s gets no Groups section and no group list request', async (role) => {
    setActivePinia(createPinia())
    const auth = useAuthStore()
    auth.user = { id: 8, email: 'x@example.org', first_name: 'Ana', last_name: 'Ruiz', current_role_name: role } as never
    vi.spyOn(auth, 'fetchUserData').mockResolvedValue(undefined)
    const fetchMock = vi.fn<(input: string) => Promise<Response>>(async () => new Response(JSON.stringify({ results: [] })))
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(ProfilePage)
    await flushPromises()
    expect(wrapper.find('[data-test="supervisor-groups"]').exists()).toBe(false)
    expect(fetchMock.mock.calls.map(([url]) => String(url)).filter((url) => url.includes('page_size=100'))).toEqual([])
    wrapper.unmount()
  })
})
