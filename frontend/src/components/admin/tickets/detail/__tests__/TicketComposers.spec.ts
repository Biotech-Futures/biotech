import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TicketSessionError } from '@/utils/ticketTransport'
import type { TicketDetail } from '@/utils/ticketAgentSchema'

import {
  api,
  deferred,
  messageWith,
  openPanel,
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
// boxes never had a test for: moveToPending on the one request, the reset
// after a send, the double-submit guard, one pending flag per box, and the
// file input emptied after a send.
vi.mock('@/utils/ticketAgentAPI', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/ticketAgentAPI')>()),
  fetchTicketDetail: vi.fn(),
  fetchAssignees: vi.fn(),
  fetchTicketHistory: vi.fn(),
  updateTicket: vi.fn(),
  sendTicketMessage: vi.fn(),
  deleteTicket: vi.fn(),
  downloadTicketAttachment: vi.fn()
}))

beforeEach(resetPanelTests)
afterEach(resetPanelTests)

const REPLY = 'textarea[aria-label="Reply to the requester"]'
const NOTE = 'textarea[aria-label="Internal note, not visible to the requester"]'
const TYPED = 'Here is the form you asked for.'

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

    const names = page.findAll('input[type="file"], textarea').map((node) => accessibleName(node.element))

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

    const names = page.findAll('input[type="file"], textarea').map((node) => accessibleName(node.element))

    expect(names).toEqual([
      'Reply to the requester',
      'Attach files to this reply',
      'Internal note, not visible to the requester',
      'Attach files to this internal note'
    ])
  })

  it('ties the "wait for their reply" label to its checkbox', async () => {
    const { page } = await openPanel(ticketWith())

    const box = page.get('.reply-box input[type="checkbox"]')
    expect(accessibleName(box.element)).toBe('I have asked them for something. Wait for their reply.')
    expect((box.element as HTMLInputElement).checked).toBe(false)
  })

  it('takes the file types the server takes, and no more text than it keeps', async () => {
    const { page } = await openPanel(ticketWith())

    for (const picker of page.findAll('input[type="file"]')) {
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
      moveToPending: false
    })
    expect(panel.wrapper.emitted('changed')).toHaveLength(1)
  })

  it('folds "wait for their reply" into the SAME request as the reply', async () => {
    // Splitting it into a reply and a status change made the email read the
    // old status and pick the wrong wording.
    api.sendTicketMessage.mockResolvedValue(ticketWith({ status: 'pending_user' }))
    const panel = await openPanel(ticketWith())

    await panel.page.get('.reply-box input[type="checkbox"]').setValue(true)
    await sendFrom(panel, 'reply')

    expect(api.sendTicketMessage).toHaveBeenCalledTimes(1)
    expect(api.sendTicketMessage.mock.calls[0][1]).toEqual({
      messageType: 'support_reply',
      body: TYPED,
      files: [],
      moveToPending: true
    })
    expect(api.updateTicket).not.toHaveBeenCalled()
  })

  it('clears the box and the tick once the server has the reply', async () => {
    api.sendTicketMessage.mockResolvedValue(ticketWith())
    const panel = await openPanel(ticketWith())
    await panel.page.get('.reply-box input[type="checkbox"]').setValue(true)

    await sendFrom(panel, 'reply')

    expect(value(panel, REPLY)).toBe('')
    expect((panel.page.get('.reply-box input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false)
  })

  it('keeps the tick when the reply did not go', async () => {
    api.sendTicketMessage.mockRejectedValue(await refusal('Attach at most 5 files to one message.'))
    const panel = await openPanel(ticketWith())
    await panel.page.get('.reply-box input[type="checkbox"]').setValue(true)

    await sendFrom(panel, 'reply')

    expect((panel.page.get('.reply-box input[type="checkbox"]').element as HTMLInputElement).checked).toBe(true)
  })

  it('never lets an internal note carry moveToPending', async () => {
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

  it('empties the file picker after a send, not just the list behind it (T14/T27)', async () => {
    // Clearing only the list left the old file name showing in the picker
    // while the next message went out with no attachment.
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

    await sendFrom(panel, 'reply')

    expect(api.sendTicketMessage.mock.calls[0][1].files).toEqual([file])
    expect(cleared).toEqual([''])
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

    await panel.page.get('select[aria-label="Change priority"]').setValue('high')
    await flushPromises()

    expect(value(panel, REPLY)).toBe('Still typing')
  })
})
