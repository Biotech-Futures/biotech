import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import AppSelect from '@/components/AppSelect.vue'
import { TicketSessionError } from '@/utils/ticketTransport'
import type { TicketDetail } from '@/utils/ticketAgentSchema'

import {
  api,
  deferred,
  messageWith,
  openPanel,
  pickChoice,
  refusal,
  resetPanelTests,
  serverError,
  ticketGone,
  ticketWith,
  type Panel
} from './ticketDetailFixtures'

// The reply box and the internal-note box, driven through the real panel.
// Ported from the "two attachment pickers and two message boxes" and "when a
// message is refused" blocks of TicketDetailPanel.test.tsx, plus what those
// boxes never had a test for: the reply's status on the one request (C-19),
// the reset after a send, the double-submit guard, one pending flag per box,
// and the file input emptied after a send.
vi.mock('@/utils/ticketAgentAPI', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/ticketAgentAPI')>()),
  fetchTicketDetail: vi.fn(),
  fetchAssignees: vi.fn(),
  fetchTicketHistory: vi.fn(),
  updateTicket: vi.fn(),
  sendTicketMessage: vi.fn(),
  downloadTicketAttachment: vi.fn()
}))

beforeEach(resetPanelTests)
afterEach(resetPanelTests)

const REPLY = 'textarea[aria-label="Reply to the requester"]'
const NOTE = 'textarea[aria-label="Internal note, not visible to the requester"]'
const TYPED = 'Here is the form you asked for.'
// The platform's AppSelect since the 2026-10-22 client meeting (C-29).
const STATUS = '.reply-box .reply-box__select'

const value = ({ page }: Panel, selector: string) =>
  (page.get(selector).element as HTMLTextAreaElement | HTMLInputElement).value

async function sendFrom(panel: Panel, box: 'reply' | 'note', text = TYPED) {
  await panel.page.get(box === 'reply' ? REPLY : NOTE).setValue(text)
  await panel.page.get(box === 'reply' ? '.reply-box' : '.note-box').trigger('submit')
  await flushPromises()
}

const alertIn = ({ page }: Panel, box: string) => page.get(`${box} [role="alert"]`).text()

/**
 * The name a screen reader computes, in the order the accname spec resolves
 * it. Placeholder is deliberately excluded: it is the last-resort source, and
 * counting it would let the very gap this guards against pass.
 */
function accessibleName(el: Element): string {
  const labelledBy = el.getAttribute('aria-labelledby')
  if (labelledBy) {
    return labelledBy
      .split(/\s+/)
      .map((id) => document.getElementById(id)?.textContent?.trim() ?? '')
      .join(' ')
      .trim()
  }
  const label = el.getAttribute('aria-label')
  if (label) return label.trim()
  const labels = (el as HTMLInputElement).labels
  if (labels && labels.length) {
    return Array.from(labels)
      .map((node) => node.textContent?.trim() ?? '')
      .join(' ')
      .trim()
  }
  return ''
}

describe('the two attachment pickers and the two message boxes', () => {
  it('gives the reply and the internal note different names', async () => {
    const { page } = await openPanel(ticketWith())

    const names = page.findAll('input[type="file"]:not([aria-hidden="true"]), textarea').map((node) => accessibleName(node.element))

    // Four controls, four names, none of them blank. A blank name is what a
    // bare file input computes to.
    expect(names).toHaveLength(4)
    expect(names.filter((name) => name === '')).toEqual([])
    expect(new Set(names).size).toBe(4)
  })

  it('says which box the requester will read and which they will not', async () => {
    // Written out rather than read from the components, so that renaming a
    // control has to be a deliberate edit here too.
    const { page } = await openPanel(ticketWith())

    const names = page.findAll('input[type="file"]:not([aria-hidden="true"]), textarea').map((node) => accessibleName(node.element))

    expect(names).toEqual([
      'Reply to the requester',
      'Attach files to this reply',
      'Internal note, not visible to the requester',
      'Attach files to this internal note'
    ])
  })

  it('asks what the reply leaves the ticket as, starting on Pending user', async () => {
    // The client's words at the 8 October meeting (C-19): "it would default
    // to pending user, but then it would allow the support agent to change it
    // to in progress or resolved." Written out, as the status words are the
    // top control's.
    const { page } = await openPanel(ticketWith())

    const field = page.get(`${STATUS} input[role="combobox"]`)
    expect(accessibleName(field.element)).toBe('Status after sending')
    expect(appSelectText(page, STATUS)).toBe('Pending user')
    expect(page.get('.reply-box').findComponent(AppSelect).props('options')).toEqual([
      { value: 'in_progress', label: 'In progress' },
      { value: 'pending_user', label: 'Pending user' },
      { value: 'resolved', label: 'Resolved' }
    ])
    expect(await appSelectLabels(page, STATUS)).toEqual(['In progress', 'Pending user', 'Resolved'])
    expect(page.find('.reply-box input[type="checkbox"]').exists()).toBe(false)
  })

  it('offers no status in the internal note box', async () => {
    const { page } = await openPanel(ticketWith())

    expect(page.find('.note-box').exists()).toBe(true)
    expect(page.find('.note-box select').exists()).toBe(false)
    expect(page.find('.note-box .app-select').exists()).toBe(false)
  })

  it('takes the file types the server takes, and no more text than it keeps', async () => {
    const { page } = await openPanel(ticketWith())

    // The two pickers a person reaches, and behind each box the one its
    // Replace buttons open: one file at a time, of the same types.
    const pickers = page.findAll('input[type="file"]')
    const visible = pickers.filter((picker) => picker.attributes('aria-hidden') !== 'true')
    const replacing = pickers.filter((picker) => picker.attributes('aria-hidden') === 'true')
    expect([visible.length, replacing.length]).toEqual([2, 2])
    for (const picker of replacing) {
      expect(picker.attributes('accept')).toBe('.pdf,.png,.jpg,.jpeg,.docx')
      expect(picker.attributes('multiple')).toBeUndefined()
      expect(picker.attributes('tabindex')).toBe('-1')
    }
    for (const picker of visible) {
      expect(picker.attributes('accept')).toBe('.pdf,.png,.jpg,.jpeg,.docx')
      expect(picker.attributes('multiple')).toBeDefined()
    }
    for (const box of page.findAll('textarea')) {
      expect(box.attributes('maxlength')).toBe('2000')
    }
  })

  it('counts what has been typed against the limit', async () => {
    const panel = await openPanel(ticketWith())

    await panel.page.get(REPLY).setValue('  hello ')

    expect(panel.page.get('.reply-box__counter').text()).toBe('8/2000')
  })

  it('will not send a message that is only blank space', async () => {
    const panel = await openPanel(ticketWith())

    await panel.page.get(REPLY).setValue('   \n  ')
    expect(panel.page.get('.reply-box__send').attributes('disabled')).toBeDefined()
    await panel.page.get('.reply-box').trigger('submit')
    await flushPromises()

    expect(api.sendTicketMessage).not.toHaveBeenCalled()
  })
})

describe('sending', () => {
  it('sends a reply trimmed, as a reply, and tells the queue', async () => {
    api.sendTicketMessage.mockResolvedValue(ticketWith())
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply', `  ${TYPED}  `)

    expect(api.sendTicketMessage).toHaveBeenCalledWith(7, {
      messageType: 'support_reply',
      body: TYPED,
      files: [],
      nextStatus: 'pending_user'
    })
    expect(panel.wrapper.emitted('changed')).toHaveLength(1)
  })

  it('sends the chosen status on the SAME request as the reply', async () => {
    // Splitting it into a reply and a status change made the email read the
    // old status and pick the wrong wording.
    api.sendTicketMessage.mockResolvedValue(ticketWith({ status: 'in_progress' }))
    const panel = await openPanel(ticketWith())

    await pickAppSelect(panel.page, STATUS, 'In progress')
    await sendFrom(panel, 'reply')

    expect(api.sendTicketMessage).toHaveBeenCalledTimes(1)
    expect(api.sendTicketMessage.mock.calls[0][1]).toEqual({
      messageType: 'support_reply',
      body: TYPED,
      files: [],
      nextStatus: 'in_progress'
    })
    expect(api.updateTicket).not.toHaveBeenCalled()
  })

  it('clears the box and goes back to Pending user once the server has the reply', async () => {
    api.sendTicketMessage.mockResolvedValue(ticketWith())
    const panel = await openPanel(ticketWith())
    await pickAppSelect(panel.page, STATUS, 'Resolved')

    await sendFrom(panel, 'reply')

    expect(value(panel, REPLY)).toBe('')
    expect(appSelectText(panel.page, STATUS)).toBe('Pending user')
  })

  it('keeps the chosen status when the reply did not go', async () => {
    api.sendTicketMessage.mockRejectedValue(await refusal('Attach at most 5 files to one message.'))
    const panel = await openPanel(ticketWith())
    await pickAppSelect(panel.page, STATUS, 'Resolved')

    await sendFrom(panel, 'reply')

    expect(appSelectText(panel.page, STATUS)).toBe('Resolved')
  })

  it('never lets an internal note carry a status', async () => {
    // A note must not move the ticket: a status that says "your move" with
    // nothing on the requester's timeline asking for anything.
    api.sendTicketMessage.mockResolvedValue(ticketWith())
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'note')

    expect(api.sendTicketMessage).toHaveBeenCalledTimes(1)
    const [id, input] = api.sendTicketMessage.mock.calls[0]
    expect(id).toBe(7)
    expect(Object.keys(input)).toEqual(['messageType', 'body', 'files'])
    expect(input.messageType).toBe('internal_note')
  })

  it('sends once, however fast the second submit comes (double-submit guard)', async () => {
    // Both submits are dispatched before anything is awaited, so no re-render
    // has put `disabled` on the button yet. What stops the second is the
    // guard reading live state; the React boxes had only `disabled`.
    const answer = deferred<TicketDetail>()
    api.sendTicketMessage.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue(TYPED)

    const form = panel.page.get('.reply-box').element
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    form.dispatchEvent(new Event('submit', { cancelable: true }))
    answer.resolve(ticketWith())
    await flushPromises()

    expect(api.sendTicketMessage).toHaveBeenCalledTimes(1)
  })

  it('does not mark the note box busy while a reply is sending (T29)', async () => {
    const answer = deferred<TicketDetail>()
    api.sendTicketMessage.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith())
    await panel.page.get(NOTE).setValue('Called the school.')

    await panel.page.get(REPLY).setValue(TYPED)
    await panel.page.get('.reply-box').trigger('submit')

    expect(panel.page.get('.reply-box__send').text()).toBe('Sending…')
    expect(panel.page.get('.note-box__send').text()).toBe('Add internal note')
    expect(panel.page.get('.note-box__send').attributes('disabled')).toBeUndefined()
    answer.resolve(ticketWith())
    await flushPromises()
  })

  it('holds the text still while it is sending, so nothing typed then is lost', async () => {
    // T30 shape: the React box kept the textarea live during the send and
    // then emptied it, taking anything typed meanwhile.
    const answer = deferred<TicketDetail>()
    api.sendTicketMessage.mockReturnValue(answer.promise)
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue(TYPED)

    await panel.page.get('.reply-box').trigger('submit')

    expect(panel.page.get(REPLY).attributes('readonly')).toBeDefined()
    answer.resolve(ticketWith())
    await flushPromises()
    expect(panel.page.get(REPLY).attributes('readonly')).toBeUndefined()
  })

  it('never leaves a file sitting in the picker once it is on the list (T14/T27)', async () => {
    // Clearing only the list used to leave the old file name showing in the
    // picker while the next message went out with no attachment. The list is
    // now the one record of what will be sent, so the input is emptied the
    // moment it hands a file over, and again after a send.
    api.sendTicketMessage.mockResolvedValue(ticketWith())
    const panel = await openPanel(ticketWith())
    const picker = panel.page.get('.reply-box input[type="file"]').element as HTMLInputElement
    const file = new File(['%PDF'], 'form.pdf', { type: 'application/pdf' })
    Object.defineProperty(picker, 'files', { configurable: true, value: [file] })
    const cleared: string[] = []
    Object.defineProperty(picker, 'value', {
      configurable: true,
      get: () => 'C:\\fakepath\\form.pdf',
      set: (next: string) => cleared.push(next)
    })
    picker.dispatchEvent(new Event('change'))
    expect(cleared).toEqual([''])

    await sendFrom(panel, 'reply')

    expect(api.sendTicketMessage.mock.calls[0][1].files).toEqual([file])
    expect(cleared).toEqual(['', ''])
    expect(panel.page.find('.reply-box__chip').exists()).toBe(false)
  })

  it('puts focus back in the box after a send, for the next message', async () => {
    api.sendTicketMessage.mockResolvedValue(ticketWith())
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue(TYPED)
    ;(panel.page.get('.reply-box__send').element as HTMLButtonElement).focus()

    await panel.page.get('.reply-box').trigger('submit')
    await flushPromises()

    expect(document.activeElement).toBe(panel.page.get(REPLY).element)
  })

  it('shows the new message once the server has it, without reading the ticket again', async () => {
    api.sendTicketMessage.mockResolvedValue(
      ticketWith({
        messages: [
          messageWith({ id: 2, messageType: 'support_reply', author: { id: 1, name: 'Sam Reid' }, body: TYPED })
        ]
      })
    )
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply')

    expect(panel.page.get('.agent-timeline').text()).toContain(TYPED)
    expect(api.fetchTicketDetail).toHaveBeenCalledTimes(1)
  })
})

describe('when a message is refused', () => {
  it("shows what the server said about the reply, not 'try again'", async () => {
    // An 11 MB attachment is refused for a reason the agent can act on, and
    // the same send fails the same way however many times they retry.
    api.sendTicketMessage.mockRejectedValue(
      await refusal('Attachment exceeds the maximum allowed size of 10 MB.')
    )
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply')

    expect(alertIn(panel, '.reply-box')).toBe(
      'Attachment exceeds the maximum allowed size of 10 MB. Your text is still here.'
    )
    expect(panel.wrapper.emitted('changed')).toBeUndefined()
  })

  it('shows what the server said about an internal note too', async () => {
    api.sendTicketMessage.mockRejectedValue(await refusal('Attach at most 5 files to one message.'))
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'note')

    expect(alertIn(panel, '.note-box')).toBe(
      'Attach at most 5 files to one message. Your text is still here.'
    )
  })

  it('still says try again when the failure carries no reason', async () => {
    // A dropped connection is the case the old wording was written for, and
    // the one case where trying again is the right advice.
    api.sendTicketMessage.mockRejectedValue(new TypeError('Failed to fetch'))
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply')

    expect(alertIn(panel, '.reply-box')).toBe(
      'That did not send. Your text is still here. Try again.'
    )
  })

  it('falls back to try again when the ticket has gone', async () => {
    // Pasting the 404's two words after the standing sentence produced
    // "Ticket not found Your text is still here.", two sentences run together.
    api.sendTicketMessage.mockRejectedValue(await ticketGone())
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply')

    expect(alertIn(panel, '.reply-box')).toBe(
      'That did not send. Your text is still here. Try again.'
    )
  })

  it('does not put CSRF on the screen', async () => {
    // A stale token is refused as permission_denied like a real access
    // problem, but its words are about the request machinery. The transport
    // already retried once.
    api.sendTicketMessage.mockRejectedValue(
      await serverError(403, {
        error: 'CSRF Failed: CSRF cookie not set.',
        code: 'permission_denied',
        request_id: 'ae7172323949'
      })
    )
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply')

    expect(alertIn(panel, '.reply-box')).toBe(
      'That did not send. Your text is still here. Try again.'
    )
  })

  it('says the session changed hands instead of "try again", which cannot work', async () => {
    api.sendTicketMessage.mockRejectedValue(
      new TicketSessionError('signed-in-as-someone-else', 'the transport wording, which agent pages do not show')
    )
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'note')

    expect(alertIn(panel, '.note-box')).toBe(
      'You appear to be signed in as someone else now. This can happen if you signed in to another BIOTech page in the same browser. Please reload and sign in again. Your text is still here.'
    )
  })

  it('keeps what was typed either way', async () => {
    api.sendTicketMessage.mockRejectedValue(
      await refusal('Attachment must use an allowed file extension.')
    )
    const panel = await openPanel(ticketWith())

    await sendFrom(panel, 'reply')
    await sendFrom(panel, 'note', 'A note about it.')

    expect(value(panel, REPLY)).toBe(TYPED)
    expect(value(panel, NOTE)).toBe('A note about it.')
  })
})

/**
 * One box, two sides (D2-16): the designer's second round folds the reply box
 * and the note box into one, with two tabs, the way Zendesk and Intercom do.
 * The danger in that is a note sent to the requester, with an email, so the
 * tests are about which side is open and what can cross between them.
 */
describe('one box with a reply side and a note side', () => {
  const sides = ({ page }: Panel) =>
    page.get('[role="tablist"][aria-label="Write to"]').findAll('[role="tab"]')
  const side = (panel: Panel, label: string) => sides(panel).find((node) => node.text() === label)!
  const shown = ({ page }: Panel, selector: string) =>
    !(page.get(selector).element.closest('[role="tabpanel"]') as HTMLElement).style.display.includes('none')

  it('opens on the reply side, as two real tabs', async () => {
    const panel = await openPanel(ticketWith())

    expect(sides(panel).map((node) => [node.text(), node.attributes('aria-selected')])).toEqual([
      ['Reply to the requester', 'true'],
      ['Internal note', 'false']
    ])
    const controlled = document.getElementById(side(panel, 'Internal note').attributes('aria-controls')!)
    expect(controlled?.getAttribute('role')).toBe('tabpanel')
    expect(controlled?.querySelector('.note-box')).not.toBeNull()
    expect(shown(panel, REPLY)).toBe(true)
    expect(shown(panel, NOTE)).toBe(false)
  })

  it('turns the whole box amber on the note side', async () => {
    const panel = await openPanel(ticketWith())
    const box = panel.page.get('.composer')
    expect(box.classes()).toContain('composer--reply')

    await side(panel, 'Internal note').trigger('click')

    expect(box.classes()).toContain('composer--note')
    expect(box.classes()).not.toContain('composer--reply')
    expect(shown(panel, NOTE)).toBe(true)
    expect(shown(panel, REPLY)).toBe(false)
  })

  it('never carries words from one side to the other', async () => {
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue('For Stella')

    await side(panel, 'Internal note').trigger('click')
    expect(value(panel, NOTE)).toBe('')
    await panel.page.get(NOTE).setValue('For the team')

    await side(panel, 'Reply to the requester').trigger('click')
    expect(value(panel, REPLY)).toBe('For Stella')
    expect(value(panel, NOTE)).toBe('For the team')
  })

  it('moves between the two with the arrow keys, and the focus goes too', async () => {
    const panel = await openPanel(ticketWith())

    await side(panel, 'Reply to the requester').trigger('keydown', { key: 'ArrowRight' })
    await flushPromises()
    expect(side(panel, 'Internal note').attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(side(panel, 'Internal note').element)

    await side(panel, 'Internal note').trigger('keydown', { key: 'Home' })
    await flushPromises()
    expect(side(panel, 'Reply to the requester').attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(side(panel, 'Reply to the requester').element)
  })

  it('keeps one tab in the tab order, the open one', async () => {
    const panel = await openPanel(ticketWith())
    await side(panel, 'Internal note').trigger('click')

    expect(sides(panel).map((node) => node.attributes('tabindex'))).toEqual(['-1', '0'])
  })

  it('says under the note who will see it, and ties that to the box', async () => {
    const { page } = await openPanel(ticketWith())

    const describedBy = page.get(NOTE).attributes('aria-describedby')!
    expect(document.getElementById(describedBy)?.textContent?.trim()).toBe(
      'Only support can see this. The requester is not emailed.'
    )
  })

  it('opens the next ticket on the reply side again', async () => {
    const panel = await openPanel(ticketWith())
    await side(panel, 'Internal note').trigger('click')

    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))
    await panel.wrapper.setProps({ ticketId: 8 })
    await flushPromises()

    expect(side(panel, 'Reply to the requester').attributes('aria-selected')).toBe('true')
    expect(shown(panel, REPLY)).toBe(true)
  })
})

describe('drafts and tickets', () => {
  it('never carries a draft from one ticket to the next', async () => {
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue('Meant for ticket 7')
    await panel.page.get(NOTE).setValue('Also about 7')

    api.fetchTicketDetail.mockResolvedValue(ticketWith({ id: 8, ticketNumber: 'SUP-2026-00008' }))
    await panel.wrapper.setProps({ ticketId: 8 })
    await flushPromises()

    expect(panel.page.get('h2').text()).toContain('SUP-2026-00008')
    expect(value(panel, REPLY)).toBe('')
    expect(value(panel, NOTE)).toBe('')
  })

  it('keeps the draft when the same ticket is repainted after a change', async () => {
    api.updateTicket.mockResolvedValue(ticketWith({ priority: 'high' }))
    const panel = await openPanel(ticketWith())
    await panel.page.get(REPLY).setValue('Still typing')

    await pickChoice(panel, 'Change priority', 'High')
    await flushPromises()

    expect(value(panel, REPLY)).toBe('Still typing')
  })
})

/**
 * A file picked by mistake could not be taken off a reply or a note at all:
 * picking again replaced the whole selection, and nothing removed one file
 * (2026-10-07 testing, item 8). Every file now has its own Replace and Remove,
 * as on the student's side, and picks add up instead of replacing.
 */
describe('the files on a reply or a note', () => {
  const pdf = (name: string) => new File(['%PDF'], name, { type: 'application/pdf' })

  async function pick(panel: Panel, box: '.reply-box' | '.note-box', files: File[], which = 0) {
    const input = panel.page.findAll(`${box} input[type="file"]`)[which]!.element as HTMLInputElement
    Object.defineProperty(input, 'files', { configurable: true, value: files })
    input.dispatchEvent(new Event('change'))
    await flushPromises()
  }

  // What the first send carried, by name.
  const sentNames = () =>
    (api.sendTicketMessage.mock.calls[0]?.[1].files ?? []).map((f: File) => f.name)

  const chips = (panel: Panel, box: string) =>
    panel.page.findAll(`${box} li`).map((li) => li.find('span').text())

  async function press(panel: Panel, name: string) {
    await panel.page.get(`button[aria-label="${name}"]`).trigger('click')
  }

  for (const box of ['.reply-box', '.note-box'] as const) {
    it(`${box}: adds each pick to the list rather than replacing it`, async () => {
      api.sendTicketMessage.mockResolvedValue(ticketWith())
      const panel = await openPanel(ticketWith())

      await pick(panel, box, [pdf('one.pdf')])
      await pick(panel, box, [pdf('two.pdf'), pdf('three.pdf')])

      expect(chips(panel, box)).toEqual(['one.pdf', 'two.pdf', 'three.pdf'])
      await sendFrom(panel, box === '.reply-box' ? 'reply' : 'note')
      expect(sentNames()).toEqual([
        'one.pdf',
        'two.pdf',
        'three.pdf'
      ])
    })

    it(`${box}: removes one file and sends the rest`, async () => {
      api.sendTicketMessage.mockResolvedValue(ticketWith())
      const panel = await openPanel(ticketWith())
      await pick(panel, box, [pdf('keep.pdf'), pdf('mistake.pdf')])

      await press(panel, 'Remove mistake.pdf')

      expect(chips(panel, box)).toEqual(['keep.pdf'])
      await sendFrom(panel, box === '.reply-box' ? 'reply' : 'note')
      expect(sentNames()).toEqual([
        'keep.pdf'
      ])
    })

    it(`${box}: replaces one file in its place and keeps the others`, async () => {
      api.sendTicketMessage.mockResolvedValue(ticketWith())
      const panel = await openPanel(ticketWith())
      await pick(panel, box, [pdf('first.pdf'), pdf('wrong.pdf'), pdf('last.pdf')])

      await press(panel, 'Replace wrong.pdf')
      await pick(panel, box, [pdf('right.pdf')], 1)

      expect(chips(panel, box)).toEqual(['first.pdf', 'right.pdf', 'last.pdf'])
      await sendFrom(panel, box === '.reply-box' ? 'reply' : 'note')
      expect(sentNames()).toEqual([
        'first.pdf',
        'right.pdf',
        'last.pdf'
      ])
    })

    it(`${box}: holds the files still while a send is on its way`, async () => {
      const answer = deferred<TicketDetail>()
      api.sendTicketMessage.mockReturnValue(answer.promise)
      const panel = await openPanel(ticketWith())
      await pick(panel, box, [pdf('one.pdf')])
      await panel.page.get(box === '.reply-box' ? REPLY : NOTE).setValue(TYPED)

      await panel.page.get(box).trigger('submit')

      expect(panel.page.get('button[aria-label="Replace one.pdf"]').attributes('disabled')).toBeDefined()
      expect(panel.page.get('button[aria-label="Remove one.pdf"]').attributes('disabled')).toBeDefined()
      answer.resolve(ticketWith())
      await flushPromises()
    })
  }
})
