import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { useSystemEmails } from '@/composables/admin/useSystemEmails'
import {
  fetchSystemEmailSettings,
  fetchSystemEmailTemplates,
  fetchSystemEmailTestRecipients,
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
  fetchSystemEmailTestRecipients: vi.fn(),
  updateSystemEmailSettings: vi.fn()
}))

vi.mock('@/utils/apiError', () => ({
  logApiError: vi.fn()
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
  updatedBy: null,
  updatedAt: null,
  sender: 'info',
  senders: [
    { key: 'info', address: 'info@biotechfutures.org' },
    { key: 'connect', address: 'connect@biotechfutures.org' }
  ],
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

const loadOnce = async (templates: SystemEmailTemplate[]) => {
  vi.mocked(fetchSystemEmailTemplates).mockResolvedValue(templates)
  vi.mocked(fetchSystemEmailSettings).mockResolvedValue({ emailsEnabled: true, updatedAt: null })
  vi.mocked(previewSystemEmailTemplate).mockResolvedValue(preview)
  const view = useSystemEmails()
  await view.load()
  return view
}

// Lets the selected email's "of" list load and the preview it starts finish.
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchSystemEmailTestRecipients).mockResolvedValue(null)
})

describe('useSystemEmails', () => {
  it('loads templates and settings and selects the first email', async () => {
    const view = await loadOnce([buildTemplate()])
    expect(view.templates.value).toHaveLength(1)
    expect(view.selectedKey.value).toBe('password_reset')
    expect(view.emailsEnabled.value).toBe(true)
    // Uncustomised emails pre-fill with the built-in wording.
    expect(view.draft.value).toEqual({
      subject: 'Reset your password',
      body: '<p>Hi Alex, reset your password.</p>'
    })
    expect(view.dirty.value).toBe(false)
  })

  it('marks the draft dirty only when it diverges from the saved wording', async () => {
    const view = await loadOnce([
      buildTemplate({ subject: 'Saved', body: '<p>Saved</p>', usingSavedContent: true })
    ])
    expect(view.dirty.value).toBe(false)

    view.setSubject('Saved!')
    expect(view.dirty.value).toBe(true)

    view.setSubject('Saved')
    expect(view.dirty.value).toBe(false)
  })

  it('saves wording, updates the row and refreshes the preview', async () => {
    const view = await loadOnce([buildTemplate()])
    const saved = buildTemplate({ subject: 'Hi {{ first_name }}', body: '<p>Hi</p>', usingSavedContent: true })
    vi.mocked(updateSystemEmailTemplate).mockResolvedValue(saved)

    view.setSubject('Hi {{ first_name }}')
    view.setBody('<p>Hi</p>')
    await view.save()

    expect(updateSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {
      subject: 'Hi {{ first_name }}',
      body: '<p>Hi</p>'
    })
    expect(view.templates.value[0]).toEqual(saved)
    expect(view.dirty.value).toBe(false)
    expect(previewSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {
      subject: 'Hi {{ first_name }}',
      body: '<p>Hi</p>'
    })
    expect(view.notice.value).toContain('saved')
  })

  it('auto-refreshes the preview after a typing pause', async () => {
    vi.useFakeTimers()
    try {
      const view = await loadOnce([buildTemplate()])
      vi.mocked(previewSystemEmailTemplate).mockClear()

      view.setSubject('Almost done')
      await nextTick()
      vi.advanceTimersByTime(400)
      expect(previewSystemEmailTemplate).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(200)
      // The body is untouched, so the server renders it from the template file.
      expect(previewSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {
        subject: 'Almost done'
      })
      expect(view.preview.value).toEqual(preview)
    } finally {
      vi.useRealTimers()
    }
  })

  it('previews and tests the template file until the built-in wording is changed', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'admin@example.com'
    })

    await view.refreshPreview()
    await view.testSend()
    expect(previewSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', {})
    expect(testSendSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', {})

    view.setBody('<p>Hi</p>')
    await view.refreshPreview()
    expect(previewSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', {
      body: '<p>Hi</p>'
    })
  })

  it('always previews saved wording as it is in the editor', async () => {
    const view = await loadOnce([
      buildTemplate({ subject: 'Saved', body: '<p>Saved</p>', usingSavedContent: true })
    ])

    await view.refreshPreview()
    expect(previewSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', {
      subject: 'Saved',
      body: '<p>Saved</p>'
    })
  })

  it('surfaces a save failure without clearing the draft', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(updateSystemEmailTemplate).mockRejectedValue(new Error('Unsupported merge tag'))

    view.setSubject('{{ nope }}')
    await view.save()

    expect(view.error.value).toBe('Unsupported merge tag')
    expect(view.draft.value.subject).toBe('{{ nope }}')
  })

  it('toggles a single email and ignores attempts to disable a locked one', async () => {
    const locked = buildTemplate({ key: 'login_code', name: 'Login code', locked: true })
    const view = await loadOnce([locked])
    const updated = { ...locked, enabled: false }
    vi.mocked(updateSystemEmailTemplate).mockResolvedValue(updated)

    await view.toggleEnabled(locked, false)
    expect(updateSystemEmailTemplate).not.toHaveBeenCalled()

    const unlocked = buildTemplate()
    view.templates.value = [unlocked]
    await view.toggleEnabled(unlocked, false)
    expect(updateSystemEmailTemplate).toHaveBeenCalledWith('password_reset', { enabled: false })
  })

  it('updates the global switch', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(updateSystemEmailSettings).mockResolvedValue({ emailsEnabled: false, updatedAt: null })

    await view.toggleGlobal(false)

    expect(updateSystemEmailSettings).toHaveBeenCalledWith(false)
    expect(view.emailsEnabled.value).toBe(false)
    expect(view.notice.value).toContain('paused')
  })

  it('restores defaults but keeps the enabled state', async () => {
    const view = await loadOnce([
      buildTemplate({
        subject: 'Custom',
        body: '<p>Custom</p>',
        usingSavedContent: true,
        enabled: false
      })
    ])
    const restored = buildTemplate({ usingSavedContent: false, enabled: false })
    vi.mocked(restoreSystemEmailTemplate).mockResolvedValue(restored)

    await view.restore()

    expect(restoreSystemEmailTemplate).toHaveBeenCalledWith('password_reset')
    expect(view.draft.value).toEqual({
      subject: 'Reset your password',
      body: '<p>Hi Alex, reset your password.</p>'
    })
    expect(view.templates.value[0].enabled).toBe(false)
  })

  it('sends a test to the current admin and reports the address', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'admin@example.com'
    })

    await view.testSend()

    expect(view.testResult.value).toEqual({ ok: true, text: 'Test sent to admin@example.com.' })
  })

  it('sends a test to a typed address, with where a bounce goes', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'tester@example.com',
      sentFrom: 'info@biotechfutures.org'
    })

    await view.testSend('tester@example.com')

    expect(testSendSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', { to: 'tester@example.com' })
    expect(view.testResult.value?.ok).toBe(true)
    expect(view.testResult.value?.text).toContain('Test sent to tester@example.com.')
    expect(view.testResult.value?.text).toContain('comes back to info@biotechfutures.org')
  })

  it('sends a test as the one picked, else with the samples', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'tester@example.com'
    })

    view.testOf.value = '9'
    await view.testSend('tester@example.com')
    expect(testSendSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', {
      to: 'tester@example.com',
      of: '9'
    })

    view.testOf.value = ''
    await view.testSend('tester@example.com')
    expect(testSendSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', { to: 'tester@example.com' })
  })

  it('loads who a test can be of, picks the first and previews the email as theirs', async () => {
    vi.mocked(fetchSystemEmailTestRecipients).mockResolvedValue([
      { value: '7', label: '(BTF1, mentor) Aga Smith' },
      { value: '9', label: '(BTF2) Ben Bell' }
    ])
    const view = await loadOnce([buildTemplate()])
    await settle()

    expect(fetchSystemEmailTestRecipients).toHaveBeenCalledWith('password_reset')
    expect(view.testOf.value).toBe('7')
    expect(previewSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', { of: '7' })

    view.testOf.value = '9'
    await settle()
    expect(previewSystemEmailTemplate).toHaveBeenLastCalledWith('password_reset', { of: '9' })
  })

  it('starts each email with its own list, never the pick from the last one', async () => {
    vi.mocked(fetchSystemEmailTestRecipients).mockImplementation(async (key) =>
      key === 'login_code' ? [{ value: '3', label: '(BTF3) Cai Chen' }] : [{ value: '7', label: '(BTF1) Amy' }]
    )
    const view = await loadOnce([buildTemplate(), buildTemplate({ key: 'login_code', name: 'Login code' })])
    await settle()
    expect(view.testOf.value).toBe('7')

    view.select('login_code')
    await settle()

    expect(view.testOf.value).toBe('3')
    expect(previewSystemEmailTemplate).not.toHaveBeenCalledWith('login_code', { of: '7' })
    expect(previewSystemEmailTemplate).toHaveBeenLastCalledWith('login_code', { of: '3' })
  })

  it('reports a failed test send beside the button', async () => {
    const view = await loadOnce([buildTemplate()])
    vi.mocked(testSendSystemEmailTemplate).mockRejectedValue(new Error('smtp down'))

    await view.testSend('tester@example.com')

    expect(view.testResult.value?.ok).toBe(false)
    expect(view.error.value).toBe('')
  })

  it('loads all emails when the server call fails', async () => {
    vi.mocked(fetchSystemEmailTemplates).mockRejectedValue(new Error('network down'))
    vi.mocked(fetchSystemEmailSettings).mockResolvedValue({ emailsEnabled: true, updatedAt: null })

    const view = useSystemEmails()
    await view.load()

    expect(view.loading.value).toBe(false)
    expect(view.error.value).toBe('network down')
    expect(view.templates.value).toEqual([])
  })
})
