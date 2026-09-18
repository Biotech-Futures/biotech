import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AdminEmailsPage from '@/views/admin/AdminEmailsPage.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import EmailEditor from '@/components/admin/emails/EmailEditor.vue'
import {
  fetchSystemEmailSettings,
  fetchSystemEmailTemplates,
  previewSystemEmailTemplate,
  restoreSystemEmailTemplate,
  testSendSystemEmailTemplate,
  updateSystemEmailSettings,
  updateSystemEmailTemplate
} from '@/utils/adminAPI'
import type { SystemEmailTemplate } from '@/utils/systemEmail'

vi.mock('@/utils/adminAPI', () => ({
  fetchSystemEmailTemplates: vi.fn(),
  fetchSystemEmailSettings: vi.fn(),
  updateSystemEmailTemplate: vi.fn(),
  restoreSystemEmailTemplate: vi.fn(),
  previewSystemEmailTemplate: vi.fn(),
  testSendSystemEmailTemplate: vi.fn(),
  updateSystemEmailSettings: vi.fn()
}))

vi.mock('@/components/admin/RichEditor.vue', () => ({
  __esModule: true,
  default: {
    name: 'RichEditor',
    props: ['modelValue', 'emailMode', 'compact', 'readOnly'],
    emits: ['update:modelValue', 'change', 'focus'],
    template:
      '<textarea class="rich-editor-stub" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />'
  }
}))

const buildTemplate = (overrides: Partial<SystemEmailTemplate> = {}): SystemEmailTemplate => ({
  key: 'password_reset',
  name: 'Password reset',
  description: 'Sent when a user asks to reset their password.',
  enabled: true,
  locked: false,
  usingSavedContent: false,
  defaultSubject: 'Reset your password',
  defaultBody: '<p>Hi Alex, reset your password.</p>',
  subject: '',
  body: '',
  updatedAt: null,
  mergeTags: [
    { name: 'first_name', description: 'Recipient first name', sample: 'Alex', html: false }
  ],
  ...overrides
})

const preview = {
  key: 'password_reset',
  subject: 'Reset your password',
  html: '<!doctype html><html><body>Reset</body></html>',
  text: 'Reset'
}

const mountPage = async () => {
  const wrapper = mount(AdminEmailsPage)
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchSystemEmailTemplates).mockResolvedValue([
    buildTemplate(),
    buildTemplate({
      key: 'login_code',
      name: 'Login code',
      description: 'The sign-in code email.',
      locked: true,
      defaultSubject: 'Your login code'
    })
  ])
  vi.mocked(fetchSystemEmailSettings).mockResolvedValue({ emailsEnabled: true, updatedAt: null })
  vi.mocked(previewSystemEmailTemplate).mockResolvedValue(preview)
})

describe('AdminEmailsPage', () => {
  it('renders every email type and the first one in the editor', async () => {
    const wrapper = await mountPage()
    const text = wrapper.text()
    expect(text).toContain('Password reset')
    expect(text).toContain('Login code')
    expect(wrapper.findComponent(EmailEditor).props('emailTemplate').key).toBe('password_reset')
  })

  it('switches the editor to the selected email', async () => {
    const wrapper = await mountPage()
    const items = wrapper.findAll('.email-type-list__item')
    await items[1].trigger('click')
    await flushPromises()

    expect(wrapper.findComponent(EmailEditor).props('emailTemplate').key).toBe('login_code')
  })

  it('pre-fills the editor with the built-in wording', async () => {
    const wrapper = await mountPage()
    const subject = wrapper.find('#email-subject')
    expect((subject.element as HTMLInputElement).value).toBe('Reset your password')
  })

  it('saves edited wording through the editor', async () => {
    const wrapper = await mountPage()
    const updated = buildTemplate({
      subject: 'New subject',
      body: '',
      usingSavedContent: true
    })
    vi.mocked(updateSystemEmailTemplate).mockResolvedValue(updated)

    await wrapper.find('#email-subject').setValue('New subject')
    const saveButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Save changes'))
    expect(saveButton).toBeTruthy()
    await saveButton!.trigger('click')
    await flushPromises()

    expect(updateSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {
      subject: 'New subject',
      body: '<p>Hi Alex, reset your password.</p>'
    })
  })

  it('flips the global switch', async () => {
    const wrapper = await mountPage()
    vi.mocked(updateSystemEmailSettings).mockResolvedValue({
      emailsEnabled: false,
      updatedAt: null
    })

    const globalSwitch = wrapper.find('.admin-emails__global input[role="switch"]')
    await globalSwitch.setValue(false)
    await flushPromises()

    expect(updateSystemEmailSettings).toHaveBeenCalledWith(false)
    expect(wrapper.text()).toContain('Emails paused')
  })

  it('confirms before restoring default wording', async () => {
    const wrapper = await mountPage()
    vi.mocked(restoreSystemEmailTemplate).mockResolvedValue(
      buildTemplate({ usingSavedContent: false })
    )

    // Restore is only meaningful once there is saved content to drop.
    const editor = wrapper.findComponent(EmailEditor)
    await editor.vm.$emit('restore')
    await flushPromises()

    const dialog = wrapper.findComponent(ConfirmDialog)
    expect(dialog.props('modelValue')).toBe(true)

    await dialog.vm.$emit('confirm')
    await flushPromises()

    expect(restoreSystemEmailTemplate).toHaveBeenCalledWith('password_reset')
  })

  it('shows a load error without rendering the editor', async () => {
    vi.mocked(fetchSystemEmailTemplates).mockRejectedValue(new Error('Request failed'))
    const wrapper = await mountPage()

    expect(wrapper.text()).toContain('Request failed')
    expect(wrapper.findComponent(EmailEditor).exists()).toBe(false)
  })

  it('sends a test email for the selected type', async () => {
    const wrapper = await mountPage()
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'admin@example.com'
    })

    await wrapper.findComponent(EmailEditor).vm.$emit('test-send')
    await flushPromises()

    expect(testSendSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {
      subject: 'Reset your password',
      body: '<p>Hi Alex, reset your password.</p>'
    })
    expect(wrapper.text()).toContain('admin@example.com')
  })
})
