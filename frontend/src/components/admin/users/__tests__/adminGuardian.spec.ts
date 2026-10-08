import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailSheet from '../AdminUserDetailSheet.vue'
import {
  downloadGuardianConsentRecord,
  fetchGuardianConsents,
  sendGuardianConsentRequest,
  updateAdminUser,
  withdrawGuardianConsent
} from '@/utils/adminAPI'
import { ApiError } from '@/utils/apiError'
import type { AdminUser } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', () => ({
  createAdminUser: vi.fn(),
  updateAdminUser: vi.fn().mockResolvedValue({ msg: 'ok', data: null }),
  setAdminUserActive: vi.fn(),
  sendGuardianConsentRequest: vi.fn(),
  fetchGuardianConsents: vi.fn(),
  withdrawGuardianConsent: vi.fn(),
  downloadGuardianConsentRecord: vi.fn()
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

  it('records consent from a response ID', async () => {
    const wrapper = await openForm(student())
    await wrapper.find('#f-consent').setValue('R_paper')

    expect((await save(wrapper))?.joinpermResponseId).toBe('R_paper')
  })

  it('revokes consent when the response ID is cleared', async () => {
    const wrapper = await openForm(student({ joinPermissionReceived: true, joinpermResponseId: 'R_1' }))
    expect(wrapper.text()).toContain('Clearing this ID revokes it')
    await wrapper.find('#f-consent').setValue('')

    expect((await save(wrapper))?.joinpermResponseId).toBe('')
  })

  it('revokes consent with no response on record only when asked', async () => {
    const unverified = student({ joinPermissionReceived: true, joinpermResponseId: null })

    const kept = await openForm(unverified)
    expect(kept.text()).toContain('no consent form response is on record')
    expect(await save(kept)).not.toHaveProperty('joinpermResponseId')

    const revoked = await openForm(unverified)
    await revoked.find('#f-revoke').setValue(true)
    expect((await save(revoked))?.joinpermResponseId).toBe('')
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

  it('flags consent with no response on record', () => {
    const wrapper = openDetail(student({ joinPermissionReceived: true, joinpermResponseId: null }))

    expect(wrapper.find('[data-test="admin-consent"]').text()).toBe('Marked received, no response on record')
  })

  it('shows recorded consent and a pending change', () => {
    const wrapper = openDetail(student({
      joinPermissionReceived: true,
      joinpermResponseId: 'R_1',
      pendingGuardian: { firstName: 'Robin', lastName: 'Carer', email: 'robin@example.com', requestedAt: '2026-10-01T00:00:00Z' }
    }))

    expect(wrapper.find('[data-test="admin-consent"]').text()).toBe('Received')
    expect(wrapper.text()).toContain('R_1')
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

describe('admin user detail: signed consent and withdrawal', () => {
  const openDetail = (user: AdminUser) =>
    mount(AdminUserDetailSheet, { props: { open: true, user }, global: { stubs: { teleport: true } } })
  const consented = (overrides: Partial<AdminUser> = {}) =>
    student({ joinPermissionReceived: true, joinpermResponseId: 'BTF-3', mediaConsent: true, ...overrides })

  beforeEach(() => {
    vi.mocked(fetchGuardianConsents).mockReset()
    vi.mocked(withdrawGuardianConsent).mockReset()
  })

  it('shows the media consent answer', () => {
    expect(openDetail(consented()).find('[data-test="admin-media-consent"]').text()).toContain('Yes')
    expect(openDetail(consented({ mediaConsent: false })).find('[data-test="admin-media-consent"]').text())
      .toContain('not permitted at in-person events')
    expect(openDetail(consented({ joinpermResponseId: 'R_1', mediaConsent: null })).find('[data-test="admin-media-consent"]').text())
      .toContain('Not recorded')
  })

  it('shows the signed form only for consent signed on the platform', () => {
    expect(openDetail(consented()).find('[data-test="admin-view-consent"]').exists()).toBe(true)
    expect(openDetail(consented({ joinpermResponseId: 'R_1' })).find('[data-test="admin-view-consent"]').exists()).toBe(false)
  })

  it('loads the signed form with its signature', async () => {
    vi.mocked(fetchGuardianConsents).mockResolvedValue([{
      id: 3,
      reference: 'BTF-3',
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

  it('hides the media withdrawal once media consent is already no', () => {
    expect(openDetail(consented({ mediaConsent: false })).find('[data-test="admin-withdraw-media"]').exists()).toBe(false)
  })

  it('records a withdrawal after confirming and passes the updated user up', async () => {
    const updated = consented({ mediaConsent: false })
    vi.mocked(withdrawGuardianConsent).mockResolvedValue({ msg: 'Media consent withdrawn.', data: updated })
    const wrapper = openDetail(consented())

    await wrapper.find('[data-test="admin-withdraw-media"]').trigger('click')
    wrapper.findComponent({ name: 'ConfirmDialog' }).vm.$emit('confirm')
    await flushPromises()

    expect(withdrawGuardianConsent).toHaveBeenCalledWith(7, true)
    expect(wrapper.emitted('updated')?.[0]).toEqual([updated])
    expect(wrapper.find('[data-test="admin-consent-message"]').text()).toBe('Media consent withdrawn.')
  })
})
