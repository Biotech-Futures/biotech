import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailSheet from '../AdminUserDetailSheet.vue'
import {
  changeSupervisees,
  confirmMentorAssignments,
  createAdminUser,
  confirmStudentAssignments,
  downloadGuardianConsentRecord,
  fetchAdminCountries,
  fetchAdminGroupList,
  fetchAdminStates,
  fetchAdminUser,
  fetchAdminUsers,
  fetchGuardianConsents,
  removeGroupMember,
  sendGuardianConsentRequest,
  removeAdminUserPhoto,
  setAdminUserActive,
  unassignMentors,
  updateAdminUser,
  uploadAdminUserPhoto
} from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'
import { appSelectLabels, appSelectText, openAppSelect, pickAppSelect } from '@/__tests__/appSelect'
import { pickerText, setPicker } from '@/__tests__/appPicker'
import type { AdminGroupDetail, AdminUser } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', async (importOriginal) => ({
  // The real wording said before activating a student from an earlier year.
  earlierYearMessage: (await importOriginal<typeof import('@/utils/adminAPI')>()).earlierYearMessage,
  createAdminUser: vi.fn(),
  checkAdminUserEmails: vi.fn(async () => ({})),
  updateAdminUser: vi.fn().mockResolvedValue({ msg: 'ok', data: null }),
  setAdminUserActive: vi.fn(),
  sendGuardianConsentRequest: vi.fn(),
  fetchGuardianConsents: vi.fn(),
  downloadGuardianConsentRecord: vi.fn(),
  fetchAdminUsers: vi.fn(),
  fetchAdminUser: vi.fn(),
  fetchAdminGroupList: vi.fn(),
  confirmStudentAssignments: vi.fn(),
  removeGroupMember: vi.fn(),
  confirmMentorAssignments: vi.fn(),
  changeSupervisees: vi.fn(),
  unassignMentors: vi.fn(),
  fetchAdminCountries: vi.fn(),
  fetchAdminStates: vi.fn(),
  uploadAdminUserPhoto: vi.fn(),
  removeAdminUserPhoto: vi.fn()
}))

const student = (overrides: Partial<AdminUser> = {}): AdminUser => ({
  id: 7,
  firstName: 'Wren',
  lastName: 'Ward',
  email: 'ward@example.com',
  role: 'student',
  country: { id: 1, countryName: 'Australia' },
  state: null,
  groupId: null,
  groupName: null,
  schoolName: 'Test High',
  mentorBackground: null,
  mentorInstitution: null,
  mentorReason: null,
  mentorMaxGroupCount: null,
  yearLevel: 10,
  guardianFirstName: 'Pat',
  guardianLastName: 'Parent',
  guardianEmail: 'pat@example.com',
  joinPermissionReceived: false,
  joinpermResponseId: null,
  joinPermissionGrantedAt: null,
  pendingGuardian: null,
  mediaConsent: null,
  consentRequestSentAt: null,
  interests: ['Biomedical Innovations'],
  isAdmin: false,
  isActive: true,
  hasLoggedIn: false,
  lastLogin: null,
  accountStatus: 'active',
  invitedAt: null,
  activatedAt: null,
  supervisorName: null,
  supervisorEmail: null,
  supervisees: [],
  ...overrides
})

async function openForm(user: AdminUser) {
  const wrapper = mount(AdminUserFormSheet, {
    props: {
      modelValue: false,
      userNoun: 'Student',
      user,
      isSupervisorMode: false,
      countries: [{ id: 1, countryName: 'Australia' }],
      states: [],
      supervisors: []
    },
    global: { stubs: { teleport: true } }
  })
  // The form fills itself in when the sheet opens.
  await wrapper.setProps({ modelValue: true })
  return wrapper
}

async function save(wrapper: Awaited<ReturnType<typeof openForm>>) {
  await wrapper.find('form').trigger('submit')
  await flushPromises()
  return vi.mocked(updateAdminUser).mock.calls.at(-1)?.[1] as Record<string, unknown> | undefined
}

const GUARDIAN_KEYS = ['guardianFirstName', 'guardianLastName', 'guardianEmail', 'joinpermResponseId']

describe('admin user form: adding a user', () => {
  const openAdd = async () => {
    const wrapper = mount(AdminUserFormSheet, {
      props: {
        modelValue: false,
        userNoun: 'User',
        user: null,
        isSupervisorMode: false,
        countries: [
          { id: 1, countryName: 'Australia' },
          { id: 2, countryName: 'New Zealand' }
        ],
        states: [{ id: 5, stateName: 'NSW', countryName: 'Australia' }],
        supervisors: [student({ id: 9, firstName: 'Grace', lastName: 'Green', email: 'grace@school.edu', role: 'supervisor' })]
      },
      global: { stubs: { teleport: true } }
    })
    await wrapper.setProps({ modelValue: true })
    return wrapper
  }

  beforeEach(() => {
    vi.mocked(createAdminUser).mockReset()
    vi.mocked(confirmStudentAssignments).mockReset()
    vi.mocked(fetchAdminGroupList).mockResolvedValue({
      items: [
        { id: '3', name: 'BTF3', members: [] },
        { id: '4', name: 'BTF4', members: Array.from({ length: 5 }, (_, i) => ({ id: i, role: 'student' })) }
      ],
      has_more: false
    } as never)
  })

  it('puts a new student in the group picked, once added', async () => {
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: student({ id: 42 }) })
    vi.mocked(confirmStudentAssignments).mockResolvedValue({ msg: 'ok', assignedCount: 1 })
    const wrapper = await openAdd()
    await flushPromises()

    const sections = wrapper.findAll('.admin-users-form__section').map((section) => section.text())
    expect(sections).toEqual(['Account', 'Student details', 'Supervisor and Group', 'Guardian & consent', 'Profile Photo'])
    // A full group can't be picked.
    const full = (await openAppSelect(wrapper, '#f-group')).find((option) => option.textContent!.includes('BTF4'))!
    expect(full.getAttribute('aria-disabled')).toBe('true')

    await wrapper.find('#f-first').setValue('Wren')
    await wrapper.find('#f-last').setValue('Ward')
    await wrapper.find('#f-email').setValue('wren@example.com')
    await pickAppSelect(wrapper, '#f-country', 'Australia')
    await pickAppSelect(wrapper, '#f-state', 'NSW')
    await wrapper.find('#f-school').setValue('Test High')
    await pickAppSelect(wrapper, '#f-year', '11')
    await pickAppSelect(wrapper, '#f-group', 'BTF3')
    await pickAppSelect(wrapper, '#f-supervisor', 'Grace Green')
    await pickAppSelect(wrapper, '#f-pronouns', 'They/them')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(createAdminUser).toHaveBeenCalledWith(
      expect.objectContaining({ supervisorEmail: 'grace@school.edu', pronouns: 'They/them', interests: [] })
    )
    expect(confirmStudentAssignments).toHaveBeenCalledWith([{ studentId: 42, groupId: 3 }])
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('adds a mentor as the mentor panel has them: details, weekly times and answers', async () => {
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: student({ id: 44, role: 'mentor' }) })
    const wrapper = await openAdd()
    await pickAppSelect(wrapper, '#f-role', 'Mentor')
    const sections = wrapper.findAll('.admin-users-form__section').map((section) => section.text())
    expect(sections).toEqual(['Account', 'Mentor details', 'Weekly Availability', 'Application Form', 'Profile Photo'])

    await wrapper.find('#f-first').setValue('Mia')
    await wrapper.find('#f-last').setValue('Ng')
    await wrapper.find('#f-email').setValue('mia@example.com')
    await pickAppSelect(wrapper, '#f-country', 'New Zealand')
    // Industry asks for a company, not an institution or field of study.
    await pickAppSelect(wrapper, '#f-mbg', 'Industry')
    expect(wrapper.find('#f-mcompany').exists()).toBe(true)
    expect(wrapper.find('#f-minst').exists()).toBe(false)
    expect(wrapper.find('#f-mfield').exists()).toBe(false)

    // A university student gives their year and field of study.
    await pickAppSelect(wrapper, '#f-mbg', 'University Student – Postgraduate')
    await wrapper.find('#f-minst').setValue('Uni')
    await pickAppSelect(wrapper, '#f-myear', 'Year 2')
    await wrapper.find('#f-mfield').setValue('Biology')
    await pickAppSelect(wrapper, '#f-mcap', '2 groups')
    await wrapper.find('[data-test="form-mentor-add-slot"]').trigger('click')
    const slot = '[data-test="form-mentor-slot-0"]'
    await pickAppSelect(wrapper.find(slot), '[aria-label="Day 1"]', 'Monday')
    await setPicker(wrapper, `${slot} [aria-label="From, time 1"]`, '18:00')
    await setPicker(wrapper, `${slot} [aria-label="To, time 1"]`, '19:00')
    // The answer is optional.
    await wrapper.find('#f-mentorReason').setValue('To help')
    // Hours a week, relevant background and how they'd mentor aren't asked.
    expect(wrapper.find('#f-mhours').exists()).toBe(false)
    expect(wrapper.find('#f-mentorRelevantBackground').exists()).toBe(false)
    expect(wrapper.find('#f-mentorMentoringApproach').exists()).toBe(false)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createAdminUser).toHaveBeenCalledWith(
      expect.objectContaining({
        mentorBackground: 'postgraduate',
        mentorInstitution: 'Uni',
        mentorCompany: '',
        mentorUniversityYear: '2',
        mentorFieldOfStudy: 'Biology',
        mentorMaxGroupCount: 2,
        mentorAvailability: [{ weekday: 0, start: '18:00', end: '19:00' }],
        mentorReason: 'To help'
      })
    )
    const sent = vi.mocked(createAdminUser).mock.lastCall![0]
    for (const gone of ['mentorWeeklyHours', 'mentorRelevantBackground', 'mentorMentoringApproach']) {
      expect(sent).not.toHaveProperty(gone)
    }
  })

  it('adds a mentor from just an email and role, the rest left for later', async () => {
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: student({ id: 45, role: 'mentor' }) })
    const wrapper = await openAdd()
    await pickAppSelect(wrapper, '#f-role', 'Mentor')
    // Only Email and Role are marked required.
    const marked = wrapper
      .findAll('label')
      .filter((label) => label.find('.required-mark').exists())
      .map((label) => label.attributes('for'))
    expect(marked).toEqual(['f-email', 'f-role'])

    await wrapper.find('#f-email').setValue('bare@example.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createAdminUser).toHaveBeenCalledWith(expect.objectContaining({ email: 'bare@example.com', role: 'mentor' }))
  })

  it('adds a student from just an email and role, the rest left for later', async () => {
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: student({ id: 47 }) })
    const wrapper = await openAdd()
    const marked = wrapper
      .findAll('label')
      .filter((label) => label.find('.required-mark').exists())
      .map((label) => label.attributes('for'))
    expect(marked).toEqual(['f-email', 'f-role'])

    await wrapper.find('#f-email').setValue('kid@example.com')
    // Consent needs a guardian on file, or a name of theirs to stand in.
    await wrapper.find('#f-consent-given').setValue(true)
    await wrapper.find('form').trigger('submit')
    expect(wrapper.text()).toContain("Enter the guardian's name to record their consent.")
    expect(createAdminUser).not.toHaveBeenCalled()

    await wrapper.find('#f-consent-given').setValue(false)
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createAdminUser).toHaveBeenCalledWith(expect.objectContaining({ email: 'kid@example.com', role: 'student' }))
  })

  it('adds a supervisor from just an email and role, as a mentor', async () => {
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: student({ id: 46, role: 'supervisor' }) })
    const wrapper = await openAdd()
    await pickAppSelect(wrapper, '#f-role', 'Supervisor')
    const marked = wrapper
      .findAll('label')
      .filter((label) => label.find('.required-mark').exists())
      .map((label) => label.attributes('for'))
    expect(marked).toEqual(['f-email', 'f-role'])

    await wrapper.find('#f-email').setValue('sup@example.com')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createAdminUser).toHaveBeenCalledWith(expect.objectContaining({ email: 'sup@example.com', role: 'supervisor' }))
  })

  it('uploads the chosen photo once the user is added', async () => {
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:chosen', revokeObjectURL: () => {} }))
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: student({ id: 43, role: 'supervisor' }) })
    vi.mocked(uploadAdminUserPhoto).mockReset().mockResolvedValue(student({ id: 43 }))
    const wrapper = await openAdd()
    await pickAppSelect(wrapper, '#f-role', 'Supervisor')
    await wrapper.find('#f-first').setValue('Kiri')
    await wrapper.find('#f-last').setValue('Hau')
    await wrapper.find('#f-email').setValue('kiri@example.com')
    await pickAppSelect(wrapper, '#f-country', 'New Zealand')

    const file = new File(['png'], 'me.png', { type: 'image/png' })
    const input = wrapper.find('[data-test="form-photo-input"]')
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    expect(wrapper.find('.admin-users-form__photo img').attributes('src')).toBe('blob:chosen')

    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(uploadAdminUserPhoto).toHaveBeenCalledWith(43, file)
    expect(wrapper.emitted('saved')).toHaveLength(1)
    vi.unstubAllGlobals()
  })

  it('has Email and Role, then Account, then their name under the role\'s details', async () => {
    const wrapper = await openAdd()
    await pickAppSelect(wrapper, '#f-role', 'Supervisor')

    const sections = wrapper.findAll('.admin-users-form__section').map((section) => section.text())
    expect(sections).toEqual(['Account', 'Supervisor details', 'Profile Photo'])
    const html = wrapper.html()
    expect(html.indexOf('id="f-email"')).toBeLessThan(html.indexOf('id="f-role"'))
    expect(html.indexOf('id="f-status"')).toBeLessThan(html.indexOf('id="f-first"'))
    expect(appSelectText(wrapper, '#f-status')).toBe('Active')
  })

  it('lists Australia\u2019s states, and takes one typed elsewhere', async () => {
    vi.mocked(createAdminUser).mockResolvedValue({ msg: 'ok', data: null } as never)
    const wrapper = await openAdd()
    await wrapper.find('#f-first').setValue('Kiri')
    await wrapper.find('#f-last').setValue('Hau')
    await wrapper.find('#f-email').setValue('kiri@example.com')

    await pickAppSelect(wrapper, '#f-country', 'Australia')
    expect(await appSelectLabels(wrapper, '#f-state')).toEqual(['NSW'])

    await pickAppSelect(wrapper, '#f-country', 'New Zealand')
    await wrapper.find('[data-test="form-state-name"]').setValue('Auckland')
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(createAdminUser).toHaveBeenCalledWith(
      expect.objectContaining({ country: 'New Zealand', state: 'Auckland', active: true })
    )
  })
})

describe('admin user form: guardian & consent', () => {
  beforeEach(() => {
    vi.mocked(updateAdminUser).mockClear()
  })

  it('lets admins edit the login email and sends the normalized change', async () => {
    const wrapper = await openForm(student())
    expect(wrapper.find('#f-email').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('#f-email').attributes('readonly')).toBeUndefined()
    expect(wrapper.find('#f-email-hint').text()).toContain("updates the user's login")
    await wrapper.find('#f-email').setValue('  New.Ward@Example.COM  ')
    expect(await save(wrapper)).toMatchObject({ email: 'new.ward@example.com' })
    expect(wrapper.emitted('saved')).toHaveLength(1)
  })

  it('does not resend an unchanged email or allow supervisor email edits', async () => {
    const wrapper = await openForm(student())
    expect(await save(wrapper)).not.toHaveProperty('email')
    await wrapper.setProps({ isSupervisorMode: true })
    expect(wrapper.find('#f-email').attributes('disabled')).toBeDefined()
    expect(wrapper.find('#f-email-hint').exists()).toBe(false)
    expect(await save(wrapper)).not.toHaveProperty('email')
  })

  it('rejects an invalid login email before saving', async () => {
    const wrapper = await openForm(student())
    await wrapper.find('#f-email').setValue('not-an-email')
    await save(wrapper)
    expect(updateAdminUser).not.toHaveBeenCalled()
    expect(wrapper.find('[role="alert"]').text()).toContain('Invalid email format')
  })

  it('keeps the form open and shows duplicate-email errors from the backend', async () => {
    vi.mocked(updateAdminUser).mockRejectedValueOnce(new Error('Account email already exists'))
    const wrapper = await openForm(student())
    await wrapper.find('#f-email').setValue('taken@example.com')
    await save(wrapper)
    expect(wrapper.find('[role="alert"]').text()).toContain('Account email already exists')
    expect(wrapper.emitted('saved')).toBeUndefined()
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('puts Account, Student details with Interests, Supervisor and Group, then Guardian & consent', async () => {
    const wrapper = await openForm(student())
    const sections = wrapper.findAll('.admin-users-form__section').map((section) => section.text())

    expect(sections).toEqual(['Account', 'Student details', 'Supervisor and Group', 'Guardian & consent'])
  })

  it('sends no guardian or consent fields when they are untouched', async () => {
    const wrapper = await openForm(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'R_1',
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))
    await pickAppSelect(wrapper, '#f-year', '11')

    const payload = await save(wrapper)

    expect(payload?.yearLevel).toBe(11)
    for (const key of GUARDIAN_KEYS) expect(payload).not.toHaveProperty(key)
  })

  it('sends only the guardian fields that changed', async () => {
    const wrapper = await openForm(student())
    await wrapper.find('#f-gemail').setValue('pat.new@example.com')

    const payload = await save(wrapper)

    expect(payload?.guardianEmail).toBe('pat.new@example.com')
    expect(payload).not.toHaveProperty('guardianFirstName')
    expect(payload).not.toHaveProperty('joinpermResponseId')
  })

  it('has no response ID field: consent comes from the guardian signing', async () => {
    const wrapper = await openForm(student({ joinPermissionReceived: true, joinpermResponseId: 'R_1' }))

    expect(wrapper.find('#f-consent').exists()).toBe(false)
    expect(wrapper.text()).not.toMatch(/response ID/i)
    expect(await save(wrapper)).not.toHaveProperty('joinpermResponseId')
  })

  const ticked = (wrapper: Awaited<ReturnType<typeof openForm>>, id: string) =>
    (wrapper.find(id).element as HTMLInputElement).checked

  it('ticks the consent boxes for what is on record, and sends nothing untouched', async () => {
    const both = await openForm(student({ joinPermissionReceived: true, joinpermResponseId: 'BTF-1', mediaConsent: true }))
    expect(ticked(both, '#f-consent-given')).toBe(true)
    expect(ticked(both, '#f-media-given')).toBe(true)
    const payload = await save(both)
    expect(payload).not.toHaveProperty('consentGiven')
    expect(payload).not.toHaveProperty('mediaConsent')

    const none = await openForm(student())
    expect(ticked(none, '#f-consent-given')).toBe(false)
    expect(ticked(none, '#f-media-given')).toBe(false)
    // Media consent goes with consent to take part.
    expect(none.find('#f-media-given').attributes('disabled')).toBeDefined()
  })

  it('records consent when ticked, with the media box', async () => {
    const wrapper = await openForm(student())
    await wrapper.find('#f-consent-given').setValue(true)
    await wrapper.find('#f-media-given').setValue(true)

    expect(await save(wrapper)).toMatchObject({ consentGiven: true, mediaConsent: true })

    const noMedia = await openForm(student())
    await noMedia.find('#f-consent-given').setValue(true)
    expect(await save(noMedia)).toMatchObject({ consentGiven: true, mediaConsent: false })
  })

  it('records media consent given later, or its withdrawal when unticked', async () => {
    const given = await openForm(student({ joinPermissionReceived: true, joinpermResponseId: 'BTF-1', mediaConsent: false }))
    await given.find('#f-media-given').setValue(true)
    const payload = await save(given)
    expect(payload?.mediaConsent).toBe(true)
    expect(payload).not.toHaveProperty('consentGiven')

    const withdrawn = await openForm(student({ joinPermissionReceived: true, joinpermResponseId: 'BTF-1', mediaConsent: true }))
    await withdrawn.find('#f-media-given').setValue(false)
    expect((await save(withdrawn))?.mediaConsent).toBe(false)
  })

  it('records a withdrawal when consent is unticked, unticking media with it', async () => {
    const wrapper = await openForm(student({ joinPermissionReceived: true, joinpermResponseId: 'BTF-1', mediaConsent: true }))
    await wrapper.find('#f-consent-given').setValue(false)

    expect(ticked(wrapper, '#f-media-given')).toBe(false)
    expect((await save(wrapper))?.consentGiven).toBe(false)
  })

  it('lets a pending new guardian be marked as having consented', async () => {
    const wrapper = await openForm(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'BTF-1',
      mediaConsent: true,
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))
    expect(wrapper.text()).toContain('Robin Carer (new guardian) has given consent')
    await wrapper.find('#f-pending-consent').setValue(true)

    expect(await save(wrapper)).toMatchObject({ consentGiven: true, mediaConsent: true })
  })

  it('says who last edited the user, at the top of the form', async () => {
    const wrapper = await openForm(student({ lastEditedBy: 'Ada Admin', lastEditedAt: '2026-10-09T05:15:00Z' }))
    expect(wrapper.text()).toContain('Last edited by Ada Admin · ')

    const never = await openForm(student())
    expect(never.text()).toContain('Update the account details below.')
  })

  it('flags consent with no signed form on record, which unticking revokes', async () => {
    const unverified = student({ joinPermissionReceived: true, joinpermResponseId: null })

    const kept = await openForm(unverified)
    expect(kept.text()).toContain('no signed consent form is on record')
    expect(await save(kept)).not.toHaveProperty('consentGiven')

    const revoked = await openForm(unverified)
    await revoked.find('#f-consent-given').setValue(false)
    expect((await save(revoked))?.consentGiven).toBe(false)
  })

  it('leaves a placeholder guardian blank and unsent', async () => {
    const wrapper = await openForm(student({ guardianFirstName: 'Wren', guardianLastName: 'Ward', guardianEmail: null }))

    expect((wrapper.find('#f-gfirst').element as HTMLInputElement).value).toBe('')
    expect(await save(wrapper)).not.toHaveProperty('guardianFirstName')
  })

  it('explains a pending guardian change', async () => {
    const wrapper = await openForm(student({
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))

    expect(wrapper.find('[data-test="form-pending-guardian"]').text()).toContain('Robin Carer')
  })

  it('rejects a half-entered guardian name and the student\'s own email', async () => {
    const wrapper = await openForm(student())
    await wrapper.find('#f-glast').setValue('')
    await save(wrapper)
    expect(wrapper.text()).toContain("Enter the guardian's first and last name.")

    await wrapper.find('#f-glast').setValue('Parent')
    await wrapper.find('#f-gemail').setValue('Ward@Example.com')
    await save(wrapper)
    expect(wrapper.text()).toContain("Guardian email can't be the student's own email.")

    expect(updateAdminUser).not.toHaveBeenCalled()
  })
})

describe('admin user detail: guardian & consent', () => {
  const openDetail = (user: AdminUser) =>
    mount(AdminUserDetailSheet, { props: { open: true, user }, global: { stubs: { teleport: true } } })

  it('flags consent with no signed form on record', () => {
    const wrapper = openDetail(student({ joinPermissionReceived: true, joinpermResponseId: null }))

    expect(wrapper.find('[data-test="admin-consent"]').text()).toBe('Yes (no signed form on record)')
  })

  it('gives permission as Yes and when it was given, or — while it is missing', () => {
    const given = openDetail(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'BTF-1',
      joinPermissionGrantedAt: '2026-10-17T04:45:41Z'
    }))
    expect(given.find('[data-test="admin-consent"]').text()).toMatch(/^Yes, \d\d\/\d\d\/\d\d \d\d:\d\d$/)
    // No separate Recorded row.
    expect(given.text()).not.toContain('Recorded')

    expect(openDetail(student()).find('[data-test="admin-consent"]').text()).toBe('—')
  })

  it('says who last edited the user', () => {
    const edited = openDetail(student({ lastEditedBy: 'Ada Admin', lastEditedAt: '2026-10-09T05:15:00Z' }))
    expect(edited.find('[data-test="admin-last-edited"]').text()).toContain('Ada Admin · ')

    const never = openDetail(student())
    expect(never.find('[data-test="admin-last-edited"]').text()).toContain('No edits on record')
  })

  it('shows recorded consent and a pending change', () => {
    const wrapper = openDetail(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'R_1',
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))

    expect(wrapper.find('[data-test="admin-consent"]').text()).toBe('Yes')
    // The consent's response ID isn't shown.
    expect(wrapper.text()).not.toContain('R_1')
    expect(wrapper.find('[data-test="admin-pending-guardian"]').text()).toContain('Robin Carer')
  })

  it('hides a placeholder guardian name', () => {
    const wrapper = openDetail(student({ guardianFirstName: 'Wren', guardianLastName: 'Ward' }))

    expect(wrapper.find('[data-test="admin-guardian-name"]').text()).toBe('—')
  })
})

describe('admin user detail: consent request', () => {
  const openDetail = (user: AdminUser) =>
    mount(AdminUserDetailSheet, { props: { open: true, user }, global: { stubs: { teleport: true } } })
  const button = '[data-test="admin-send-consent-request"]'

  beforeEach(() => {
    vi.mocked(sendGuardianConsentRequest).mockReset()
  })

  it('offers to email the guardian while consent is missing', () => {
    const wrapper = openDetail(student())

    expect(wrapper.find(button).text()).toBe('Send consent request')
    expect(wrapper.text()).toContain('Emails the consent form to pat@example.com.')
  })

  it('emails the new guardian when a change is pending', () => {
    const wrapper = openDetail(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'R_1',
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))

    expect(wrapper.text()).toContain('Emails the consent form to robin@example.com.')
  })

  it('hides the button once consent is in, or with no guardian email', () => {
    expect(openDetail(student({ joinPermissionReceived: true, joinpermResponseId: 'R_1' })).find(button).exists()).toBe(false)
    expect(openDetail(student({ guardianEmail: null })).find(button).exists()).toBe(false)
  })

  it('offers a resend and shows when it was last sent', () => {
    const wrapper = openDetail(student({ consentRequestSentAt: '2026-10-07T03:00:00Z' }))

    expect(wrapper.find(button).text()).toBe('Resend consent request')
    expect(wrapper.find('[data-test="admin-consent-request-sent"]').exists()).toBe(true)
  })

  it('sends and passes the updated user up', async () => {
    const updated = student({ consentRequestSentAt: '2026-10-08T03:00:00Z' })
    vi.mocked(sendGuardianConsentRequest).mockResolvedValue({ msg: 'Consent request sent to pat@example.com.', data: updated })
    const wrapper = openDetail(student())

    await wrapper.find(button).trigger('click')
    await flushPromises()

    expect(sendGuardianConsentRequest).toHaveBeenCalledWith(7)
    expect(wrapper.find('[data-test="admin-consent-request-message"]').text()).toBe('Consent request sent to pat@example.com.')
    expect(wrapper.emitted('updated')?.[0]).toEqual([updated])
  })

  it('shows the reason a send was refused', async () => {
    vi.mocked(sendGuardianConsentRequest).mockRejectedValue(
      new ApiError({ error: 'A consent request was just sent. Try again in 9 minutes.', code: 'http_429', request_id: 'x' }, 429)
    )
    const wrapper = openDetail(student())

    await wrapper.find(button).trigger('click')
    await flushPromises()

    const message = wrapper.find('[data-test="admin-consent-request-message"]')
    expect(message.text()).toBe('A consent request was just sent. Try again in 9 minutes.')
    expect(message.classes()).toContain('admin-users-detail__consent-message--error')
    expect(wrapper.emitted('updated')).toBeUndefined()
  })
})

describe('admin user detail: signed consent', () => {
  const openDetail = (user: AdminUser) =>
    mount(AdminUserDetailSheet, { props: { open: true, user }, global: { stubs: { teleport: true } } })
  const consented = (overrides: Partial<AdminUser> = {}) =>
    student({ joinPermissionReceived: true, joinpermResponseId: 'BTF-3', mediaConsent: true, ...overrides })

  beforeEach(() => {
    vi.mocked(fetchGuardianConsents).mockReset()
  })

  it('shows the media consent answer and when it was given', () => {
    const answer = (overrides: Partial<AdminUser>) =>
      openDetail(consented(overrides)).find('[data-test="admin-media-consent"] dd').text()

    expect(answer({ mediaConsentAt: '2026-10-17T04:45:41Z' })).toMatch(/^Yes, \d\d\/\d\d\/\d\d \d\d:\d\d$/)
    expect(answer({ mediaConsent: false, mediaConsentAt: '2026-10-17T04:45:41Z' })).toMatch(/^No, /)
    // Recorded by an admin with no form saying so: no time to give.
    expect(answer({ mediaConsentAt: null })).toBe('Yes')
    expect(answer({ joinpermResponseId: 'R_1', mediaConsent: null })).toBe('—')
  })

  it('shows the signed form only for consent signed on the platform', () => {
    expect(openDetail(consented()).find('[data-test="admin-view-consent"]').exists()).toBe(true)
    expect(openDetail(consented({ joinpermResponseId: 'R_1' })).find('[data-test="admin-view-consent"]').exists()).toBe(false)
  })

  it('leaves no empty button row when there is no signed form to view', () => {
    const wrapper = openDetail(consented({ joinpermResponseId: 'ADMIN-20261009063000' }))
    expect(wrapper.find('.admin-users-detail__consent-actions').exists()).toBe(false)
  })

  it('loads the signed form with its signature', async () => {
    vi.mocked(fetchGuardianConsents).mockResolvedValue([{
      id: 3,
      reference: 'BTF-3',
      fileName: '2026_318_BTF_1.pdf',
      guardianFullName: 'Pat Parent',
      guardianEmail: 'pat@example.com',
      mediaConsent: true,
      consentVersion: '2026-09-16',
      signedAt: '2026-10-08T03:00:00Z',
      withdrawnAt: null,
      mediaWithdrawnAt: null,
      signature: 'data:image/png;base64,AAAA'
    }])
    const wrapper = openDetail(consented())

    await wrapper.find('[data-test="admin-view-consent"]').trigger('click')
    await flushPromises()

    expect(fetchGuardianConsents).toHaveBeenCalledWith(7)
    const list = wrapper.find('[data-test="admin-signed-consents"]')
    expect(list.text()).toContain('Signed by Pat Parent')
    expect(list.find('img').attributes('src')).toBe('data:image/png;base64,AAAA')

    await list.find('[data-test="admin-download-record"]').trigger('click')
    await flushPromises()
    expect(downloadGuardianConsentRecord).toHaveBeenCalledWith(7, expect.objectContaining({ id: 3, reference: 'BTF-3' }))
  })

  it('has no withdrawal buttons, withdrawals are unticked on the Edit form', () => {
    const wrapper = openDetail(consented())
    expect(wrapper.find('[data-test="admin-withdraw-media"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-withdraw-consent"]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('withdrawal')
  })
})

describe('admin user detail: a student edited part by part', () => {
  const openDetail = (user: AdminUser, props: Record<string, unknown> = {}) =>
    mount(AdminUserDetailSheet, { props: { open: true, user, ...props }, global: { stubs: { teleport: true } } })

  beforeEach(() => {
    for (const fn of [updateAdminUser, confirmStudentAssignments, removeGroupMember, fetchAdminUser, uploadAdminUserPhoto, removeAdminUserPhoto]) {
      vi.mocked(fn).mockReset()
    }
  })

  it('shows Account, then each part with its own Edit, and no buttons at the bottom', () => {
    const wrapper = openDetail(student({ supervisorName: 'Sam Lee', supervisorEmail: 'sam@example.com', groupName: 'BTF1' }))

    const headings = wrapper.findAll('h3').map((h) => h.text())
    expect(headings).toEqual([
      'Profile Photo',
      'Account',
      'Internal Admin Notes',
      'Supervisor and Group',
      'Student Details',
      'Guardian Details'
    ])
    for (const part of ['account', 'details', 'guardian', 'supervisor']) {
      expect(wrapper.find(`[data-test="admin-edit-${part}"]`).exists()).toBe(true)
    }
    expect(wrapper.find('[data-test="admin-supervisor-group"]').text()).toContain('BTF1')
    expect(wrapper.find('.admin-users-detail__footer').exists()).toBe(false)
  })

  it('shows an admin their Admin Details, with no buttons below either', () => {
    const wrapper = openDetail(student({ role: 'admin' }))

    expect(wrapper.findAll('h3').map((h) => h.text())).toEqual([
      'Profile Photo',
      'Account',
      'Internal Admin Notes',
      'Admin Details'
    ])
    expect(wrapper.find('.admin-users-detail__footer').exists()).toBe(false)
    expect(wrapper.findAll('button').map((b) => b.text())).not.toContain('Close')
  })

  it('shows an admin pronouns after their name, and edits both', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student({ role: 'admin' }) })
    const wrapper = openDetail(student({ role: 'admin', pronouns: 'She/her' }))
    expect(wrapper.find('[data-test="admin-admin-pronouns"] dd').text()).toBe('She/her')
    // Their country and state are theirs to edit too, under Account.
    expect(wrapper.find('[data-test="admin-edit-account"]').exists()).toBe(true)

    await wrapper.find('[data-test="admin-edit-admin-details"]').trigger('click')
    await pick(wrapper, 'admin-admin-pronouns-select', 'They/them')
    await wrapper.find('[data-test="admin-admin-details-form"]').trigger('submit')
    await flushPromises()
    expect(updateAdminUser).toHaveBeenCalledWith(7, { firstName: 'Wren', lastName: 'Ward', pronouns: 'They/them' })
  })

  it('offers no Edit where the panel only views a student', () => {
    const wrapper = openDetail(student(), { showEdit: false })

    expect(wrapper.find('[data-test="admin-edit-details"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-edit-guardian"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-edit-supervisor"]').exists()).toBe(false)
  })

  const optionsOf = (wrapper: ReturnType<typeof openDetail>, select: string) =>
    openAppSelect(wrapper, `[data-test="${select}"]`)

  const pick = (wrapper: ReturnType<typeof openDetail>, select: string, label: string) =>
    pickAppSelect(wrapper, `[data-test="${select}"]`, label)

  // Australia (NSW, VIC) and New Zealand (Auckland); the student is in NSW.
  const editAccount = async (wrapper: ReturnType<typeof openDetail>) => {
    vi.mocked(fetchAdminCountries).mockResolvedValue([
      { id: 1, countryName: 'Australia' },
      { id: 2, countryName: 'New Zealand' }
    ])
    vi.mocked(fetchAdminStates).mockResolvedValue([
      { id: 11, stateName: 'NSW', countryName: 'Australia' },
      { id: 12, stateName: 'VIC', countryName: 'Australia' },
      { id: 21, stateName: 'Auckland', countryName: 'New Zealand' }
    ])
    await wrapper.find('[data-test="admin-edit-account"]').trigger('click')
    await flushPromises()
  }
  const inNsw = () => student({ state: { id: 11, stateName: 'NSW' } })

  it('changes the login email on its own', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(inNsw())
    await editAccount(wrapper)

    const form = wrapper.find('[data-test="admin-account-form"]')
    await form.find('input[type="email"]').setValue('New@Example.com')
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(7, { email: 'new@example.com' })
    expect(wrapper.find('[data-test="admin-account-form"]').exists()).toBe(false)
  })

  it("picks Australia's states, and types the state elsewhere", async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(inNsw())
    await editAccount(wrapper)

    expect(await appSelectLabels(wrapper, '[data-test="admin-state-select"]')).toEqual(['NSW', 'VIC'])
    await wrapper.find('[data-test="admin-state-select"] input').trigger('blur')

    // A new country clears the state, now typed.
    await pick(wrapper, 'admin-country-select', 'New Zealand')
    expect(wrapper.find('[data-test="admin-state-select"]').exists()).toBe(false)
    const typed = wrapper.find('[data-test="admin-state-text"]')
    expect((typed.element as HTMLInputElement).value).toBe('')
    await typed.setValue('Auckland')

    await wrapper.find('[data-test="admin-account-form"]').trigger('submit')
    await flushPromises()
    expect(updateAdminUser).toHaveBeenCalledWith(7, { countryId: 2, stateName: 'Auckland' })
  })

  it('picks Status without typing, as a plain dropdown', async () => {
    const wrapper = openDetail(inNsw())
    await editAccount(wrapper)

    const box = wrapper.find('[data-test="admin-status-select"] input')
    expect(box.attributes('readonly')).toBeDefined()
    expect((box.element as HTMLInputElement).value).toBe('Active')
  })

  it('makes the student inactive, or active again', async () => {
    const inactive = student({ isActive: false, accountStatus: 'deactivated' })
    vi.mocked(setAdminUserActive).mockReset().mockResolvedValue({ msg: 'ok', data: inactive })
    const wrapper = openDetail(inNsw())
    await editAccount(wrapper)

    await pick(wrapper, 'admin-status-select', 'Inactive')
    await wrapper.find('[data-test="admin-account-form"]').trigger('submit')
    await flushPromises()

    expect(setAdminUserActive).toHaveBeenCalledWith(7, false)
    // Nothing else changed, so nothing else is sent.
    expect(updateAdminUser).not.toHaveBeenCalled()
    expect(wrapper.emitted('updated')).toEqual([[inactive]])
  })

  it("says first when activating a student from an earlier year makes them this year's", async () => {
    vi.mocked(setAdminUserActive).mockReset().mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(student({
      state: { id: 11, stateName: 'NSW' }, isActive: false, accountStatus: 'deactivated', earlierChallengeYear: 2026
    }))
    await editAccount(wrapper)

    await pick(wrapper, 'admin-status-select', 'Active')
    await wrapper.find('[data-test="admin-account-form"]').trigger('submit')
    await flushPromises()

    expect(setAdminUserActive).not.toHaveBeenCalled()
    const dialog = wrapper.get('.admin-modal--confirm')
    expect(dialog.text()).toContain('Activate for this year?')
    expect(dialog.text()).toContain("is from the 2026 challenge. Activating them makes them one of this year's students")
    await dialog.findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(setAdminUserActive).toHaveBeenCalledWith(7, true)
  })

  it('rejects an invalid email and saves nothing unchanged', async () => {
    const wrapper = openDetail(inNsw())
    await editAccount(wrapper)

    const form = wrapper.find('[data-test="admin-account-form"]')
    await form.find('input[type="email"]').setValue('not-an-email')
    await form.trigger('submit')
    expect(form.text()).toContain('Enter a valid email address.')

    await form.find('input[type="email"]').setValue('ward@example.com')
    await form.trigger('submit')
    await flushPromises()
    expect(updateAdminUser).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="admin-account-form"]').exists()).toBe(false)
  })

  it('saves the student details and passes the updated student up', async () => {
    const updated = student({ schoolName: 'New High' })
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: updated })
    const wrapper = openDetail(student())

    await wrapper.find('[data-test="admin-edit-details"]').trigger('click')
    const form = wrapper.find('[data-test="admin-details-form"]')
    await form.findAll('input')[2].setValue('New High')
    await pick(wrapper, 'admin-year-select', '11')
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(7, {
      firstName: 'Wren',
      lastName: 'Ward',
      schoolName: 'New High',
      yearLevel: 11,
      interests: ['Biomedical Innovations'],
      pronouns: ''
    })
    expect(wrapper.emitted('updated')).toEqual([[updated]])
    expect(wrapper.find('[data-test="admin-details-form"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-details-form"]').exists()).toBe(false)
  })

  it('shows when they agreed to the policies, just above Status', () => {
    const agreed = openDetail(student({ policiesAgreedAt: '2026-10-21T00:15:00Z' }))
    const terms = agreed.findAll('[data-test="admin-account"] dt').map((term) => term.text())
    expect(terms.indexOf('Policies')).toBe(terms.indexOf('Status') - 1)
    expect(agreed.get('[data-test="admin-policies"] dd').text()).toMatch(/^Agreed, /)

    const never = openDetail(student({ policiesAgreedAt: null }))
    expect(never.get('[data-test="admin-policies"] dd').text()).toBe('—')
  })

  it('shows their profile photo before Account, as a row like Account\'s', () => {
    const photo = 'https://files.example.com/users/7/photo.png'
    const withPhoto = openDetail(student({ profileImageUrl: photo }))
    expect(withPhoto.find('[data-test="admin-photo"] dd img').attributes('src')).toBe(photo)

    const without = openDetail(student({ profileImageUrl: null }))
    expect(without.find('[data-test="admin-photo"] img').exists()).toBe(false)
    expect(without.find('[data-test="admin-photo"] dd').text()).toBe('—')
  })

  it('uploads a chosen photo on Save, and passes the user up', async () => {
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: () => 'blob:chosen', revokeObjectURL: () => {} }))
    const updated = student({ profileImageUrl: 'https://files.example.com/new.png' })
    vi.mocked(uploadAdminUserPhoto).mockResolvedValue(updated)
    const wrapper = openDetail(student({ profileImageUrl: null }))

    await wrapper.find('[data-test="admin-edit-photo"]').trigger('click')
    const file = new File(['png'], 'me.png', { type: 'image/png' })
    const input = wrapper.find('[data-test="admin-photo-input"]')
    Object.defineProperty(input.element, 'files', { value: [file] })
    await input.trigger('change')
    // Shown before it's saved.
    expect(wrapper.find('[data-test="admin-photo-form"] img').attributes('src')).toBe('blob:chosen')

    await wrapper.find('[data-test="admin-photo-form"]').trigger('submit')
    await flushPromises()
    expect(uploadAdminUserPhoto).toHaveBeenCalledWith(7, file)
    expect(wrapper.emitted('updated')).toEqual([[updated]])
    expect(wrapper.find('[data-test="admin-photo-form"]').exists()).toBe(false)
    vi.unstubAllGlobals()
  })

  it('refuses a file that is not a photo, and removes a photo on Save', async () => {
    vi.mocked(removeAdminUserPhoto).mockResolvedValue(student({ profileImageUrl: null }))
    const wrapper = openDetail(student({ profileImageUrl: 'https://files.example.com/old.png' }))

    await wrapper.find('[data-test="admin-edit-photo"]').trigger('click')
    const input = wrapper.find('[data-test="admin-photo-input"]')
    Object.defineProperty(input.element, 'files', { value: [new File(['x'], 'notes.pdf', { type: 'application/pdf' })] })
    await input.trigger('change')
    expect(wrapper.text()).toContain('Choose a PNG, JPEG, or WebP image smaller than 5 MB.')

    await wrapper.find('[data-test="admin-photo-remove"]').trigger('click')
    expect(wrapper.find('[data-test="admin-photo-form"] img').exists()).toBe(false)
    await wrapper.find('[data-test="admin-photo-form"]').trigger('submit')
    await flushPromises()
    expect(removeAdminUserPhoto).toHaveBeenCalledWith(7)
    expect(uploadAdminUserPhoto).not.toHaveBeenCalled()
  })

  it('shows pronouns after Interests, and edits them as registering offers them', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(student({ pronouns: 'Xe/xem' }))
    expect(wrapper.find('[data-test="admin-student-pronouns"] dd').text()).toBe('Xe/xem')

    await wrapper.find('[data-test="admin-edit-details"]').trigger('click')
    // Their own words come back under Other.
    expect(appSelectText(wrapper, '[data-test="admin-pronouns-select"]')).toBe('Other')
    expect((wrapper.find('[data-test="admin-pronouns-other"]').element as HTMLInputElement).value).toBe('Xe/xem')

    await wrapper.find('[data-test="admin-pronouns-other"]').setValue(' ')
    await wrapper.find('[data-test="admin-details-form"]').trigger('submit')
    expect(wrapper.text()).toContain('Enter their pronouns.')

    await pick(wrapper, 'admin-pronouns-select', 'They/them')
    expect(wrapper.find('[data-test="admin-pronouns-other"]').exists()).toBe(false)
    await wrapper.find('[data-test="admin-details-form"]').trigger('submit')
    await flushPromises()
    expect(vi.mocked(updateAdminUser).mock.calls[0][1]).toMatchObject({ pronouns: 'They/them' })
  })

  it('needs at least one interest', async () => {
    const wrapper = openDetail(student())

    await wrapper.find('[data-test="admin-edit-details"]').trigger('click')
    const form = wrapper.find('[data-test="admin-details-form"]')
    for (const box of form.findAll('input[type="checkbox"]')) await box.setValue(false)
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).not.toHaveBeenCalled()
    expect(form.text()).toContain('Choose at least one interest.')
  })

  it('sends only the guardian fields that changed, and consent once ticked', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(student())

    await wrapper.find('[data-test="admin-edit-guardian"]').trigger('click')
    const form = wrapper.find('[data-test="admin-guardian-form"]')
    await form.find('input[type="email"]').setValue('new@example.com')
    await form.find('[data-test="admin-consent-given"]').setValue(true)
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(7, {
      guardianEmail: 'new@example.com',
      consentGiven: true,
      mediaConsent: false
    })
  })

  it('can still change the guardian once permission is in', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(student({ joinPermissionReceived: true, joinpermResponseId: 'R_1', mediaConsent: true }))

    await wrapper.find('[data-test="admin-edit-guardian"]').trigger('click')
    const form = wrapper.find('[data-test="admin-guardian-form"]')
    const [first, last] = form.findAll('input')
    await first.setValue('Robin')
    await last.setValue('Carer')
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(7, { guardianFirstName: 'Robin', guardianLastName: 'Carer' })
  })

  it('closes a guardian edit that changes nothing without saving', async () => {
    const wrapper = openDetail(student())

    await wrapper.find('[data-test="admin-edit-guardian"]').trigger('click')
    await wrapper.find('[data-test="admin-guardian-form"]').trigger('submit')
    await flushPromises()

    expect(updateAdminUser).not.toHaveBeenCalled()
    expect(wrapper.find('[data-test="admin-guardian-form"]').exists()).toBe(false)
  })

  const sam = student({ id: 9, role: 'supervisor', firstName: 'Sam', lastName: 'Lee', email: 'sam@example.com' })
  const group = (id: number, name: string, students: number): AdminGroupDetail => ({
    id,
    name,
    members: Array.from({ length: students }, (_, index) => ({
      id: String(100 + index),
      name: `Member ${index}`,
      email: `m${index}@example.com`,
      role: 'student',
      membershipId: index
    })),
    mentor: null,
    createdAt: '',
    updatedAt: ''
  })

  // Supervisors and groups to pick from, loaded when Edit is pressed.
  const editSupervisorAndGroup = async (wrapper: ReturnType<typeof openDetail>) => {
    vi.mocked(fetchAdminUsers).mockResolvedValue({ items: [sam], total: 1, page: 1, limit: 200 } as never)
    vi.mocked(fetchAdminGroupList).mockResolvedValue({
      items: [group(1, 'BTF1', 5), group(2, 'BTF2', 2), group(10, 'BTF10', 0)],
      total: 3,
      page: 1,
      limit: 200,
      has_more: false
    })
    await wrapper.find('[data-test="admin-edit-supervisor"]').trigger('click')
    await flushPromises()
  }

  it('picks a supervisor from a list, by name with the email under it', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(student())
    await editSupervisorAndGroup(wrapper)

    const input = wrapper.find('[data-test="admin-supervisor-select"] input')
    const [first] = await optionsOf(wrapper, 'admin-supervisor-select')
    expect(first.textContent).toContain('Sam Lee')
    expect(first.textContent).toContain('sam@example.com')
    await input.setValue('nobody')
    expect(wrapper.find('[data-test="admin-supervisor-select"]').text()).toContain('No supervisor matches')
    await input.setValue('lee')

    await pick(wrapper, 'admin-supervisor-select', 'Sam Lee')
    expect((input.element as HTMLInputElement).value).toBe('Sam Lee')
    await wrapper.find('[data-test="admin-supervisor-form"]').trigger('submit')
    await flushPromises()

    // They had none, so no popup.
    expect(wrapper.find('[data-test="admin-replacing"]').exists()).toBe(false)
    expect(updateAdminUser).toHaveBeenCalledWith(7, { supervisorEmail: 'sam@example.com' })
    expect(confirmStudentAssignments).not.toHaveBeenCalled()
  })

  it('puts a student with no group into one, where full groups cannot be picked', async () => {
    const moved = student({ groupId: 2, groupName: 'BTF2' })
    vi.mocked(confirmStudentAssignments).mockResolvedValue({ msg: 'ok', assignedCount: 1 })
    vi.mocked(fetchAdminUser).mockResolvedValue(moved)
    const wrapper = openDetail(student())
    await editSupervisorAndGroup(wrapper)

    const options = await optionsOf(wrapper, 'admin-group-select')
    // No group first, then by name with the seats taken.
    expect(options.map((o) => o.querySelector('.app-select__label')?.textContent?.trim())).toEqual([
      'No group',
      'BTF1',
      'BTF2',
      'BTF10'
    ])
    expect(options[1].textContent).toContain('5/5 students · Full')
    expect(options[1].getAttribute('aria-disabled')).toBe('true')
    options[1].dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }))
    await flushPromises()
    expect(wrapper.find('[data-test="admin-group-select"]').find('.is-selected').text()).toContain('No group')

    await pick(wrapper, 'admin-group-select', 'BTF2')
    await wrapper.find('[data-test="admin-supervisor-form"]').trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-test="admin-replacing"]').exists()).toBe(false)
    expect(confirmStudentAssignments).toHaveBeenCalledWith([{ studentId: 7, groupId: 2 }])
    expect(updateAdminUser).not.toHaveBeenCalled()
    expect(wrapper.emitted('updated')).toEqual([[moved]])
  })

  it('asks before replacing a supervisor or group they already have', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    vi.mocked(removeGroupMember).mockResolvedValue('ok')
    vi.mocked(fetchAdminUser).mockResolvedValue(student())
    const wrapper = openDetail(student({
      supervisorName: 'Old Supervisor',
      supervisorEmail: 'old@example.com',
      groupId: 2,
      groupName: 'BTF2'
    }))
    await editSupervisorAndGroup(wrapper)

    await pick(wrapper, 'admin-supervisor-select', 'Sam Lee')
    await pick(wrapper, 'admin-group-select', 'No group')
    await wrapper.find('[data-test="admin-supervisor-form"]').trigger('submit')
    await flushPromises()

    expect(updateAdminUser).not.toHaveBeenCalled()
    const popup = wrapper.find('.admin-modal--confirm')
    expect(wrapper.find('[data-test="admin-replacing"]').text()).toContain(
      'Change supervisor from Old Supervisor to Sam Lee.'
    )
    expect(wrapper.find('[data-test="admin-replacing"]').text()).toContain('Take them out of BTF2.')

    // Cancel saves nothing; Save does both.
    await popup.findAll('button').find((b) => b.text() === 'Cancel')!.trigger('click')
    expect(wrapper.find('.admin-modal--confirm').exists()).toBe(false)
    expect(updateAdminUser).not.toHaveBeenCalled()

    await wrapper.find('[data-test="admin-supervisor-form"]').trigger('submit')
    await wrapper.find('.admin-modal--confirm').findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(7, { supervisorEmail: 'sam@example.com' })
    expect(removeGroupMember).toHaveBeenCalledWith(2, 7)
    expect(wrapper.find('.admin-modal--confirm').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-supervisor-form"]').exists()).toBe(false)
  })

  it('keeps the form open and shows why a save was refused', async () => {
    vi.mocked(updateAdminUser).mockRejectedValue(new ApiError({ error: 'No supervisor with that email.', code: 'http_400', request_id: 'x' }, 400))
    const wrapper = openDetail(student())
    await editSupervisorAndGroup(wrapper)

    await pick(wrapper, 'admin-supervisor-select', 'Sam Lee')
    const form = wrapper.find('[data-test="admin-supervisor-form"]')
    await form.trigger('submit')
    await flushPromises()

    expect(form.text()).toContain('No supervisor with that email.')
    expect(wrapper.emitted('updated')).toBeUndefined()
  })
})

describe('admin user detail: a mentor edited part by part', () => {
  const openDetail = (user: AdminUser) =>
    mount(AdminUserDetailSheet, { props: { open: true, user }, global: { stubs: { teleport: true } } })

  // A postgraduate mentor of BTF2, free Monday and Wednesday evenings.
  const mentor = (overrides: Partial<AdminUser> = {}) =>
    student({
      id: 5,
      firstName: 'Mia',
      lastName: 'Ng',
      role: 'mentor',
      schoolName: null,
      yearLevel: null,
      interests: ['Biomedical Innovations', 'Structural Biology'],
      mentorBackground: 'postgraduate',
      mentorInstitution: 'Uni of Sydney',
      mentorUniversityYear: '2',
      mentorFieldOfStudy: 'Biology',
      mentorCompany: '',
      mentorReason: 'To help',
      mentorMaxGroupCount: 3,
      mentorAvailability: [
        { weekday: 0, start: '18:00', end: '20:00' },
        { weekday: 2, start: '17:00', end: '19:00' }
      ],
      mentorGroups: [{ id: 2, name: 'BTF2', studentCount: 3 }],
      ...overrides
    })

  const group = (id: number, name: string, mentorName: string | null): AdminGroupDetail => ({
    id,
    name,
    members: [{ id: '100', name: 'A student', email: 's@example.com', role: 'student', membershipId: 1 }],
    mentor: mentorName
      ? { id: mentorName === 'Mia Ng' ? '5' : '9', name: mentorName, email: 'm@example.com', role: 'mentor', membershipId: 2 }
      : null,
    createdAt: '',
    updatedAt: ''
  })

  beforeEach(() => {
    for (const fn of [updateAdminUser, confirmMentorAssignments, unassignMentors, fetchAdminUser]) {
      vi.mocked(fn).mockReset()
    }
    vi.mocked(fetchAdminGroupList).mockResolvedValue({
      items: [group(2, 'BTF2', 'Mia Ng'), group(3, 'BTF3', 'Sam Lee'), group(4, 'BTF4', null)],
      total: 3,
      page: 1,
      limit: 200,
      has_more: false
    })
  })

  it('shows pronouns after the name, and reads an old typed background as the list’s choice', async () => {
    const wrapper = openDetail(mentor({ pronouns: 'She/her', mentorBackground: 'Undergraduate Student', mentorUniversityYear: '3' }))
    const rows = wrapper.findAll('[data-test="admin-mentor-details"] dt').map((term) => term.text())
    expect(rows.slice(0, 3)).toEqual(['Name', 'Pronouns', 'Background'])
    expect(wrapper.find('[data-test="admin-mentor-pronouns"] dd').text()).toBe('She/her')
    // Its year of study shows, as for anyone at university.
    expect(wrapper.find('[data-test="admin-mentor-background-label"]').text()).toBe('University Student – Undergraduate')
    expect(rows).toContain('Year of study')

    // Edit picks the list's choice, so saving stores it.
    await wrapper.find('[data-test="admin-edit-mentor-details"]').trigger('click')
    expect(appSelectText(wrapper, '#admin-mentor-background')).toBe('University Student – Undergraduate')
  })

  it('shows Account, Groups, Mentor Details and Application Form, each with Edit, and nothing at the bottom', () => {
    const wrapper = openDetail(mentor())

    expect(wrapper.findAll('h3').map((h) => h.text())).toEqual([
      'Profile Photo',
      'Account',
      'Internal Admin Notes',
      'Groups',
      'Mentor Details',
      'Weekly Availability',
      'Application Form'
    ])
    for (const edit of ['account', 'mentor-groups', 'mentor-details', 'availability', 'application']) {
      expect(wrapper.find(`[data-test="admin-edit-${edit}"]`).exists(), edit).toBe(true)
    }
    expect(wrapper.find('.admin-users-detail__footer').exists()).toBe(false)
  })

  it('shows their groups in one row, what their background asks, and why they would mentor', () => {
    const wrapper = openDetail(mentor({ mentorGroups: [{ id: 2, name: 'BTF2', studentCount: 3 }, { id: 10, name: 'BTF10', studentCount: 1 }] }))

    expect(wrapper.find('[data-test="admin-mentor-group-names"]').text()).toBe('BTF2, BTF10')
    const details = wrapper.find('[data-test="admin-mentor-details"]').text()
    for (const text of ['University Student – Postgraduate', 'Uni of Sydney', 'Year 2', 'Biology', 'Structural Biology', '3 groups']) {
      expect(details).toContain(text)
    }
    expect(details).not.toContain('Company')
    expect(details).not.toContain('Hours per week')
    expect(wrapper.find('[data-test="admin-answer-view-mentorReason"]').text()).toBe('To help')
    expect(wrapper.find('[data-test="admin-answer-view-mentorRelevantBackground"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-answer-view-mentorMentoringApproach"]').exists()).toBe(false)

    const industry = openDetail(mentor({ mentorBackground: 'industry', mentorCompany: 'Acme Bio', mentorInstitution: '' }))
    const industryDetails = industry.find('[data-test="admin-mentor-details"]').text()
    expect(industryDetails).toContain('Acme Bio')
    expect(industryDetails).not.toContain('Institution')
    expect(industryDetails).not.toContain('Field of study')
  })

  it('offers Group 2 once Group 1 is filled, and adds a group without a mentor straight away', async () => {
    const updated = mentor()
    vi.mocked(confirmMentorAssignments).mockResolvedValue({ msg: 'ok', confirmedCount: 1 })
    vi.mocked(fetchAdminUser).mockResolvedValue(updated)
    const wrapper = openDetail(mentor())
    await wrapper.find('[data-test="admin-edit-mentor-groups"]').trigger('click')
    await flushPromises()

    const form = wrapper.find('[data-test="admin-mentor-groups-form"]')
    expect(form.findAll('.admin-users-detail__label').map((label) => label.text())).toEqual(['Group 1', 'Group 2'])
    // Their own group isn't offered again; another's says whose it is.
    expect(await appSelectLabels(wrapper, '[data-test="admin-mentor-group-1"]')).toEqual(['BTF3', 'BTF4'])
    const [btf3] = await openAppSelect(wrapper, '[data-test="admin-mentor-group-1"]')
    expect(btf3.textContent).toContain('mentor: Sam Lee')
    await pickAppSelect(wrapper, '[data-test="admin-mentor-group-1"]', 'BTF4')
    expect(form.findAll('.admin-users-detail__label').map((label) => label.text())).toEqual(['Group 1', 'Group 2', 'Group 3'])

    await form.trigger('submit')
    await flushPromises()

    expect(wrapper.find('[data-test="admin-replacing"]').exists()).toBe(false)
    expect(unassignMentors).not.toHaveBeenCalled()
    expect(confirmMentorAssignments).toHaveBeenCalledWith([{ groupId: 4, mentorUserId: 5 }])
    expect(wrapper.emitted('updated')).toEqual([[updated]])
  })

  it('asks before taking them off a group or replacing another mentor', async () => {
    vi.mocked(unassignMentors).mockResolvedValue({ msg: 'ok', unassignedCount: 1 })
    vi.mocked(confirmMentorAssignments).mockResolvedValue({ msg: 'ok', confirmedCount: 1 })
    vi.mocked(fetchAdminUser).mockResolvedValue(mentor())
    const wrapper = openDetail(mentor())
    await wrapper.find('[data-test="admin-edit-mentor-groups"]').trigger('click')
    await flushPromises()

    await pickAppSelect(wrapper, '[data-test="admin-mentor-group-0"]', 'BTF3')
    await wrapper.find('[data-test="admin-mentor-groups-form"]').trigger('submit')
    await flushPromises()

    const lines = wrapper.find('[data-test="admin-replacing"]').text()
    expect(lines).toContain('Take them off BTF2.')
    expect(lines).toContain("Replace Sam Lee as BTF3's mentor.")
    expect(confirmMentorAssignments).not.toHaveBeenCalled()

    await wrapper.find('.admin-modal--confirm').findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(unassignMentors).toHaveBeenCalledWith([2])
    expect(confirmMentorAssignments).toHaveBeenCalledWith([{ groupId: 3, mentorUserId: 5 }])
  })

  it('shows no more groups than their capacity', async () => {
    const wrapper = openDetail(mentor({ mentorMaxGroupCount: 1 }))
    await wrapper.find('[data-test="admin-edit-mentor-groups"]').trigger('click')
    await flushPromises()

    const form = wrapper.find('[data-test="admin-mentor-groups-form"]')
    expect(form.findAll('.admin-users-detail__label').map((label) => label.text())).toEqual(['Group 1'])
    expect(form.text()).toContain('capacity of 1 group')
  })

  it('saves their details, showing what their background asks for and clearing the rest', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: mentor() })
    const wrapper = openDetail(mentor())
    await wrapper.find('[data-test="admin-edit-mentor-details"]').trigger('click')

    const form = () => wrapper.find('[data-test="admin-mentor-details-form"]')
    // Expertise from outside the list stays, ticked.
    const structural = form().findAll('input[type="checkbox"]').find((box) => (box.element as HTMLInputElement).value === 'Structural Biology')
    expect((structural!.element as HTMLInputElement).checked).toBe(true)

    await pickAppSelect(wrapper, '[data-test="admin-mentor-background"]', 'Industry')
    expect(form().find('[data-test="admin-mentor-institution"]').exists()).toBe(false)
    expect(form().find('[data-test="admin-mentor-year"]').exists()).toBe(false)

    await form().find('[data-test="admin-mentor-company"]').setValue('Acme Bio')
    expect(form().find('[data-test="admin-mentor-hours-input"]').exists()).toBe(false)
    await form().trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(5, {
      firstName: 'Mia',
      lastName: 'Ng',
      pronouns: '',
      mentorBackground: 'industry',
      mentorCompany: 'Acme Bio',
      mentorInstitution: '',
      mentorUniversityYear: '',
      mentorFieldOfStudy: '',
      interests: ['Biomedical Innovations', 'Structural Biology'],
      mentorMaxGroupCount: 3
    })
  })

  it('saves with nothing required: a field left blank is saved blank', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: mentor() })
    const wrapper = openDetail(mentor())
    await wrapper.find('[data-test="admin-edit-mentor-details"]').trigger('click')
    const form = wrapper.find('[data-test="admin-mentor-details-form"]')
    await form.find('[data-test="admin-mentor-field"]').setValue('')
    for (const box of form.findAll('input[type="checkbox"]')) await box.setValue(false)
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(5, expect.objectContaining({ mentorFieldOfStudy: '', interests: [] }))
  })

  it('shows each weekly time, and edits them as day and times', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: mentor() })
    const wrapper = openDetail(mentor())
    const times = wrapper.find('[data-test="admin-mentor-times"]')
    expect(times.findAll('dt').map((day) => day.text())).toEqual(['Monday', 'Wednesday'])
    expect(times.findAll('dd').map((time) => time.text())).toEqual(['18:00 – 20:00', '17:00 – 19:00'])
    expect(openDetail(mentor({ mentorAvailability: [] })).find('[data-test="admin-mentor-times"]').text()).toContain('—')

    await wrapper.find('[data-test="admin-edit-availability"]').trigger('click')
    const form = () => wrapper.find('[data-test="admin-availability-form"]')
    // A third time, then the first taken away.
    await wrapper.find('[data-test="admin-mentor-add-slot"]').trigger('click')
    await pickAppSelect(wrapper, '[data-test="admin-mentor-slot-2"]', 'Friday')
    // Each time picked with the time picker: every hour, and the minutes in
    // 5-minute steps.
    const slot = (part: string) => `[data-test="admin-mentor-slot-2-${part}"]`
    await wrapper.find(slot('start')).trigger('click')
    // In place, as the sheet's spec stubs Teleport.
    const panel = wrapper.find('.app-picker__panel')
    expect(panel.findAll('[data-hour]')).toHaveLength(24)
    expect(panel.findAll('[data-minute]').map((minute) => minute.text())).toEqual([
      '00', '05', '10', '15', '20', '25', '30', '35', '40', '45', '50', '55'
    ])
    await wrapper.find(slot('start')).trigger('click')
    await setPicker(wrapper, slot('start'), '10:30')
    await setPicker(wrapper, slot('end'), '09:00')
    await form().trigger('submit')
    await flushPromises()
    expect(form().text()).toContain('Each weekly time must end after it starts.')
    expect(updateAdminUser).not.toHaveBeenCalled()

    await setPicker(wrapper, slot('end'), '12:00')
    // A saved time shows as it was saved.
    expect(pickerText(wrapper, '[data-test="admin-mentor-slot-0-start"]')).toBe('18:00')
    await form().find('[data-test="admin-mentor-slot-0"] .admin-users-detail__slot-remove').trigger('click')
    await form().trigger('submit')
    await flushPromises()
    expect(updateAdminUser).toHaveBeenCalledWith(5, {
      mentorAvailability: [
        { weekday: 2, start: '17:00', end: '19:00' },
        { weekday: 4, start: '10:30', end: '12:00' }
      ]
    })
  })

  it('edits why they would mentor, kept to 150 words', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: mentor() })
    const wrapper = openDetail(mentor())
    await wrapper.find('[data-test="admin-edit-application"]').trigger('click')

    const form = wrapper.find('[data-test="admin-application-form"]')
    expect(form.text()).toContain('Why would you like to mentor?')
    expect(form.text()).not.toContain('Relevant background')
    expect(form.text()).not.toContain('How would you mentor BIOTech groups?')
    await form.find('[data-test="admin-answer-mentorReason"]').setValue('word '.repeat(151))
    expect(form.text()).toContain('151/150 words')
    await form.trigger('submit')
    await flushPromises()
    expect(form.text()).toContain('Keep the answer to 150 words or fewer.')

    await form.find('[data-test="admin-answer-mentorReason"]').setValue('To share what I know')
    await form.trigger('submit')
    await flushPromises()
    expect(updateAdminUser).toHaveBeenCalledWith(5, { mentorReason: 'To share what I know' })
  })
})

describe('admin user detail: a supervisor edited part by part', () => {
  const openDetail = (user: AdminUser) =>
    mount(AdminUserDetailSheet, { props: { open: true, user }, global: { stubs: { teleport: true } } })

  const supervisor = (overrides: Partial<AdminUser> = {}) =>
    student({
      id: 8,
      firstName: 'Sam',
      lastName: 'Lee',
      role: 'supervisor',
      schoolName: 'Cardinal College',
      yearLevel: null,
      supervisorGroups: [{ id: 5, name: 'BTF5', studentCount: 3 }, { id: 6, name: 'BTF6', studentCount: 2 }],
      supervisees: [
        { id: 21, name: 'Idris Novak', email: 'idris@example.com' },
        { id: 22, name: 'Tariq Mensah', email: 'tariq@example.com' }
      ],
      ...overrides
    })

  beforeEach(() => {
    vi.mocked(updateAdminUser).mockReset()
    vi.mocked(changeSupervisees).mockReset()
  })

  it('shows Account, Groups, Supervisor Details and Supervisees, and nothing at the bottom', () => {
    const wrapper = openDetail(supervisor())

    expect(wrapper.findAll('h3').map((h) => h.text())).toEqual([
      'Profile Photo',
      'Account',
      'Internal Admin Notes',
      'Groups',
      'Supervisor Details',
      'Supervisees'
    ])
    expect(wrapper.find('[data-test="admin-edit-account"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="admin-edit-supervisor-details"]').exists()).toBe(true)
    expect(wrapper.find('.admin-users-detail__footer').exists()).toBe(false)

    expect(wrapper.find('[data-test="admin-supervisor-group-names"]').text()).toBe('BTF5, BTF6')
    const rows = wrapper.find('[data-test="admin-supervisees"]').findAll('.admin-users-detail__item')
    expect(rows.map((row) => [row.find('dt').text(), row.find('dd').text()])).toEqual([
      ['Idris Novak', 'idris@example.com'],
      ['Tariq Mensah', 'tariq@example.com']
    ])
  })

  it('shows — with no groups or students', () => {
    const wrapper = openDetail(supervisor({ supervisorGroups: [], supervisees: [] }))
    expect(wrapper.find('[data-test="admin-supervisor-group-names"]').text()).toBe('—')
    expect(wrapper.find('[data-test="admin-supervisees"]').text()).toContain('—')
  })

  it('shows pronouns after the school, and edits them there', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: supervisor() })
    const wrapper = openDetail(supervisor({ pronouns: 'He/him' }))
    const rows = wrapper.findAll('[data-test="admin-supervisor-pronouns"]')
    expect(rows[0].find('dd').text()).toBe('He/him')
    const terms = rows[0].element.parentElement!.querySelectorAll('dt')
    expect([...terms].map((term) => term.textContent)).toEqual(['Name', 'School', 'Pronouns'])

    await wrapper.find('[data-test="admin-edit-supervisor-details"]').trigger('click')
    await pickAppSelect(wrapper, '[data-test="admin-supervisor-pronouns-select"]', 'They/them')
    await wrapper.find('[data-test="admin-supervisor-details-form"]').trigger('submit')
    await flushPromises()
    expect(vi.mocked(updateAdminUser).mock.calls.at(-1)![1]).toMatchObject({ pronouns: 'They/them' })
  })

  it('edits their name and school', async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: supervisor() })
    const wrapper = openDetail(supervisor())
    await wrapper.find('[data-test="admin-edit-supervisor-details"]').trigger('click')

    const form = wrapper.find('[data-test="admin-supervisor-details-form"]')
    await form.find('[data-test="admin-supervisor-school"]').setValue('St Mary College')
    await form.trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(8, {
      firstName: 'Sam',
      lastName: 'Lee',
      pronouns: '',
      supervisorSchoolName: 'St Mary College'
    })
    expect(wrapper.find('[data-test="admin-supervisor-details-form"]').exists()).toBe(false)
  })

  const listGroups = (...groups: [number, string, number][]) =>
    vi.mocked(fetchAdminGroupList).mockResolvedValue({
      items: groups.map(([id, name, students]) => ({
        // The list gives ids as text.
        id: String(id) as unknown as number,
        name,
        members: Array.from({ length: students }, (_, index) => ({
          id: String(100 + index),
          name: `S${index}`,
          email: `s${index}@example.com`,
          role: 'student',
          membershipId: index
        })),
        mentor: null,
        createdAt: '',
        updatedAt: ''
      })),
      total: groups.length,
      page: 1,
      limit: 200,
      has_more: false
    })

  it('adds a group, warning first of students moving from another supervisor', async () => {
    listGroups([5, 'BTF5', 3], [6, 'BTF6', 2], [7, 'BTF7', 2])
    vi.mocked(changeSupervisees)
      .mockResolvedValueOnce({
        changes: [
          { studentId: 31, name: 'Ana Lee', group: 'BTF7', from: 'Pat Kim', to: 'Sam Lee' },
          { studentId: 32, name: 'Ben Ng', group: 'BTF7', from: 'Pat Kim', to: 'Sam Lee' }
        ]
      })
      .mockResolvedValueOnce({ changes: [], user: supervisor() })
    const wrapper = openDetail(supervisor())
    await wrapper.find('[data-test="admin-edit-supervisor-groups"]').trigger('click')
    await flushPromises()

    const form = wrapper.find('[data-test="admin-supervisor-groups-form"]')
    expect(form.findAll('.admin-users-detail__label').map((label) => label.text())).toEqual(['Group 1', 'Group 2', 'Group 3'])
    // Theirs is recognised though the list gives text ids, so BTF7 alone is new.
    expect(await appSelectLabels(wrapper, '[data-test="admin-supervisor-group-2"]')).toEqual(['BTF7'])
    await pickAppSelect(wrapper, '[data-test="admin-supervisor-group-2"]', 'BTF7')
    await form.trigger('submit')
    await flushPromises()

    expect(changeSupervisees).toHaveBeenCalledWith(8, { addGroupIds: [7], removeGroupIds: [], preview: true })
    expect(wrapper.find('[data-test="admin-replacing"]').text()).toContain('BTF7: Ana Lee and Ben Ng move from Pat Kim to Sam Lee.')
    await wrapper.find('.admin-modal--confirm').findAll('button').find((b) => b.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(changeSupervisees).toHaveBeenLastCalledWith(8, { addGroupIds: [7], removeGroupIds: [] })
    expect(wrapper.emitted('updated')).toBeTruthy()
  })

  it('takes a student off, warning that they will have no supervisor', async () => {
    vi.mocked(fetchAdminUsers).mockResolvedValue({ items: [], total: 0, page: 1, limit: 200, hasMore: false })
    vi.mocked(changeSupervisees).mockResolvedValueOnce({
      changes: [{ studentId: 21, name: 'Idris Novak', group: 'BTF5', from: 'Sam Lee', to: null }]
    })
    const wrapper = openDetail(supervisor())
    await wrapper.find('[data-test="admin-edit-supervisees"]').trigger('click')
    await flushPromises()

    await wrapper.find('[data-test="admin-supervisee-0"] .admin-users-detail__slot-remove').trigger('click')
    await wrapper.find('[data-test="admin-supervisees-form"]').trigger('submit')
    await flushPromises()

    expect(changeSupervisees).toHaveBeenCalledWith(8, { addStudentIds: [], removeStudentIds: [21], preview: true })
    expect(wrapper.find('[data-test="admin-replacing"]').text()).toContain('BTF5: Idris Novak will have no supervisor.')
  })

  it('adds a student with no supervisor straight away, showing whose each one is', async () => {
    vi.mocked(fetchAdminUsers).mockResolvedValue({
      items: [
        student({ id: 40, firstName: 'Cara', lastName: 'Wu', email: 'cara@example.com', groupName: null, supervisorName: null }),
        student({ id: 41, firstName: 'Dan', lastName: 'Ho', email: 'dan@example.com', groupName: 'BTF9', supervisorName: 'Pat Kim' })
      ],
      total: 2,
      page: 1,
      limit: 200,
      hasMore: false
    })
    vi.mocked(changeSupervisees)
      .mockResolvedValueOnce({ changes: [{ studentId: 40, name: 'Cara Wu', group: null, from: null, to: 'Sam Lee' }] })
      .mockResolvedValueOnce({ changes: [], user: supervisor() })
    const wrapper = openDetail(supervisor())
    await wrapper.find('[data-test="admin-edit-supervisees"]').trigger('click')
    await flushPromises()

    const options = await openAppSelect(wrapper, '[data-test="admin-supervisee-add"]')
    expect(options.map((option) => option.textContent)).toEqual([
      expect.stringContaining('cara@example.com · no group · no supervisor'),
      expect.stringContaining('dan@example.com · BTF9 · supervisor: Pat Kim')
    ])
    await pickAppSelect(wrapper, '[data-test="admin-supervisee-add"]', 'Cara Wu')
    expect(wrapper.find('[data-test="admin-supervisee-2"]').text()).toContain('cara@example.com')
    await wrapper.find('[data-test="admin-supervisees-form"]').trigger('submit')
    await flushPromises()

    // Nobody moves from anyone, so no warning.
    expect(wrapper.find('[data-test="admin-replacing"]').exists()).toBe(false)
    expect(changeSupervisees).toHaveBeenLastCalledWith(8, { addStudentIds: [40], removeStudentIds: [] })
  })
})
