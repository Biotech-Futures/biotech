import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailSheet from '../AdminUserDetailSheet.vue'
import {
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
  setAdminUserActive,
  updateAdminUser
} from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'
import { appSelectLabels, openAppSelect, pickAppSelect } from '@/__tests__/appSelect'
import type { AdminGroupDetail, AdminUser } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', () => ({
  createAdminUser: vi.fn(),
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
  fetchAdminCountries: vi.fn(),
  fetchAdminStates: vi.fn()
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

  it('puts Guardian & consent under Interests, before Account', async () => {
    const wrapper = await openForm(student())
    const sections = wrapper.findAll('.admin-users-form__section').map((section) => section.text())

    expect(sections).toEqual(['Student details', 'Interests *', 'Guardian & consent', 'Account'])
  })

  it('sends no guardian or consent fields when they are untouched', async () => {
    const wrapper = await openForm(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'R_1',
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))
    await wrapper.find('#f-year').setValue(11)

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
    for (const fn of [updateAdminUser, confirmStudentAssignments, removeGroupMember, fetchAdminUser]) {
      vi.mocked(fn).mockReset()
    }
  })

  it('shows Account, then each part with its own Edit, and no buttons at the bottom', () => {
    const wrapper = openDetail(student({ supervisorName: 'Sam Lee', supervisorEmail: 'sam@example.com', groupName: 'BTF1' }))

    const headings = wrapper.findAll('h3').map((h) => h.text())
    expect(headings).toEqual(['Account', 'Supervisor and Group', 'Student Details', 'Guardian Details'])
    for (const part of ['account', 'details', 'guardian', 'supervisor']) {
      expect(wrapper.find(`[data-test="admin-edit-${part}"]`).exists()).toBe(true)
    }
    expect(wrapper.find('[data-test="admin-supervisor-group"]').text()).toContain('BTF1')
    expect(wrapper.find('.admin-users-detail__footer').exists()).toBe(false)
  })

  it('keeps Close and Edit at the bottom for other roles', () => {
    const wrapper = openDetail(student({ role: 'mentor' }))

    expect(wrapper.find('.admin-users-detail__footer').text()).toContain('Close')
    expect(wrapper.find('[data-test="admin-edit-details"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-edit-account"]').exists()).toBe(false)
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
    expect(wrapper.find('[data-test="admin-account"]').text()).toContain('Saved.')
  })

  it("picks Australia's states, and types the state elsewhere", async () => {
    vi.mocked(updateAdminUser).mockResolvedValue({ msg: 'ok', data: student() })
    const wrapper = openDetail(inNsw())
    await editAccount(wrapper)

    expect(await appSelectLabels(wrapper, '[data-test="admin-state-select"]')).toEqual(['No state', 'NSW', 'VIC'])
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
      interests: ['Biomedical Innovations']
    })
    expect(wrapper.emitted('updated')).toEqual([[updated]])
    expect(wrapper.find('[data-test="admin-details-form"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-student-details"]').text()).toContain('Saved.')
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
    expect(wrapper.find('[data-test="admin-supervisor-group"]').text()).toContain('Saved.')
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
