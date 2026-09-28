import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NonFinalistPage from '@/views/grading/NonFinalistPage.vue'
import {
  fetchSymposiumEmail,
  previewSymposiumEmail,
  sendSymposiumEmailBatch,
  type SymposiumEmail,
  type SymposiumEmailStatus
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchTestEmailRecipients: vi.fn(async () => ({ recipients: [] })),
  sendTestEmail: vi.fn(),
  fetchSymposiumEmail: vi.fn(),
  previewSymposiumEmail: vi.fn(),
  sendSymposiumEmailBatch: vi.fn()
}))
const statusMock = vi.mocked(fetchSymposiumEmail)
const previewMock = vi.mocked(previewSymposiumEmail)
const sendMock = vi.mocked(sendSymposiumEmailBatch)

const status = (overrides: Partial<SymposiumEmailStatus> = {}): SymposiumEmailStatus => ({
  teams: { total: 3, emailed: 0 },
  students: { total: 6, emailed: 0 },
  blocked: '',
  ...overrides
})

// What each card is told by the server, unless a test says otherwise.
let statuses: Record<SymposiumEmail, SymposiumEmailStatus>

const mountPage = async () => {
  const wrapper = mount(NonFinalistPage, {
    global: {
      stubs: {
        teleport: true,
        RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
      }
    }
  })
  await flushPromises()
  return wrapper
}
type Page = Awaited<ReturnType<typeof mountPage>>

// The Email Nonfinalist card and the Email Nonsubmission card below it.
const NONFINALISTS = '.symposium-email--nonfinalists'
const NONSUBMISSIONS = '.symposium-email--nonsubmissions'

const buttonIn = (wrapper: Page, card: string, label: RegExp) =>
  wrapper.findAll(`${card} button`).find((b) => label.test(b.text().trim()))!
const dialogButton = (wrapper: Page, label: RegExp) =>
  wrapper.findAll('[role="dialog"] button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  statusMock.mockReset()
  previewMock.mockReset()
  sendMock.mockReset()
  statuses = {
    nonfinalists: status(),
    nonsubmissions: status({ teams: { total: 1, emailed: 0 }, students: { total: 1, emailed: 0 } })
  }
  statusMock.mockImplementation(async (email) => statuses[email])
})

describe('Email Nonfinalist', () => {
  it('has the page title, then each section heading and where the date and link come from', async () => {
    const wrapper = await mountPage()
    expect(wrapper.find('.card-title').text()).toBe('Email Nonfinalist')
    expect(wrapper.findAll('.non-finalist__section-title').map((h) => h.text())).toEqual([
      'Email Nonfinalist',
      'Email Nonsubmission'
    ])
    // Each sentence on its own line, spaced like the lines around it.
    expect(wrapper.findAll(`${NONFINALISTS} .non-finalist__hint`).map((p) => p.text())).toEqual([
      "For teams that submitted but weren't selected as finalists.",
      'The Symposium date and registration link come from Email Details on Notify Finalists.'
    ])
    expect(wrapper.findAll(`${NONSUBMISSIONS} .non-finalist__hint`).map((p) => p.text())).toEqual([
      "For teams that didn't make a submission.",
      'The Symposium date and registration link come from Email Details on Notify Finalists.'
    ])
    expect(wrapper.find('.non-finalist__hint a').attributes('href')).toBe('/management/notify-finalists')
  })

  it('shows each email: not sent yet, how many students, and its buttons', async () => {
    const wrapper = await mountPage()
    for (const [card, count, label] of [
      [NONFINALISTS, 'Students: 0 of 6 emailed', 'Email Nonfinalists'],
      [NONSUBMISSIONS, 'Students: 0 of 1 emailed', 'Email Nonsubmissions']
    ] as const) {
      const line = wrapper.find(`${card} .symposium-email__status`)
      expect(line.text()).toBe('Emails are not sent to every group member')
      expect(line.classes()).toContain('symposium-email__status--warn')
      expect(wrapper.find(`${card} .symposium-email__counts`).text()).toBe(count)
      expect(buttonIn(wrapper, card, new RegExp(`^${label}$`)).attributes('disabled')).toBeUndefined()
      expect(buttonIn(wrapper, card, /^Preview Email$/).attributes('disabled')).toBeUndefined()
    }
    expect(statusMock.mock.calls.map(([email]) => email).sort()).toEqual(['nonfinalists', 'nonsubmissions'])
  })

  it('turns green and stops offering to send once every team is emailed', async () => {
    statuses.nonsubmissions = status({ teams: { total: 1, emailed: 1 }, students: { total: 1, emailed: 1 } })
    const wrapper = await mountPage()
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__status`).text()).toBe(
      'Emails are sent to every group member'
    )
    expect(buttonIn(wrapper, NONSUBMISSIONS, /^Email Nonsubmissions$/).attributes('disabled')).toBeDefined()
    expect(buttonIn(wrapper, NONFINALISTS, /^Email Nonfinalists$/).attributes('disabled')).toBeUndefined()
  })

  it('says why it cannot send, from the server', async () => {
    const reason = 'Set the Symposium date and registration link on Notify Finalists before sending.'
    statuses.nonfinalists = status({ blocked: reason })
    const wrapper = await mountPage()
    expect(wrapper.find(`${NONFINALISTS} .symposium-email__blocked`).text()).toBe(reason)
    expect(buttonIn(wrapper, NONFINALISTS, /^Email Nonfinalists$/).attributes('disabled')).toBeDefined()
  })

  it('still shows the status line and count while no team is due the email', async () => {
    statuses.nonsubmissions = status({ teams: { total: 0, emailed: 0 }, students: { total: 0, emailed: 0 } })
    const wrapper = await mountPage()
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__status`).text()).toBe(
      'Emails are not sent to every group member'
    )
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__counts`).text()).toBe('Students: 0 of 0 emailed')
    // Nobody to email, so nothing to send.
    expect(buttonIn(wrapper, NONSUBMISSIONS, /^Email Nonsubmissions$/).attributes('disabled')).toBeDefined()
  })

  it('says when the teams could not be loaded', async () => {
    statusMock.mockImplementation(async (email) => {
      if (email === 'nonsubmissions') throw new Error('Server down')
      return statuses[email]
    })
    const wrapper = await mountPage()
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__load-error`).text()).toContain(
      'Failed to load the teams.'
    )
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__actions`).exists()).toBe(false)
    expect(wrapper.find(`${NONFINALISTS} .symposium-email__actions`).exists()).toBe(true)
  })

  it("previews each card's own email", async () => {
    previewMock.mockImplementation(async (email) => ({
      subject:
        email === 'nonfinalists'
          ? 'Thank you for your submission – Invitation to the Symposium'
          : 'BIOTech Futures – No Submission Received',
      to: email === 'nonfinalists' ? 'BTF07' : 'BTF09',
      html: '<p>email</p>'
    }))
    const wrapper = await mountPage()
    await buttonIn(wrapper, NONSUBMISSIONS, /^Preview Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith('nonsubmissions')
    const dialog = wrapper.find('[aria-label="Email preview"]')
    expect(dialog.text()).toContain('BIOTech Futures – No Submission Received')
    expect(dialog.text()).toContain('As BTF09 would get it. Nothing has been sent.')
  })

  it('asks first, then emails batch after batch until done', async () => {
    sendMock
      .mockResolvedValueOnce({
        emailed: 8, failed: 0, cursor: 5, done: false,
        teams: { total: 3, emailed: 2 }, students: { total: 6, emailed: 4 }
      })
      .mockResolvedValueOnce({
        emailed: 4, failed: 0, cursor: 9, done: true,
        teams: { total: 3, emailed: 3 }, students: { total: 6, emailed: 6 }
      })
    const wrapper = await mountPage()
    await buttonIn(wrapper, NONFINALISTS, /^Email Nonfinalists$/).trigger('click')
    const confirm = wrapper.find('[aria-label="Send the email"]')
    expect(confirm.text()).toContain('Email non-finalist teams?')
    expect(confirm.text()).toContain("This emails every member of the 3 teams that haven't had this email yet.")
    expect(sendMock).not.toHaveBeenCalled()

    statuses.nonfinalists = status({ teams: { total: 3, emailed: 3 }, students: { total: 6, emailed: 6 } })
    await dialogButton(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(sendMock.mock.calls).toEqual([
      ['nonfinalists', null],
      ['nonfinalists', 5]
    ])
    expect(wrapper.find(`${NONFINALISTS} .symposium-email__banner--ok`).text()).toBe('Emailed 12 people.')
    expect(wrapper.find(`${NONFINALISTS} .symposium-email__counts`).text()).toBe('Students: 6 of 6 emailed')
  })

  it('says how many teams were not emailed in full, for a retry', async () => {
    sendMock.mockResolvedValue({
      emailed: 1, failed: 1, cursor: 5, done: true,
      teams: { total: 1, emailed: 0 }, students: { total: 1, emailed: 0 }
    })
    const wrapper = await mountPage()
    await buttonIn(wrapper, NONSUBMISSIONS, /^Email Nonsubmissions$/).trigger('click')
    const confirm = wrapper.find('[aria-label="Send the email"]')
    expect(confirm.text()).toContain('Email teams without a submission?')
    expect(confirm.text()).toContain("This emails every member of the 1 team that hasn't had this email yet.")
    await dialogButton(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(sendMock).toHaveBeenCalledWith('nonsubmissions', null)
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__banner--error`).text()).toBe(
      "Emailed 1 person. 1 team wasn't emailed in full; press Email Nonsubmissions again to retry."
    )
  })
})
