import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AdminEmailsPage from '@/views/admin/AdminEmailsPage.vue'
import ConfirmDialog from '@/components/admin/ConfirmDialog.vue'
import EmailEditor from '@/components/admin/emails/EmailEditor.vue'
import {
  fetchSystemEmailLog,
  fetchSystemEmailUnseenFailures,
  markSystemEmailFailuresSeen,
  fetchSystemEmailSettings,
  fetchSystemEmailTemplates,
  fetchSystemEmailTestRecipients,
  previewSystemEmailTemplate,
  restoreSystemEmailTemplate,
  testSendSystemEmailTemplate,
  updateSystemEmailSettings,
  updateSystemEmailTemplate
} from '@/utils/adminAPI'
import type { SystemEmailLogEntry, SystemEmailTemplate } from '@/utils/systemEmail'

vi.mock('@/utils/adminAPI', () => ({
  fetchSystemEmailLog: vi.fn(),
  fetchSystemEmailUnseenFailures: vi.fn(),
  markSystemEmailFailuresSeen: vi.fn(),
  fetchSystemEmailTemplates: vi.fn(),
  fetchSystemEmailSettings: vi.fn(),
  updateSystemEmailTemplate: vi.fn(),
  restoreSystemEmailTemplate: vi.fn(),
  previewSystemEmailTemplate: vi.fn(),
  testSendSystemEmailTemplate: vi.fn(),
  fetchSystemEmailTestRecipients: vi.fn(),
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

const mountPage = async () => {
  const wrapper = mount(AdminEmailsPage)
  await flushPromises()
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  // The editor's test send starts from the signed-in admin's address.
  setActivePinia(createPinia())
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
  // Most tests use an email with nothing of a person's own, so no "of" list.
  vi.mocked(fetchSystemEmailTestRecipients).mockResolvedValue(null)
})

describe('AdminEmailsPage', () => {
  it('renders every email type and the first one in the editor', async () => {
    const wrapper = await mountPage()
    const text = wrapper.text()
    expect(text).toContain('Password reset')
    expect(text).toContain('Login code')
    expect(wrapper.findComponent(EmailEditor).props('emailTemplate').key).toBe('password_reset')
  })

  it('shows who an email goes to in normal weight, apart from its bold name', async () => {
    vi.mocked(fetchSystemEmailTemplates).mockResolvedValue([
      buildTemplate({ key: 'guardian_consent_student_notice', name: 'Guardian consent sent (to student)' })
    ])
    const wrapper = await mountPage()

    for (const selector of ['.email-type-list__name', '.email-editor__title']) {
      const name = wrapper.find(selector)
      expect(name.text()).toBe('Guardian consent sent (to student)')
      expect(name.find('.email-type-list__to, .email-editor__to').text()).toBe('(to student)')
    }
  })

  it('says above Send from who a group email goes to, and nothing for an email to one person', async () => {
    const delivery = 'Each group gets one email: its students in To, and its mentors and supervisors in CC.'
    vi.mocked(fetchSystemEmailTemplates).mockResolvedValue([
      buildTemplate(),
      buildTemplate({ key: 'submission_reminder', name: 'Submission reminder', delivery })
    ])
    const wrapper = await mountPage()
    expect(wrapper.find('[data-test="delivery"]').exists()).toBe(false)

    await wrapper.findAll('.email-type-list__item')[1].trigger('click')
    await flushPromises()

    const note = wrapper.find('[data-test="delivery"]')
    expect(note.text()).toBe(delivery)
    // Just above Send from.
    expect(note.element.nextElementSibling?.querySelector('label')?.textContent).toBe('Send from')
  })

  it('lists the files the one picked would get, after the email', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('[data-test="attachments"]').exists()).toBe(false)

    vi.mocked(previewSystemEmailTemplate).mockResolvedValue({
      ...preview,
      attachments: ['2026_BTF_Student_Certificate_Liam_Dubois.docx', '2026_BTF_Marks_BTF01.docx']
    })
    await wrapper.findAll('.email-type-list__item')[1].trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 600))
    await flushPromises()

    const files = wrapper.find('[data-test="attachments"]')
    expect(files.text()).toContain('Attachments')
    expect(files.element.previousElementSibling?.classList.contains('email-preview__frame-wrap')).toBe(true)
    expect(files.findAll('li').map((li) => li.text())).toEqual([
      '2026_BTF_Student_Certificate_Liam_Dubois.docx',
      '2026_BTF_Marks_BTF01.docx'
    ])
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
    const subject = wrapper.find('#template-subject')
    expect((subject.element as HTMLInputElement).value).toBe('Reset your password')
  })

  it('shows who last edited an email and a key-aware lock reason', async () => {
    vi.mocked(fetchSystemEmailTemplates).mockResolvedValue([
      buildTemplate({
        locked: true,
        usingSavedContent: true,
        updatedBy: 'Ada Admin',
        updatedAt: '2026-09-18T10:30:00Z'
      })
    ])
    const wrapper = await mountPage()
    const text = wrapper.text()
    expect(text).toContain('Last edited by Ada Admin')
    expect(text).toContain('Account security depends on this email')

    vi.mocked(fetchSystemEmailTemplates).mockResolvedValue([
      buildTemplate({ key: 'login_code', name: 'Login code', locked: true })
    ])
    const loginWrapper = await mountPage()
    expect(loginWrapper.text()).toContain('Account sign-in would break')
  })

  it('saves edited wording through the editor', async () => {
    const wrapper = await mountPage()
    const updated = buildTemplate({
      subject: 'New subject',
      body: '',
      usingSavedContent: true
    })
    vi.mocked(updateSystemEmailTemplate).mockResolvedValue(updated)

    await wrapper.find('#template-subject').setValue('New subject')
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

  it('picks the mailbox it goes from, saved at once', async () => {
    const wrapper = await mountPage()
    vi.mocked(updateSystemEmailTemplate).mockResolvedValue(buildTemplate({ sender: 'connect' }))

    const select = wrapper.find<HTMLSelectElement>('#password_reset-sender')
    // Only the mailboxes the server can sign in to.
    expect(select.findAll('option').map((option) => option.text())).toEqual([
      'info@biotechfutures.org',
      'connect@biotechfutures.org'
    ])
    expect(select.element.value).toBe('info')
    await select.setValue('connect')
    await flushPromises()

    expect(updateSystemEmailTemplate).toHaveBeenCalledWith('password_reset', { sender: 'connect' })
    expect(wrapper.find<HTMLSelectElement>('#password_reset-sender').element.value).toBe('connect')
  })

  it('keeps Subject and Body editable while Send from saves', async () => {
    const wrapper = await mountPage()
    let finish: (template: SystemEmailTemplate) => void = () => {}
    vi.mocked(updateSystemEmailTemplate).mockReturnValue(
      new Promise((resolve) => {
        finish = resolve
      })
    )

    await wrapper.find('#password_reset-sender').setValue('connect')
    // Disabling them flashed the Subject box and dropped the Body's toolbar.
    expect(wrapper.find<HTMLInputElement>('#template-subject').element.disabled).toBe(false)
    expect(wrapper.findComponent({ name: 'RichEditor' }).props('readOnly')).toBe(false)

    finish(buildTemplate({ sender: 'connect' }))
    await flushPromises()
  })

  const dialogTitled =(wrapper: Awaited<ReturnType<typeof mountPage>>, title: string) =>
    wrapper.findAllComponents(ConfirmDialog).find((dialog) => dialog.props('title') === title)!

  it('asks before pausing all emails, and pauses only once confirmed', async () => {
    const wrapper = await mountPage()
    vi.mocked(updateSystemEmailSettings).mockResolvedValue({
      emailsEnabled: false,
      updatedAt: null
    })

    const globalSwitch = wrapper.find<HTMLInputElement>('.admin-emails__global input[role="switch"]')
    await globalSwitch.setValue(false)
    await flushPromises()

    const dialog = dialogTitled(wrapper, 'Pause all system emails?')
    expect(dialog.props('modelValue')).toBe(true)
    expect(updateSystemEmailSettings).not.toHaveBeenCalled()
    expect(globalSwitch.element.checked).toBe(true)

    await dialog.vm.$emit('confirm')
    await flushPromises()

    expect(updateSystemEmailSettings).toHaveBeenCalledWith(false)
    expect(wrapper.text()).toContain('Emails paused')
  })

  describe('the Log', () => {
    const at = (iso: string) => {
      const when = new Date(iso)
      return `${when.toLocaleDateString('en-GB')} ${when.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
    }
    const logEntry = (overrides: Partial<SystemEmailLogEntry> = {}): SystemEmailLogEntry => ({
      key: 'password_reset',
      name: 'Password reset',
      lastSentAt: null,
      lastSentBy: '',
      sentFrom: 'info@biotechfutures.org',
      toGroups: false,
      missed: [],
      ...overrides
    })
    const unreachable = "couldn't reach the mail server"

    beforeEach(() => {
      vi.mocked(fetchSystemEmailUnseenFailures).mockResolvedValue(0)
      vi.mocked(markSystemEmailFailuresSeen).mockResolvedValue(0)
      vi.mocked(fetchSystemEmailLog).mockResolvedValue([
        logEntry({
          lastSentAt: '2026-09-29T13:58:00Z',
          missed: [
            { at: '2026-09-29T13:58:00Z', people: [{ who: 'jin@seed.test (BTF06, Jin Fischer)', reason: unreachable }] },
            { at: '2026-09-28T09:00:00Z', people: [{ who: 'amy@seed.test (BTF06, Amy Chen)', reason: 'address refused' }] }
          ]
        }),
        logEntry({ key: 'login_code', name: 'Login code' }),
        logEntry({
          key: 'finalist_notification',
          name: 'Finalist notification',
          lastSentAt: '2026-09-29T13:58:00Z',
          lastSentBy: 'test1 1',
          toGroups: true,
          missed: [
            {
              at: '2026-09-29T13:58:00Z',
              people: [
                { who: 'jin@seed.test (BTF06, Jin Fischer)', reason: unreachable },
                { who: 'nadia@seed.test (BTF06, Nadia Kowalski)', reason: unreachable }
              ]
            }
          ]
        })
      ])
    })

    const openLog = async () => {
      const wrapper = await mountPage()
      await wrapper.find('[data-test="emails-log"]').trigger('click')
      await flushPromises()
      return wrapper
    }

    it('is a green button that swaps the editor for the log, and back', async () => {
      const wrapper = await mountPage()
      const button = wrapper.find('[data-test="emails-log"]')
      expect(button.classes()).toContain('btn-primary')
      expect(button.text()).toBe('Failed Sending Emails')

      await button.trigger('click')
      await flushPromises()
      expect(fetchSystemEmailLog).toHaveBeenCalledTimes(1)
      expect(wrapper.find('[data-test="emails-log-panel"]').exists()).toBe(true)
      expect(wrapper.findComponent(EmailEditor).exists()).toBe(false)
      expect(button.text()).toBe('Back to emails')

      await button.trigger('click')
      expect(wrapper.find('[data-test="emails-log-panel"]').exists()).toBe(false)
      expect(wrapper.findComponent(EmailEditor).exists()).toBe(true)
    })

    it('starts on All emails, above the same list, with each one that missed someone', async () => {
      const wrapper = await openLog()
      const all = wrapper.find('[data-test="all-emails"]')
      expect(all.text()).toBe('All emails')
      expect(all.classes()).toContain('is-selected')
      expect(wrapper.findAll('.email-type-list__items .email-type-list__item')).toHaveLength(2)

      // Where bounces go comes first here, naming no mailbox.
      const panel = wrapper.find('[data-test="emails-log-panel"]')
      expect(panel.find('p').attributes('data-test')).toBe('log-all-note')
      expect(panel.find('[data-test="log-all-note"]').text()).toBe(
        "Any that can't be delivered, such as a mistyped address or one a school's mail server refuses, come back " +
          'to the email address they were sent from.'
      )

      const emails = wrapper.findAll('[data-test="log-email"]')
      // Login code missed nobody, so isn't listed.
      expect(emails).toHaveLength(2)
      // Two sends: each its own time. One send: its time beside the name.
      expect(emails[0].find('h3').text()).toBe('Password reset')
      expect(emails[0].findAll('p.email-log__when').map((when) => when.text())).toEqual([
        at('2026-09-29T13:58:00Z'),
        at('2026-09-28T09:00:00Z')
      ])
      expect(emails[0].text()).toContain(`jin@seed.test (BTF06, Jin Fischer) · ${unreachable}`)
      expect(emails[1].find('h3').text()).toBe(`Finalist notification ${at('2026-09-29T13:58:00Z')}`)
      expect(emails[1].findAll('li')).toHaveLength(2)
    })

    it('shows one email as Notify Finalists does', async () => {
      const wrapper = await openLog()
      // Password reset, below All emails.
      await wrapper.findAll('.email-type-list__items .email-type-list__item')[0].trigger('click')

      const panel = wrapper.find('[data-test="emails-log-panel"]')
      expect(panel.find('[data-test="log-last-emailed"]').text()).toBe(
        `Last Emailed at ${at('2026-09-29T13:58:00Z')}.`
      )
      expect(panel.find('.email-log__note').text()).toBe(
        "Emails can take a few minutes to arrive. Any that can't be delivered, such as a mistyped address " +
          "or one a school's mail server refuses, come back to info@biotechfutures.org."
      )
      expect(panel.find('[data-test="log-missed"]').text()).toContain("Couldn't be emailed:")
      expect(panel.findAll('[data-test="log-missed"] li')).toHaveLength(2)
    })

    it('names who last sent an email and notes a group email still reaches the rest', async () => {
      vi.mocked(fetchSystemEmailTemplates).mockResolvedValue([
        buildTemplate({ key: 'finalist_notification', name: 'Finalist notification' })
      ])
      const wrapper = await openLog()
      await wrapper.find('.email-type-list__items .email-type-list__item').trigger('click')

      expect(wrapper.find('[data-test="log-last-emailed"]').text()).toBe(
        `Last Emailed at ${at('2026-09-29T13:58:00Z')} by test1 1.`
      )
      expect(wrapper.find('.email-log__note').text()).toMatch(/and the rest of the group still gets it\.$/)
    })

    it('shows a red count of failures nobody has seen, gone once someone looks', async () => {
      vi.mocked(fetchSystemEmailUnseenFailures).mockResolvedValue(3)
      const wrapper = await mountPage()
      expect(wrapper.find('[data-test="failed-unseen"]').text()).toBe('3')

      await wrapper.find('[data-test="emails-log"]').trigger('click')
      await flushPromises()
      expect(markSystemEmailFailuresSeen).toHaveBeenCalledTimes(1)
      expect(wrapper.find('[data-test="failed-unseen"]').exists()).toBe(false)
    })

    it('shows no count with nothing unseen, and 99+ past 99', async () => {
      expect((await mountPage()).find('[data-test="failed-unseen"]').exists()).toBe(false)

      vi.mocked(fetchSystemEmailUnseenFailures).mockResolvedValue(140)
      expect((await mountPage()).find('[data-test="failed-unseen"]').text()).toBe('99+')
    })

    it('counts leaving any of its pages as looking too', async () => {
      const wrapper = await openLog()
      expect(markSystemEmailFailuresSeen).toHaveBeenCalledTimes(1)

      // All emails to one email, and back.
      await wrapper.find('.email-type-list__items .email-type-list__item').trigger('click')
      await wrapper.find('[data-test="all-emails"]').trigger('click')
      expect(markSystemEmailFailuresSeen).toHaveBeenCalledTimes(3)

      await wrapper.find('[data-test="emails-log"]').trigger('click')
      expect(markSystemEmailFailuresSeen).toHaveBeenCalledTimes(4)

      // Leaving the page with it open.
      await wrapper.find('[data-test="emails-log"]').trigger('click')
      wrapper.unmount()
      expect(markSystemEmailFailuresSeen).toHaveBeenCalledTimes(6)
    })

    it('says when nothing has been sent and when nobody was missed', async () => {
      vi.mocked(fetchSystemEmailLog).mockResolvedValue([logEntry()])
      const wrapper = await openLog()
      expect(wrapper.find('[data-test="log-none-missed"]').text()).toBe('Every email reached everyone it was sent to.')

      await wrapper.find('.email-type-list__items .email-type-list__item').trigger('click')
      expect(wrapper.find('[data-test="log-last-emailed"]').text()).toBe('Not emailed yet.')
      expect(wrapper.find('[data-test="log-missed"]').exists()).toBe(false)
    })
  })

  it('keeps emails on when the pause is cancelled', async () => {
    const wrapper = await mountPage()
    const globalSwitch = wrapper.find<HTMLInputElement>('.admin-emails__global input[role="switch"]')
    await globalSwitch.setValue(false)
    await flushPromises()

    await dialogTitled(wrapper, 'Pause all system emails?').vm.$emit('update:modelValue', false)
    await flushPromises()

    expect(updateSystemEmailSettings).not.toHaveBeenCalled()
    expect(globalSwitch.element.checked).toBe(true)
    expect(wrapper.text()).toContain('Emails on')
  })

  it('turns paused emails back on without asking', async () => {
    vi.mocked(fetchSystemEmailSettings).mockResolvedValue({ emailsEnabled: false, updatedAt: null })
    const wrapper = await mountPage()
    vi.mocked(updateSystemEmailSettings).mockResolvedValue({ emailsEnabled: true, updatedAt: null })

    await wrapper.find('.admin-emails__global input[role="switch"]').setValue(true)
    await flushPromises()

    expect(updateSystemEmailSettings).toHaveBeenCalledWith(true)
    expect(dialogTitled(wrapper, 'Pause all system emails?').props('modelValue')).toBe(false)
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

    const dialog = dialogTitled(wrapper, 'Restore default wording?')
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

    // Unchanged built-in wording is sent from the template file.
    expect(testSendSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {})
    expect(wrapper.text()).toContain('admin@example.com')
  })

  it('sends a test to the address typed, with Save green and Restore styled like it', async () => {
    const wrapper = await mountPage()
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'tester@example.com',
      sentFrom: 'info@biotechfutures.org'
    })
    const control = wrapper.find('[data-test="test-email"]')
    const send = control.findAll('button').find((button) => button.text() === 'Send Test')!

    await control.find('input').setValue('tester@example.com')
    await send.trigger('click')
    await flushPromises()

    expect(testSendSystemEmailTemplate).toHaveBeenCalledWith('password_reset', { to: 'tester@example.com' })
    expect(control.text()).toContain('Test sent to tester@example.com.')
    // Save is the green button; Restore default and Send Test share the outlined look.
    const button = (label: string) => wrapper.findAll('button').find((b) => b.text() === label)!
    expect(button('Save changes').classes()).toEqual(expect.arrayContaining(['btn', 'btn-primary', 'btn-sm']))
    for (const label of ['Restore default', 'Send Test']) {
      expect(button(label).classes()).toEqual(expect.arrayContaining(['btn', 'btn-outline', 'btn-sm']))
    }
    // An email with nothing of a person's own has no "of" list.
    expect(control.find('[data-test="test-of"]').exists()).toBe(false)
  })

  it('tests an email as the group or person picked from its list', async () => {
    vi.mocked(fetchSystemEmailTestRecipients).mockResolvedValue([
      { value: '7', label: '(BTF1, mentor) Aga Smith' },
      { value: '9', label: '(BTF2) Ben Bell' }
    ])
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'tester@example.com'
    })
    const wrapper = await mountPage()
    const control = wrapper.find('[data-test="test-email"]')
    const of = control.find('[data-test="test-of"]')

    expect(fetchSystemEmailTestRecipients).toHaveBeenCalledWith('password_reset')
    expect(control.text()).toMatch(/Send Test\s*of\s*(.|\n)*to/)
    expect(of.findAll('option').map((option) => option.text())).toEqual([
      '(BTF1, mentor) Aga Smith',
      '(BTF2) Ben Bell'
    ])
    // The first one to start with, with no lock on an email that can be switched off.
    expect((of.element as HTMLSelectElement).value).toBe('7')
    expect(control.find('button .fa-lock').exists()).toBe(false)

    await of.setValue('9')
    await control.find('input').setValue('tester@example.com')
    await control.findAll('button').find((button) => button.text() === 'Send Test')!.trigger('click')
    await flushPromises()

    expect(testSendSystemEmailTemplate).toHaveBeenCalledWith('password_reset', {
      to: 'tester@example.com',
      of: '9'
    })
  })

  it('falls back to the sample details when nobody is on the list yet', async () => {
    vi.mocked(fetchSystemEmailTestRecipients).mockResolvedValue([])
    vi.mocked(testSendSystemEmailTemplate).mockResolvedValue({
      key: 'password_reset',
      sentTo: 'tester@example.com'
    })
    const wrapper = await mountPage()
    const control = wrapper.find('[data-test="test-email"]')
    const of = control.find('[data-test="test-of"]')

    expect(of.text()).toBe('Nobody yet (sample details)')
    expect(of.attributes('disabled')).toBeDefined()

    await control.find('input').setValue('tester@example.com')
    await control.findAll('button').find((button) => button.text() === 'Send Test')!.trigger('click')
    await flushPromises()

    expect(testSendSystemEmailTemplate).toHaveBeenCalledWith('password_reset', { to: 'tester@example.com' })
  })

  it('loads the list again for each email picked', async () => {
    vi.mocked(fetchSystemEmailTestRecipients).mockImplementation(async (key) =>
      key === 'login_code' ? [{ value: '3', label: '(BTF3) Cai Chen' }] : null
    )
    const wrapper = await mountPage()
    expect(wrapper.find('[data-test="test-of"]').exists()).toBe(false)

    await wrapper.findAll('.email-type-list__item')[1].trigger('click')
    await flushPromises()

    expect(fetchSystemEmailTestRecipients).toHaveBeenLastCalledWith('login_code')
    expect(wrapper.find('[data-test="test-of"]').text()).toBe('(BTF3) Cai Chen')
    // A critical email can't be test sent: Send Test shows a lock and is off,
    // while anyone can still be picked and an address typed.
    const control = wrapper.find('[data-test="test-email"]')
    const send = control.find('button')
    expect(send.find('.fa-lock').exists()).toBe(true)
    expect(send.attributes('disabled')).toBeDefined()
    expect(control.find('input').attributes('disabled')).toBeUndefined()
    expect(control.find('[data-test="test-of"]').attributes('disabled')).toBeUndefined()
    expect(control.find('[data-test="test-of"] .fa-lock').exists()).toBe(false)
  })
})
