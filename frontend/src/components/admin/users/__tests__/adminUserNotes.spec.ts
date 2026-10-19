import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminUserFormSheet from '../AdminUserFormSheet.vue'
import AdminUserDetailContent from '../AdminUserDetailContent.vue'
import { createAdminUser, updateAdminUser } from '@/utils/adminAPI'
import type { AdminUser } from '@/utils/adminAPI'

vi.mock('@/utils/adminAPI', () => ({
  createAdminUser: vi.fn(),
  updateAdminUser: vi.fn().mockResolvedValue({ msg: 'ok', data: null }),
  setAdminUserActive: vi.fn(),
  sendGuardianConsentRequest: vi.fn(),
  fetchGuardianConsents: vi.fn(),
  downloadGuardianConsentRecord: vi.fn(),
}))

const sampleUser = (overrides: Partial<AdminUser> = {}): AdminUser => ({
  id: 42,
  firstName: 'Morgan',
  lastName: 'Lee',
  email: 'morgan.lee@example.com',
  role: 'student',
  country: { id: 1, countryName: 'Australia' },
  state: null,
  groupId: null,
  groupName: null,
  schoolName: 'Sydney High',
  mentorBackground: null,
  mentorInstitution: null,
  mentorReason: null,
  mentorMaxGroupCount: null,
  yearLevel: 11,
  guardianFirstName: 'Jordan',
  guardianLastName: 'Lee',
  guardianEmail: 'jordan.lee@example.com',
  joinPermissionReceived: true,
  joinpermResponseId: 'BTF-99',
  joinPermissionGrantedAt: null,
  pendingGuardian: null,
  mediaConsent: true,
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
  adminNotes: 'Confidential background information.',
  ...overrides,
})

describe('Admin User Notes: Detail Content Component', () => {
  beforeEach(() => {
    vi.mocked(updateAdminUser).mockClear()
  })

  it('renders existing admin notes in detail view', () => {
    const user = sampleUser({ adminNotes: 'Special dietary and accessibility context.' })
    const wrapper = mount(AdminUserDetailContent, {
      props: { user },
    })

    expect(wrapper.find('[data-test="admin-notes-section"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="admin-notes-section"] h3').text()).toBe('Internal Admin Notes')
    const display = wrapper.find('[data-test="admin-notes-display"]')
    expect(display.exists()).toBe(true)
    expect(display.text()).toBe('Special dietary and accessibility context.')
    expect(wrapper.find('[data-test="admin-notes-empty"]').exists()).toBe(false)
  })

  it('displays empty state message when user has no admin notes', () => {
    const user = sampleUser({ adminNotes: '' })
    const wrapper = mount(AdminUserDetailContent, {
      props: { user },
    })

    expect(wrapper.find('[data-test="admin-notes-section"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="admin-notes-display"]').exists()).toBe(false)
    const empty = wrapper.find('[data-test="admin-notes-empty"]')
    expect(empty.exists()).toBe(true)
    expect(empty.text()).toBe('No private notes recorded.')
  })

  it('renders image-only notes instead of showing the empty state', () => {
    const user = sampleUser({
      adminNotes: '<p><img src="data:image/png;base64,abc" alt="Context image"></p>',
    })
    const wrapper = mount(AdminUserDetailContent, {
      props: { user },
    })

    expect(wrapper.find('[data-test="admin-notes-display"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="admin-notes-content"] img').exists()).toBe(true)
    expect(wrapper.find('[data-test="admin-notes-empty"]').exists()).toBe(false)
  })

  it('shows the empty state for markup without text or media', () => {
    const user = sampleUser({ adminNotes: '<p><br></p>' })
    const wrapper = mount(AdminUserDetailContent, {
      props: { user },
    })

    expect(wrapper.find('[data-test="admin-notes-display"]').exists()).toBe(false)
    expect(wrapper.find('[data-test="admin-notes-empty"]').exists()).toBe(true)
  })

  it('does not render an inline Add note or Edit note button when plainly viewing', () => {
    const userWithNotes = sampleUser({ adminNotes: 'Some notes' })
    const wrapperWithNotes = mount(AdminUserDetailContent, { props: { user: userWithNotes } })
    expect(wrapperWithNotes.find('[data-test="edit-notes-btn"]').exists()).toBe(false)
    expect(wrapperWithNotes.text()).not.toContain('Edit note')
    expect(wrapperWithNotes.text()).not.toContain('Add note')

    const userWithoutNotes = sampleUser({ adminNotes: '' })
    const wrapperWithoutNotes = mount(AdminUserDetailContent, { props: { user: userWithoutNotes } })
    expect(wrapperWithoutNotes.find('[data-test="edit-notes-btn"]').exists()).toBe(false)
    expect(wrapperWithoutNotes.text()).not.toContain('Add note')
  })
})

const RichEditorStub = {
  name: 'RichEditor',
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template:
    '<textarea data-test="form-admin-notes" class="rich-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)"></textarea>',
}

describe('Admin User Notes: Form Sheet Component', () => {
  beforeEach(() => {
    vi.mocked(updateAdminUser).mockClear()
    vi.mocked(createAdminUser).mockClear()
  })

  it('pre-fills admin notes when editing an existing user', async () => {
    const user = sampleUser({ adminNotes: 'Existing admin note for user.' })
    const wrapper = mount(AdminUserFormSheet, {
      props: {
        modelValue: false,
        userNoun: 'Student',
        user,
        isSupervisorMode: false,
        countries: [{ id: 1, countryName: 'Australia' }],
        states: [],
        supervisors: [],
      },
      global: {
        stubs: {
          teleport: true,
          RichEditor: RichEditorStub,
          RichTextEditor: RichEditorStub,
        },
      },
    })
    await wrapper.setProps({ modelValue: true })

    const editor = wrapper.findComponent({ name: 'RichEditor' })
    expect(editor.exists()).toBe(true)
    expect(editor.props('modelValue')).toBe('Existing admin note for user.')

    const textarea = wrapper.find('[data-test="form-admin-notes"]')
    expect(textarea.exists()).toBe(true)
    expect((textarea.element as HTMLTextAreaElement).value).toBe('Existing admin note for user.')
  })

  it('sends updated admin notes on form submit when editing', async () => {
    const user = sampleUser({ adminNotes: 'Existing note' })
    const wrapper = mount(AdminUserFormSheet, {
      props: {
        modelValue: false,
        userNoun: 'Student',
        user,
        isSupervisorMode: false,
        countries: [{ id: 1, countryName: 'Australia' }],
        states: [],
        supervisors: [],
      },
      global: {
        stubs: {
          teleport: true,
          RichEditor: RichEditorStub,
          RichTextEditor: RichEditorStub,
        },
      },
    })
    await wrapper.setProps({ modelValue: true })

    await wrapper.find('[data-test="form-admin-notes"]').setValue('Updated note from form')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(updateAdminUser).toHaveBeenCalledWith(
      42,
      expect.objectContaining({ adminNotes: 'Updated note from form' }),
    )
  })

  it('submits admin notes when creating a new user', async () => {
    vi.mocked(createAdminUser).mockResolvedValueOnce({
      msg: 'ok',
      data: sampleUser({ id: 99 }),
    })

    const wrapper = mount(AdminUserFormSheet, {
      props: {
        modelValue: false,
        userNoun: 'Student',
        user: null,
        isSupervisorMode: false,
        countries: [{ id: 1, countryName: 'Australia' }],
        states: [],
        supervisors: [],
      },
      global: {
        stubs: {
          teleport: true,
          RichEditor: RichEditorStub,
          RichTextEditor: RichEditorStub,
        },
      },
    })
    await wrapper.setProps({ modelValue: true })

    await wrapper.find('#f-first').setValue('New')
    await wrapper.find('#f-last').setValue('User')
    await wrapper.find('#f-email').setValue('new.user@example.com')
    await wrapper.find('#f-country').setValue(1)
    await wrapper.find('#f-school').setValue('Sydney High')
    await wrapper.find('#f-year').setValue(10)
    await wrapper.find('.admin-users-form__interest input').setValue(true)
    await wrapper
      .find('[data-test="form-admin-notes"]')
      .setValue('Initial private admin note during creation.')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(createAdminUser).toHaveBeenCalledWith(
      expect.objectContaining({
        email: 'new.user@example.com',
        adminNotes: 'Initial private admin note during creation.',
      }),
    )
  })
})
