import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import NotifyFinalistsPage from '@/views/management/NotifyFinalistsPage.vue'
import { fetchFinalists } from '@/utils/gradingAPI'
import { defineComponent, h } from 'vue'
import {
  fetchFinalistEmailDetails,
  fetchOutcomeAnnouncement,
  fetchTestEmailRecipients,
  notifyFinalists,
  postOutcomeAnnouncement,
  previewFinalistEmail,
  restoreOutcomeAnnouncement,
  updateFinalistEmailDetails,
  updateOutcomeAnnouncement
} from '@/utils/managementAPI'

vi.mock('@/utils/gradingAPI', () => ({
  fetchFinalists: vi.fn()
}))
vi.mock('@/utils/managementAPI', () => ({
  fetchTestEmailRecipients: vi.fn(async () => ({ recipients: [] })),
  sendTestEmail: vi.fn(),
  notifyFinalists: vi.fn(),
  fetchFinalistEmailDetails: vi.fn(),
  updateFinalistEmailDetails: vi.fn(),
  previewFinalistEmail: vi.fn(),
  fetchOutcomeAnnouncement: vi.fn(),
  updateOutcomeAnnouncement: vi.fn(),
  postOutcomeAnnouncement: vi.fn(),
  restoreOutcomeAnnouncement: vi.fn()
}))
// The rich editor as a plain box, typed into like one.
const RichEditorStub = defineComponent({
  props: { modelValue: { type: String, default: '' } },
  emits: ['update:modelValue'],
  setup: (props, { emit }) => () =>
    h('textarea', {
      class: 'rich-editor-stub',
      value: props.modelValue,
      onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLTextAreaElement).value)
    })
})
const announcementMock = vi.mocked(fetchOutcomeAnnouncement)
const saveAnnouncementMock = vi.mocked(updateOutcomeAnnouncement)
const postAnnouncementMock = vi.mocked(postOutcomeAnnouncement)
const restoreAnnouncementMock = vi.mocked(restoreOutcomeAnnouncement)
const ANNOUNCEMENT = {
  title: 'Congratulations – You’re a BIOTech Futures Finalist!',
  body: '<p>Dear members of our finalist teams,</p><ul><li>Confirm by Friday.</li></ul>',
  edited: false,
  recipients: 2,
  noun: 'finalist group',
  posted_at: null as string | null,
  posted_by: null as string | null
}
const listMock = vi.mocked(fetchFinalists)
const notifyMock = vi.mocked(notifyFinalists)
const detailsMock = vi.mocked(fetchFinalistEmailDetails)
const saveMock = vi.mocked(updateFinalistEmailDetails)
const previewMock = vi.mocked(previewFinalistEmail)

// A run's progress, as the server reports it.
const run = (over: Record<string, unknown> = {}) => ({
  due: 9,
  emailed: 0,
  failed: 0,
  error: '',
  missed: [] as { who: string; reason: string }[],
  started_at: '2026-10-20T00:00:00Z',
  finished_at: null as string | null,
  ...over
})
const sendingRun = (over: Record<string, unknown> = {}) => ({ sending: true, queued: 0, ahead: [], run: run(over) })
const finishedRun = (over: Record<string, unknown> = {}) => ({
  sending: false,
  queued: 0,
  ahead: [] as string[],
  run: run({ finished_at: '2026-10-20T00:01:00Z', ...over })
})

// Every detail set: the email can go out.
const details = (over: Record<string, unknown> = {}) => ({
  symposium_date: '2026-10-23',
  confirm_by: '2026-10-04',
  slides_due: '2026-10-16',
  registration_url: 'https://events.example.com/s',
  complete: true,
  today: '2026-09-27',
  dates_in_past: [] as string[],
  submissions_open: '',
  sending: false,
  queued: 0,
  ahead: [] as string[],
  run: null,
  counts: COUNTS,
  // One team never tried, and two people on one team a send missed.
  waiting: { new: { teams: 1, people: 3, groups: ['BTF-1'] }, missed: { teams: 1, people: 2, groups: ['BTF-2'] } },
  ...over
})

const finalist = (group_id: number, over: Record<string, unknown> = {}) => ({
  group_id,
  group_name: `BTF-${group_id}`,
  flagged_at: '2026-09-01T00:00:00Z',
  flagged_by: 'Ada Admin',
  notified: false,
  notified_at: null,
  notified_by: null,
  ...over
})

// Everyone the finalist email goes to, by role: people emailed, and the
// emails that makes ("times"), as the server counts them.
const COUNTS = {
  groups: { total: 2, emailed: 1 },
  students: { total: 6, emailed: 3, times: { total: 6, emailed: 3 } },
  mentors: { total: 1, emailed: 1, times: { total: 2, emailed: 1 } },
  supervisors: { total: 2, emailed: 1, times: { total: 3, emailed: 1 } }
}

const mountPage = async () => {
  const wrapper = mount(NotifyFinalistsPage, { global: { stubs: { teleport: true } } })
  await flushPromises()
  return wrapper
}

const buttonNamed = (wrapper: Awaited<ReturnType<typeof mountPage>>, label: RegExp) =>
  wrapper.findAll('button').find((b) => label.test(b.text().trim()))!

beforeEach(() => {
  announcementMock.mockReset().mockResolvedValue({ ...ANNOUNCEMENT })
  saveAnnouncementMock.mockReset()
  postAnnouncementMock.mockReset()
  restoreAnnouncementMock.mockReset()
  listMock.mockReset()
  notifyMock.mockReset()
  detailsMock.mockReset().mockResolvedValue(details())
  saveMock.mockReset()
  previewMock.mockReset()
  listMock.mockResolvedValue({
    finalists: [
      finalist(1),
      finalist(2, {
        notified: true,
        notified_at: '2026-09-10T00:00:00Z',
        notified_by: 'Ada Admin'
      })
    ] })
})

describe('the finalist roster', () => {
  it('lists teams with their notified stamp, dash when never emailed', async () => {
    const wrapper = await mountPage()
    const rows = wrapper.findAll('tbody tr')
    expect(rows[0]!.text()).toContain('BTF-1')
    expect(rows[0]!.text()).toContain('—')
    expect(rows[1]!.text()).toContain(
      `${new Date('2026-09-10T00:00:00Z').toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: '2-digit' })} ${new Date('2026-09-10T00:00:00Z').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hourCycle: 'h23' })}`
    )
  })

  it('an already-notified team cannot be ticked again', async () => {
    const wrapper = await mountPage()
    const boxes = wrapper.findAll('tbody input[type="checkbox"]')
    expect(boxes[0]!.attributes('disabled')).toBeUndefined()
    expect(boxes[1]!.attributes('disabled')).toBeDefined()
  })

  it('surfaces the most recent send above the actions', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Last Emailed at')
    expect(wrapper.text()).toContain('by Ada Admin')
  })

  it('says where undeliverable emails come back to, above the last send', async () => {
    detailsMock.mockResolvedValue(details({ sent_from: 'info@biotechfutures.org' }))
    const wrapper = await mountPage()
    const note = wrapper.find('.notify-finalists__delivery-note')
    expect(note.text()).toBe(
      "Emails can take a few minutes to arrive. Any that can't be delivered, such as a " +
        "mistyped address or one a school's mail server refuses, come back to info@biotechfutures.org " +
        'and the rest of the group still gets it.'
    )
    expect(note.element.nextElementSibling?.textContent).toContain('Last Emailed at')
  })

  it('names the newly added teams not emailed yet, above the delivery note', async () => {
    detailsMock.mockResolvedValue(details({
      sent_from: 'info@biotechfutures.org',
      waiting: { new: { teams: 2, people: 5, groups: ['BTF-3', 'BTF-10'] }, missed: { teams: 0, people: 0, groups: [] } }
    }))
    const wrapper = await mountPage()
    const names = wrapper.find('.notify-finalists__newly-added')
    expect(names.text()).toBe('Newly added, not emailed yet: BTF-3, BTF-10')
    expect(names.element.nextElementSibling?.classList).toContain('notify-finalists__delivery-note')
  })

  it('names no teams when none are newly added', async () => {
    detailsMock.mockResolvedValue(
      details({ waiting: { new: { teams: 0, people: 0, groups: [] }, missed: { teams: 0, people: 0, groups: [] } } })
    )
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__newly-added').exists()).toBe(false)
  })

  it('says so when no finalists exist yet', async () => {
    listMock.mockResolvedValue({ finalists: [] })
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__empty').text()).toBe('No finalists yet.')
    expect(wrapper.find('.notify-finalists__status').exists()).toBe(false)
  })

  it('warns while a team is still to be emailed', async () => {
    const wrapper = await mountPage()
    const status = wrapper.find('.notify-finalists__status')
    expect(status.text()).toBe('Emails are not sent to every group member')
    expect(status.classes()).toContain('notify-finalists__status--warn')
    // People, and for mentors and supervisors the emails that makes: the
    // mentor is on both teams, one of them notified.
    expect(wrapper.find('.notify-finalists__counts').text()).toBe(
      'Groups: 1 of 2 emailed Students: 3 of 6 emailed · Mentors: 1 of 1 emailed (Times 1 of 2) · ' +
        'Supervisors: 1 of 2 emailed (Times 1 of 3)'
    )
  })

  it('says every member was emailed once all teams are notified', async () => {
    listMock.mockResolvedValue({
      finalists: [finalist(1, { notified: true, notified_at: '2026-09-10T00:00:00Z' })] })
    const wrapper = await mountPage()
    const status = wrapper.find('.notify-finalists__status')
    expect(status.text()).toBe('Emails are sent to every group member')
    expect(status.classes()).toContain('notify-finalists__status--ok')
  })

  it('offers a retry when the roster fails to load', async () => {
    listMock.mockRejectedValueOnce(new Error('backend down'))
    const wrapper = await mountPage()
    expect(wrapper.text()).toContain('Failed to load.')
    await buttonNamed(wrapper, /Try again/).trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('BTF-1')
  })
})

describe('sending', () => {
  it('sending to all confirms first, then reports how many went out', async () => {
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 3, emailed: 3 }), pending: 0 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    const dialog = wrapper.find('[role="dialog"]')
    expect(dialog.text()).toContain('every finalist team that has not been notified yet')

    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    // Every team not yet notified, which the server picks.
    expect(notifyMock).toHaveBeenCalledWith(undefined)
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe('Emailed 3 people.')
    expect(listMock).toHaveBeenCalledTimes(2) // roster refreshes after a send
  })

  it('says emails can take a while, and where undeliverable ones come back to', async () => {
    detailsMock.mockResolvedValue(details({ sent_from: 'info@biotechfutures.org' }))
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 3, emailed: 3 }), pending: 0 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe(
      "Emailed 3 people. Emails can take a few minutes to arrive. Any that can't be delivered, such as a " +
        "mistyped address or one a school's mail server refuses, come back to info@biotechfutures.org " +
        'and the rest of the group still gets it.'
    )
  })

  it('says where undeliverable ones come back to after a run that missed some', async () => {
    detailsMock.mockResolvedValue(details({ sent_from: 'info@biotechfutures.org' }))
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 3, emailed: 2, failed: 1 }), pending: 1 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--error').text()).toBe(
      "Emailed 2 people. 1 team wasn't emailed in full; press Resend Email To Missed Individuals to email only " +
        "those it missed. Emails can take a few minutes to arrive. Any that can't be delivered, such as a " +
        "mistyped address or one a school's mail server refuses, come back to info@biotechfutures.org " +
        'and the rest of the group still gets it.'
    )
  })

  it('says where undeliverable ones come back to even when nobody was left to email', async () => {
    detailsMock.mockResolvedValue(details({ sent_from: 'info@biotechfutures.org' }))
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 0, emailed: 0 }), pending: 0 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toContain(
      'every finalist team is already notified or has no members to email. Emails can take a few minutes to arrive.'
    )
  })

  it('explains, with a plain dash, a send that had nobody left to email', async () => {
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 0, emailed: 0 }), pending: 0 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe(
      'No emails sent - every finalist team is already notified or has no members to email.'
    )
  })

  it("closes the dialog on Send, then shows the run's progress until it is done", async () => {
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    try {
      notifyMock.mockResolvedValueOnce({ ...sendingRun({ due: 28 }), pending: 7 })
      const wrapper = await mountPage()
      await buttonNamed(wrapper, /Email All/).trigger('click')
      await buttonNamed(wrapper, /^Send$/).trigger('click')
      await flushPromises()
      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
      expect(wrapper.find('.notify-finalists__progress').text()).toBe('Emailed 0 of 28 people so far…')
      expect(buttonNamed(wrapper, /Email Selected/).attributes('disabled')).toBeDefined()

      detailsMock.mockResolvedValue(details({ ...sendingRun({ due: 28, emailed: 20 }) }))
      vi.advanceTimersByTime(2000)
      await flushPromises()
      expect(wrapper.find('.notify-finalists__progress').text()).toBe('Emailed 20 of 28 people so far…')

      detailsMock.mockResolvedValue(details({ ...finishedRun({ due: 28, emailed: 28 }) }))
      listMock.mockClear()
      vi.advanceTimersByTime(2000)
      await flushPromises()
      expect(wrapper.find('.notify-finalists__progress').exists()).toBe(false)
      expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe('Emailed 28 people.')
      // The roster is reloaded, with the teams the run reached.
      expect(listMock).toHaveBeenCalledOnce()
    } finally {
      vi.useRealTimers()
    }
  })

  it("lists, under the buttons, who the last run couldn't reach", async () => {
    detailsMock.mockResolvedValue(details({ ...finishedRun({ due: 4, emailed: 2, failed: 1,
      missed: [{ who: '(BTF01) Amy Chen', reason: 'mail server busy' }, { who: '(BTF01) Mo Mentor', reason: '' }] }) }))
    const wrapper = await mountPage()
    const missed = wrapper.find('[data-testid="missed"]')
    expect(missed.text()).toContain("Couldn't be emailed:")
    // Each with why, when the run kept it.
    expect(missed.findAll('li').map((li) => li.text())).toEqual(['(BTF01) Amy Chen · mail server busy', '(BTF01) Mo Mentor'])
  })

  it('a page opened mid-run shows its progress, and more sends can be queued', async () => {
    detailsMock.mockResolvedValue(details({ ...sendingRun({ due: 28, emailed: 12 }) }))
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__progress').text()).toBe('Emailed 12 of 28 people so far…')
    expect(buttonNamed(wrapper, /^Email All$/).attributes('disabled')).toBeUndefined()
  })

  it('a send pressed while another is going says it is queued', async () => {
    notifyMock.mockResolvedValueOnce({ ...finishedRun(), queued: 1, ahead: ['Results (To groups)'], pending: 2 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Email All$/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe(
      'Queued behind the Results (To groups) email. It starts a few seconds after that has finished.'
    )
    expect(wrapper.find('.notify-finalists__queued').text()).toBe(
      'Queued behind the Results (To groups) email, starts once that has finished.'
    )
  })

  it('the selected-teams button stays off until something is ticked', async () => {
    const wrapper = await mountPage()
    const selectedButton = buttonNamed(wrapper, /Email Selected/)
    expect(selectedButton.attributes('disabled')).toBeDefined()

    await wrapper.find('tbody input[type="checkbox"]').trigger('change')
    expect(selectedButton.attributes('disabled')).toBeUndefined()
  })

  it('sending to selected teams names the count and targets only them', async () => {
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 3, emailed: 3 }), pending: 0 })
    const wrapper = await mountPage()
    await wrapper.find('tbody input[type="checkbox"]').trigger('change')
    await buttonNamed(wrapper, /Email Selected/).trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain('the 1 selected team.')

    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(notifyMock).toHaveBeenCalledWith([1])
  })

  it('has Newly Added and Missed Individuals between All and Selected', async () => {
    const wrapper = await mountPage()
    // The send buttons, not the details' Save, Preview and Test.
    const labels = wrapper
      .findAll('.notify-finalists__email-actions button')
      .map((b) => b.text())
      .filter((label) => /^(Email|Resend)/.test(label))
    expect(labels).toEqual([
      'Email All',
      'Email Newly Added',
      'Resend Email To Missed Individuals',
      'Email Selected'
    ])
  })

  it('sending to newly added groups names how many and asks for only them', async () => {
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 3, emailed: 3 }), pending: 1 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email Newly Added/).trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain(
      'This will send the notification email to the 1 finalist team not emailed yet.'
    )
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(notifyMock).toHaveBeenCalledWith(undefined, 'new')
  })

  it('retrying names who was missed and asks for only them', async () => {
    notifyMock.mockResolvedValueOnce({ ...finishedRun({ due: 2, emailed: 2 }), pending: 1 })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Resend Email To Missed Individuals/).trigger('click')
    expect(wrapper.find('[role="dialog"]').text()).toContain(
      'This will email only the 2 people earlier sends missed, on 1 team.'
    )
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(notifyMock).toHaveBeenCalledWith(undefined, 'missed')
  })

  it('Newly Added and Missed Individuals are off when they have nobody to email', async () => {
    detailsMock.mockResolvedValue(
      details({ waiting: { new: { teams: 0, people: 0, groups: [] }, missed: { teams: 0, people: 0, groups: [] } } })
    )
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, /Email Newly Added/).attributes('disabled')).toBeDefined()
    expect(buttonNamed(wrapper, /Resend Email To Missed Individuals/).attributes('disabled')).toBeDefined()
    expect(buttonNamed(wrapper, /Email All/).attributes('disabled')).toBeUndefined()
  })

  it('cancelling the dialog sends nothing', async () => {
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    await buttonNamed(wrapper, /^Cancel$/).trigger('click')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(notifyMock).not.toHaveBeenCalled()
  })

  it('a refused send is reported and the dialog closes', async () => {
    notifyMock.mockRejectedValueOnce(new Error('email disabled'))
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /Email All/).trigger('click')
    await buttonNamed(wrapper, /^Send$/).trigger('click')
    await flushPromises()
    expect(wrapper.find('.notify-finalists__banner--error').text()).toContain('email disabled')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
  })
})

describe('the announcement', () => {
  it('puts Preview, Edit and Post Announcement under Last Emailed', async () => {
    const wrapper = await mountPage()
    const row = wrapper.find('.outcome-announcement__actions')
    expect(row.findAll('button').map((b) => b.text())).toEqual([
      'Preview Announcement',
      'Edit Announcement',
      'Post Announcement'
    ])
    expect(announcementMock).toHaveBeenCalledWith('finalists')
    const block = wrapper.find('.outcome-announcement').element
    expect(block.previousElementSibling?.textContent).toContain('Last Emailed at')
  })

  it('previews it as finalists will see it, posting nothing', async () => {
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Preview Announcement$/).trigger('click')
    const dialog = wrapper.find('[aria-label="Announcement preview"]')
    expect(dialog.text()).toContain('Congratulations – You’re a BIOTech Futures Finalist!')
    expect(dialog.text()).toContain('As the 2 finalist groups emailed so far will see it in the app.')
    expect(dialog.find('.outcome-announcement__body li').text()).toBe('Confirm by Friday.')
    expect(postAnnouncementMock).not.toHaveBeenCalled()
  })

  it('edits the title and text, starting from the current wording', async () => {
    saveAnnouncementMock.mockResolvedValueOnce({ ...ANNOUNCEMENT, title: 'Finalists!', edited: true })
    const wrapper = mount(NotifyFinalistsPage, {
      global: { stubs: { teleport: true, RichEditor: RichEditorStub } }
    })
    await flushPromises()
    await buttonNamed(wrapper, /^Edit Announcement$/).trigger('click')
    await flushPromises()
    const dialog = wrapper.find('[aria-label="Edit announcement"]')
    expect((dialog.find('input').element as HTMLInputElement).value).toBe(ANNOUNCEMENT.title)
    const editor = () => wrapper.find('[aria-label="Edit announcement"]')
    await editor().find('input').setValue('Finalists!')
    await editor().find('.rich-editor-stub').setValue('<p>Well done.</p>')
    await editor().findAll('button').find((b) => b.text() === 'Save changes')!.trigger('click')
    await flushPromises()
    expect(saveAnnouncementMock).toHaveBeenCalledWith('finalists', { title: 'Finalists!', body: '<p>Well done.</p>' })
    expect(wrapper.find('[aria-label="Edit announcement"]').exists()).toBe(false)
  })

  it('has Save changes and Restore default as on System Emails', async () => {
    announcementMock.mockResolvedValue({ ...ANNOUNCEMENT, title: 'Finalists!', edited: true })
    restoreAnnouncementMock.mockResolvedValueOnce({ ...ANNOUNCEMENT })
    const wrapper = mount(NotifyFinalistsPage, {
      global: { stubs: { teleport: true, RichEditor: RichEditorStub } }
    })
    await flushPromises()
    await buttonNamed(wrapper, /^Edit Announcement$/).trigger('click')
    const editor = () => wrapper.find('[aria-label="Edit announcement"]')
    const named = (label: string) => editor().findAll('button').find((b) => b.text() === label)!
    // Nothing changed yet, so nothing to save.
    expect(named('Save changes').attributes('disabled')).toBeDefined()
    await named('Restore default').trigger('click')
    await flushPromises()
    expect(restoreAnnouncementMock).toHaveBeenCalledWith('finalists')
    // The email's wording, back in the editor.
    expect((editor().find('input').element as HTMLInputElement).value).toBe(ANNOUNCEMENT.title)
    expect(named('Restore default').attributes('disabled')).toBeDefined()
  })

  it('asks first, then posts it and says when', async () => {
    postAnnouncementMock.mockResolvedValueOnce({
      ...ANNOUNCEMENT, posted_at: '2026-10-04T01:00:00Z', posted_by: 'Ada Admin'
    })
    const wrapper = await mountPage()
    await buttonNamed(wrapper, /^Post Announcement$/).trigger('click')
    expect(wrapper.find('[aria-label="Post announcement"]').text()).toContain(
      'This posts it in the app to the 2 finalist groups emailed so far.'
    )
    expect(postAnnouncementMock).not.toHaveBeenCalled()
    await buttonNamed(wrapper, /^Post$/).trigger('click')
    await flushPromises()
    expect(postAnnouncementMock).toHaveBeenCalledWith('finalists')
    expect(wrapper.text()).toContain('Announcement posted to 2 finalist groups.')
    expect(wrapper.find('[data-testid="announcement-posted"]').text()).toContain('by Ada Admin')
  })

  it('cannot be posted before any finalist group is emailed', async () => {
    announcementMock.mockResolvedValue({ ...ANNOUNCEMENT, recipients: 0 })
    const wrapper = await mountPage()
    expect(buttonNamed(wrapper, /^Post Announcement$/).attributes('disabled')).toBeDefined()
  })
})

describe('the email details', () => {
  it("the date pickers start at the server's today", async () => {
    const wrapper = await mountPage()
    for (const input of wrapper.findAll('input[type="date"]')) {
      expect(input.attributes('min')).toBe('2026-09-27')
    }
  })

  it('a date before today is only pointed out, above Save, once Save is pressed', async () => {
    saveMock.mockResolvedValueOnce(details())
    const wrapper = await mountPage()
    const [symposium] = wrapper.findAll('input[type="date"]')
    await symposium!.setValue('2026-09-26')
    // Nothing flagged while typing, and Save stays available.
    expect(symposium!.classes()).not.toContain('is-invalid')
    expect(wrapper.find('.notify-finalists__field-error').exists()).toBe(false)
    const save = buttonNamed(wrapper, /^Save$/)
    expect(save.attributes('disabled')).toBeUndefined()

    await save.trigger('click')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(symposium!.classes()).toContain('is-invalid')
    const message = wrapper.find('.notify-finalists__field-error')
    expect(message.text()).toBe("Symposium Date can't be before today.")
    // It sits just above the Save button.
    expect(message.element.nextElementSibling?.contains(save.element)).toBe(true)

    await symposium!.setValue('2026-09-27') // today is fine
    expect(wrapper.find('.notify-finalists__field-error').exists()).toBe(false)
    await save.trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledOnce()
  })

  it('a saved date that has since passed is flagged and blocks sending', async () => {
    detailsMock.mockResolvedValue(
      details({ confirm_by: '2025-10-05', dates_in_past: ['confirm_by'] })
    )
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__field-error').exists()).toBe(false)
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(
      'Some email dates are before today. Update and save them before sending.'
    )
    expect(buttonNamed(wrapper, /Email All/).attributes('disabled')).toBeDefined()

    // Saving other details names the passed dates, all of them, and saves nothing.
    await wrapper.findAll('input[type="date"]')[2]!.setValue('2026-09-01')
    await wrapper.find('input[type="url"]').setValue('https://events.example.com/new')
    await buttonNamed(wrapper, /^Save$/).trigger('click')
    await flushPromises()
    expect(saveMock).not.toHaveBeenCalled()
    expect(wrapper.find('.notify-finalists__field-error').text()).toBe(
      "Confirm Attendance By and Slides Due can't be before today."
    )
  })

  it('shows the saved details, and no leftover under-construction banner', async () => {
    const wrapper = await mountPage()
    expect(wrapper.text()).not.toContain('still being built')
    expect((wrapper.find('input[type="date"]').element as HTMLInputElement).value).toBe(
      '2026-10-23'
    )
    expect((wrapper.find('input[type="url"]').element as HTMLInputElement).value).toBe(
      'https://events.example.com/s'
    )
  })

  it('Save can always be pressed, and saves blanks as none', async () => {
    saveMock.mockResolvedValueOnce(details({ slides_due: null, complete: false }))
    const wrapper = await mountPage()
    const save = buttonNamed(wrapper, /^Save$/)
    expect(save.attributes('disabled')).toBeUndefined()

    await wrapper.findAll('input[type="date"]')[2]!.setValue('')
    await save.trigger('click')
    await flushPromises()
    expect(saveMock).toHaveBeenCalledWith({
      symposium_date: '2026-10-23',
      confirm_by: '2026-10-04',
      slides_due: null,
      registration_url: 'https://events.example.com/s'
    })
    expect(wrapper.find('.notify-finalists__banner--ok').text()).toBe('Email details saved.')
  })

  it('Send stays off, saying why, while a detail is missing', async () => {
    detailsMock.mockResolvedValue(details({ slides_due: null, complete: false }))
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(
      'Fill in and save every email detail above before sending.'
    )
    expect(buttonNamed(wrapper, /Email All/).attributes('disabled')).toBeDefined()
  })

  it('Send stays off, saying until when, while submissions are still open', async () => {
    const reason =
      "A team's extension is open until Friday, 17 October 2026, 11:59 PM (Sydney time). Send this once every extension has ended."
    detailsMock.mockResolvedValue(details({ submissions_open: reason }))
    const wrapper = await mountPage()
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(reason)
    expect(buttonNamed(wrapper, /Email All/).attributes('disabled')).toBeDefined()
  })

  it('Send stays off until an edit is saved', async () => {
    const wrapper = await mountPage()
    await wrapper.find('input[type="date"]').setValue('2026-10-30')
    expect(wrapper.find('.notify-finalists__blocked').text()).toBe(
      'Save the email details before sending.'
    )
    expect(buttonNamed(wrapper, /Email All/).attributes('disabled')).toBeDefined()
  })

  it('Preview shows the email as the person picked in Send Test Email gets it', async () => {
    vi.mocked(fetchTestEmailRecipients).mockResolvedValueOnce({
      recipients: [{ value: '1:1', label: '(BTF-1) Amy Chen' }, { value: '2:4', label: '(BTF-2) Ben Lee' }]
    })
    previewMock.mockResolvedValueOnce({ subject: 'Congratulations', group_name: 'BTF-2', html: '<p>email</p>' })
    const wrapper = await mountPage()
    await wrapper.find('.test-email__select').setValue('2:4')
    await buttonNamed(wrapper, /Preview Email/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith(expect.any(Object), '2:4')
    expect(wrapper.find('[aria-label="Email preview"]').text()).toContain('As the members of BTF-2 would get it')
  })

  it('Preview shows the email for the details as typed, sending nothing', async () => {
    previewMock.mockResolvedValueOnce({
      subject: 'Congratulations',
      group_name: 'BTF-1',
      html: '<p>Dear members of BTF-1</p>'
    })
    const wrapper = await mountPage()
    await wrapper.find('input[type="date"]').setValue('2026-10-30')
    await buttonNamed(wrapper, /Preview Email/).trigger('click')
    await flushPromises()
    expect(previewMock).toHaveBeenCalledWith(
      expect.objectContaining({ symposium_date: '2026-10-30' }),
      ''
    )
    const dialog = wrapper.find('[aria-label="Email preview"]')
    expect(dialog.text()).toContain('As the members of BTF-1 would get it')
    expect(dialog.find('iframe').attributes('srcdoc')).toContain('Dear members of BTF-1')
    expect(notifyMock).not.toHaveBeenCalled()

    await buttonNamed(wrapper, /^Close$/).trigger('click')
    expect(wrapper.find('[aria-label="Email preview"]').exists()).toBe(false)
  })
})
