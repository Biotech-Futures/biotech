import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailSheet from '../AdminUserDetailSheet.vue'
import { updateAdminUser } from '@/utils/adminAPI'
import type { AdminUser } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', () => ({
  createAdminUser: vi.fn(),
  updateAdminUser: vi.fn().mockResolvedValue({ msg: 'ok', data: null }),
  setAdminUserActive: vi.fn()
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
