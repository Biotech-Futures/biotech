import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NonFinalistPage from '@/views/grading/NonFinalistPage.vue'
import {
  fetchSymposiumEmail,
  fetchTestEmailRecipients,
  previewSymposiumEmail,
  startSymposiumEmail,
  type SymposiumEmail,
  type SymposiumEmailStatus
} from '@/utils/gradingAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchTestEmailRecipients: vi.fn(async () => ({ recipients: [] })),
  sendTestEmail: vi.fn(),
  fetchSymposiumEmail: vi.fn(),
  previewSymposiumEmail: vi.fn(),
  startSymposiumEmail: vi.fn()
}))
const statusMock = vi.mocked(fetchSymposiumEmail)
const previewMock = vi.mocked(previewSymposiumEmail)
const sendMock = vi.mocked(startSymposiumEmail)

// A run's progress, as the server reports it.
const run = (over: Record<string, unknown> = {}) => ({
  due: 9,
  emailed: 0,
  failed: 0,
  error: '',
  missed: [] as string[],
  started_at: '2026-10-20T00:00:00Z',
  finished_at: null as string | null,
  ...over
})
const sendingRun = (over: Record<string, unknown> = {}) => ({ sending: true, run: run(over) })
const finishedRun = (over: Record<string, unknown> = {}) => ({
  sending: false,
  run: run({ finished_at: '2026-10-20T00:01:00Z', ...over })
})
const IDLE = { sending: false, run: null }

// People due the email and emailed, and the emails that makes ("times").
const people = (total: number, emailed: number, timesTotal = total, timesEmailed = emailed) => ({
  total,
  emailed,
  times: { total: timesTotal, emailed: timesEmailed }
})

const status = (overrides: Partial<SymposiumEmailStatus> = {}): SymposiumEmailStatus => ({
  teams: { total: 3, emailed: 0 },
  students: people(6, 0),
  mentors: people(3, 0, 4),
  supervisors: people(2, 0),
  blocked: '',
  ...IDLE,
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
    nonsubmissions: status({ teams: { total: 1, emailed: 0 }, students: people(1, 0) })
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
      "Students, mentors and supervisors in these groups each get the email. Anyone in multiple groups gets multiple emails, one for each group.",
      'The Symposium date and registration link come from Email Details on Notify Finalists.'
    ])
    expect(wrapper.findAll(`${NONSUBMISSIONS} .non-finalist__hint`).map((p) => p.text())).toEqual([
      "For teams that didn't make a submission.",
      "Students, mentors and supervisors in these groups each get the email. Anyone in multiple groups gets multiple emails, one for each group.",
      'The Symposium date and registration link come from Email Details on Notify Finalists.'
    ])
    expect(wrapper.find('.non-finalist__hint a').attributes('href')).toBe('/management/notify-finalists')
  })

  it('shows each email: not sent yet, how many students, mentors and supervisors, and its buttons', async () => {
    const wrapper = await mountPage()
    for (const [card, count, label] of [
      [
        NONFINALISTS,
        'Students: 0 of 6 emailed · Mentors: 0 of 3 emailed (Times 0 of 4) · Supervisors: 0 of 2 emailed (Times 0 of 2)',
        'Email Nonfinalists'
      ],
      [
        NONSUBMISSIONS,
        'Students: 0 of 1 emailed · Mentors: 0 of 3 emailed (Times 0 of 4) · Supervisors: 0 of 2 emailed (Times 0 of 2)',
        'Email Nonsubmissions'
      ]
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
    statuses.nonsubmissions = status({ teams: { total: 1, emailed: 1 }, students: people(1, 1) })
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
    statuses.nonsubmissions = status({ teams: { total: 0, emailed: 0 }, students: people(0, 0) })
    const wrapper = await mountPage()
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__status`).text()).toBe(
      'Emails are not sent to every group member'
    )
    expect(wrapper.find(`${NONSUBMISSIONS} .symposium-email__counts`).text()).toContain('Students: 0 of 0 emailed')
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

  it('asks first, then starts a run on the server and shows its progress until it is done', async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    try {
      sendMock.mockResolvedValueOnce(status({ ...sendingRun({ due: 12 }) }))
      const wrapper = await mountPage()
      await buttonIn(wrapper, NONFINALISTS, /^Email Nonfinalists$/).trigger('click')
      const confirm = wrapper.find('[aria-label="Send the email"]')
      expect(confirm.text()).toContain('Email non-finalist teams?')
      expect(confirm.text()).toContain("This emails every member of the 3 teams that haven't had this email yet.")
      expect(sendMock).not.toHaveBeenCalled()

      await dialogButton(wrapper, /^Send$/).trigger('click')
      await flushPromises()
      expect(sendMock).toHaveBeenCalledWith('nonfinalists')
      expect(wrapper.find('[aria-label="Send the email"]').exists()).toBe(false)
      expect(wrapper.find(`${NONFINALISTS} .symposium-email__progress`).text()).toBe('Emailed 0 of 12 people so far…')
      expect(buttonIn(wrapper, NONFINALISTS, /^Sending…$/).attributes('disabled')).toBeDefined()

      statuses.nonfinalists = status({ ...sendingRun({ due: 12, emailed: 8 }) })
      vi.advanceTimersByTime(2000)
      await flushPromises()
      expect(wrapper.find(`${NONFINALISTS} .symposium-email__progress`).text()).toBe('Emailed 8 of 12 people so far…')

      statuses.nonfinalists = status({
        ...finishedRun({ due: 12, emailed: 12 }),
        teams: { total: 3, emailed: 3 }, students: people(6, 6),
        mentors: people(3, 3, 4, 4), supervisors: people(2, 2)
      })
      vi.advanceTimersByTime(2000)
      await flushPromises()
      expect(wrapper.find(`${NONFINALISTS} .symposium-email__progress`).exists()).toBe(false)
      expect(wrapper.find(`${NONFINALISTS} .symposium-email__banner--ok`).text()).toBe('Emailed 12 people.')
      expect(wrapper.find(`${NONFINALISTS} .symposium-email__counts`).text()).toBe(
        'Students: 6 of 6 emailed · Mentors: 3 of 3 emailed (Times 4 of 4) · ' +
          'Supervisors: 2 of 2 emailed (Times 2 of 2)'
      )
    } finally {
      vi.useRealTimers()
    }
  })

  it('a page opened mid-run shows its progress; the other email can still go', async () => {
    statuses.nonfinalists = status({ ...sendingRun({ due: 12, emailed: 5 }) })
    const wrapper = await mountPage()
    expect(wrapper.find(`${NONFINALISTS} .symposium-email__progress`).text()).toBe('Emailed 5 of 12 people so far…')
    expect(buttonIn(wrapper, NONFINALISTS, /^Sending…$/).attributes('disabled')).toBeDefined()
    expect(buttonIn(wrapper, NONSUBMISSIONS, /^Email Nonsubmissions$/).attributes('disabled')).toBeUndefined()
  })

  it("lists, under the button, who the last run couldn't reach", async () => {
    statuses.nonfinalists = status({ ...finishedRun({ failed: 1, missed: ['(BTF03) Amy Chen'] }) })
    const wrapper = await mountPage()
    const missed = wrapper.find(`${NONFINALISTS} [data-testid="missed"]`)
    expect(missed.text()).toContain("Couldn't be emailed:")
    expect(missed.findAll('li').map((li) => li.text())).toEqual(['(BTF03) Amy Chen'])
    expect(wrapper.find(`${NONSUBMISSIONS} [data-testid="missed"]`).exists()).toBe(false)
  })

  it('says how many teams were not emailed in full, for a retry', async () => {
    sendMock.mockResolvedValueOnce(status({ ...finishedRun({ due: 3, emailed: 1, failed: 1 }) }))
    const wrapper = await mountPage()
    await buttonIn(wrapper, NONFINALISTS, /^Email Nonfinalists$/).trigger('click')
    await dialogButton(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find(`${NONFINALISTS} .symposium-email__banner--error`).text()).toBe(
      "Emailed 1 person. 1 team wasn't emailed in full; press Email Nonfinalists again to retry."
    )
  })

  it('previews the email as the person picked in Send Test Email gets it', async () => {
    vi.mocked(fetchTestEmailRecipients).mockImplementation(async (kind) => ({
      recipients: kind === 'nonsubmissions'
        ? [{ value: '9:1', label: '(BTF09) Amy Chen' }, { value: '12:4', label: '(BTF12) Ben Lee' }]
        : []
    }))
    previewMock.mockResolvedValue({ subject: 'No Submission', to: 'BTF12', html: '<p>email</p>' })
    const wrapper = await mountPage()
    await wrapper.find(`${NONSUBMISSIONS} .test-email__select`).setValue('12:4')
    await buttonIn(wrapper, NONSUBMISSIONS, /^Preview Email$/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith('nonsubmissions', '12:4')
    expect(wrapper.find('[aria-label="Email preview"]').text()).toContain('As BTF12 would get it.')
    vi.mocked(fetchTestEmailRecipients).mockImplementation(async () => ({ recipients: [] }))
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
    // Nobody to pick from: the first team due.
    expect(previewMock).toHaveBeenCalledWith('nonsubmissions', '')
    const dialog = wrapper.find('[aria-label="Email preview"]')
    expect(dialog.text()).toContain('BIOTech Futures – No Submission Received')
    expect(dialog.text()).toContain('As BTF09 would get it. Nothing has been sent.')
  })

})
