import { flushPromises } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { TicketMessage } from '@/utils/ticketAgentSchema'

import { DOWNLOAD_ACCESS_REVOKED, DOWNLOAD_NOT_FOUND } from '../ticketDetailText'
import {
  api,
  messageWith,
  openPanel,
  resetPanelTests,
  serverError,
  ticketWith,
  type Panel
} from './ticketDetailFixtures'

// The conversation on the agent's side of the wall, through the real panel.
// Ported from the "who a message is from" and "opening an attachment" blocks
// of TicketDetailPanel.test.tsx, plus the rows React never tested (system
// line, the internal-note wall, order, plain text) and the two download
// refusals that now get their own sentence (scaffold open question O4).
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

const showing = (messages: TicketMessage[]) => openPanel(ticketWith({ messages }))
const rows = ({ page }: Panel) => page.findAll('.agent-timeline__row')

describe('the conversation', () => {
  it('lists every kind of message in the order the server sent them', async () => {
    const panel = await showing([
      messageWith({ id: 1, body: 'First, from the student.' }),
      messageWith({ id: 2, messageType: 'system', author: null, body: 'Status changed to In progress.' }),
      messageWith({ id: 3, messageType: 'internal_note', author: { id: 1, name: 'Sam Reid' }, body: 'Checked the group.' }),
      messageWith({ id: 4, messageType: 'support_reply', author: { id: 1, name: 'Sam Reid' }, body: 'Try again now.' })
    ])

    expect(rows(panel).map((row) => row.find('.agent-timeline__body, .agent-timeline__system').text())).toEqual([
      'First, from the student.',
      expect.stringContaining('Status changed to In progress.'),
      'Checked the group.',
      'Try again now.'
    ])
  })

  it('prints a system line centred and unsigned, with its time', async () => {
    const at = '2026-08-04T03:37:00Z'
    const panel = await showing([
      messageWith({ id: 2, messageType: 'system', author: null, body: 'Status changed to Resolved.', createdAt: at })
    ])

    const line = panel.page.get('.agent-timeline__system')
    expect(line.text()).toBe(
      `Status changed to Resolved. · ${new Date(at).toLocaleString('en-AU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      })}`
    )
    expect(panel.page.find('.agent-timeline__author').exists()).toBe(false)
  })

  it('walls off an internal note, and only an internal note', async () => {
    const panel = await showing([
      messageWith({ id: 1, messageType: 'support_reply', author: { id: 1, name: 'Sam Reid' }, body: 'To the student.' }),
      messageWith({ id: 2, messageType: 'internal_note', author: { id: 1, name: 'Sam Reid' }, body: 'Between us.' })
    ])

    const [reply, note] = rows(panel)
    expect(reply.classes()).not.toContain('agent-timeline__row--note')
    expect(reply.find('.agent-timeline__wall').exists()).toBe(false)
    expect(note.classes()).toContain('agent-timeline__row--note')
    const wall = note.get('.agent-timeline__wall')
    expect(wall.text()).toBe('🔒 Internal note')
    // The lock is decoration; a screen reader hears "Internal note".
    expect(wall.get('[aria-hidden="true"]').text()).toBe('🔒')
  })

  it('shows a message as the text it is, never as markup', async () => {
    const panel = await showing([messageWith({ body: '<b>bold?</b>\nsecond line' })])

    const body = panel.page.get('.agent-timeline__body')
    expect(body.text()).toBe('<b>bold?</b>\nsecond line')
    expect(body.find('b').exists()).toBe(false)
  })

  it('puts the time zone on every message time', async () => {
    const at = '2026-08-04T03:37:00Z'
    const panel = await showing([messageWith({ createdAt: at })])

    expect(panel.page.get('.agent-timeline__time').text()).toBe(
      new Date(at).toLocaleString('en-AU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        timeZoneName: 'short'
      })
    )
  })
})

describe('who a message is from', () => {
  const NO_AUTHOR = messageWith({
    id: 1,
    messageType: 'internal_note',
    author: null,
    body: 'A message was flagged by automated screening.'
  })

  it('does not claim an account was removed when none ever existed', async () => {
    // Three kinds of support row arrive with no author: an agent whose
    // account was deleted, screening's evidence note, and the note recording
    // an undeliverable email. Nothing in the payload tells them apart.
    const panel = await showing([NO_AUTHOR])

    expect(panel.page.get('.agent-timeline__author').text()).toBe('Support (author not recorded)')
    expect(panel.page.get('.agent-timeline').text()).not.toMatch(/account removed/i)
  })

  it("still keeps an unsigned support row off the requester's name", async () => {
    // An internal note is written ABOUT the student, so calling it theirs is
    // worse than saying nothing.
    const panel = await showing([
      NO_AUTHOR,
      messageWith({ id: 2, messageType: 'support_reply', author: null, body: 'Signed by nobody.' })
    ])

    expect(panel.page.findAll('.agent-timeline__author').map((node) => node.text())).toEqual([
      'Support (author not recorded)',
      'Support (author not recorded)'
    ])
  })

  it('calls an unsigned message from the student the requester', async () => {
    const panel = await showing([messageWith({ author: null })])

    expect(panel.page.get('.agent-timeline__author').text()).toBe('Requester')
  })

  it('names the person when there is one', async () => {
    const panel = await showing([{ ...NO_AUTHOR, author: { id: 4, name: 'Sam Reid' } }])

    expect(panel.page.get('.agent-timeline__author').text()).toBe('Sam Reid')
    expect(panel.page.get('.agent-timeline').text()).not.toMatch(/author not recorded/i)
  })
})

/**
 * ⚠️ Structural, not behavioural, and on purpose. jsdom cannot navigate:
 * clicking an `<a href>` logs "Not implemented: navigation" and leaves the
 * document standing, so a test that typed a draft, clicked a broken link and
 * asserted the draft survived would pass WITH THE BUG PRESENT. What is pinned
 * here is that there is no anchor at the endpoint and that a refusal is
 * rendered in the panel; the behavioural proof is a real browser.
 */
describe('opening an attachment', () => {
  const WITH_FILES = messageWith({
    id: 1,
    body: 'Screenshots attached.',
    // Attachment ids that are not the ticket's id (7). The React fixture used
    // 7 for both, so a call with the two ids swapped still passed.
    attachments: [
      { id: 17, filename: 'gone.png', mimeType: 'image/png', size: 1024 },
      { id: 18, filename: 'fine.png', mimeType: 'image/png', size: 2048 }
    ]
  })

  const fileButton = ({ page }: Panel, name: string) => {
    const found = page.findAll('button.agent-timeline__file').find((node) => node.text() === name)
    if (!found) throw new Error(`no button for ${name}`)
    return found
  }

  const errors = ({ page }: Panel) => page.findAll('.agent-timeline__file-error')

  it('does not point the browser at the download endpoint', async () => {
    // Asserted on the endpoint rather than on the tag, because an anchor with
    // a click handler and a live href is still middle-clickable into the bug.
    // Read off the whole document: the panel is teleported to body.
    const panel = await showing([WITH_FILES])

    expect(fileButton(panel, 'gone.png').element.tagName).toBe('BUTTON')
    const hrefs = Array.from(document.body.querySelectorAll('a')).map(
      (link) => link.getAttribute('href') ?? ''
    )
    expect(hrefs.filter((href) => href.includes('/attachments/'))).toEqual([])
  })

  it('fetches the file under the name the panel is showing', async () => {
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(api.downloadTicketAttachment).toHaveBeenCalledWith(7, 17, 'gone.png')
  })

  it('says why the file did not open, in the panel, and stays on it', async () => {
    api.downloadTicketAttachment.mockRejectedValue(
      await serverError(404, { msg: 'Attachment not found', data: null })
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(errors(panel).map((node) => node.text())).toEqual([
      'This file could not be found. Its ticket or message may have been deleted, or the file is missing from storage. Reload the queue to check.'
    ])
    expect(errors(panel)[0].attributes('role')).toBe('alert')
    // Still the panel, still offering both files.
    expect(fileButton(panel, 'fine.png').exists()).toBe(true)
  })

  it('tells an expired session apart from a file that is gone', async () => {
    // Signed out is a 403 here, not a 401 (SessionAuthentication sends no
    // WWW-Authenticate), and DRF names it not_authenticated.
    api.downloadTicketAttachment.mockRejectedValue(
      await serverError(403, {
        error: 'Authentication credentials were not provided.',
        code: 'not_authenticated',
        request_id: 'abc'
      })
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(errors(panel)[0].text()).toBe(
      'Your session has expired. Reload this page and sign in again to open this file.'
    )
  })

  it('tells an agent whose queue access was revoked that, not that their session expired (O4)', async () => {
    // Signing in again gets the same answer, so "your session has expired"
    // sends them round a loop.
    api.downloadTicketAttachment.mockRejectedValue(
      await serverError(403, {
        error: 'You do not have support privileges.',
        code: 'permission_denied',
        request_id: 'def'
      })
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(errors(panel)[0].text()).toBe(
      'You no longer have access to the support queue, so this file cannot be opened. Ask an admin if you still need access.'
    )
    expect(errors(panel)[0].text()).toBe(DOWNLOAD_ACCESS_REVOKED)
  })

  it('does not claim a deletion for a 404 that a file lost from storage answers too (O4)', async () => {
    // The body the admin download really sends when storage has lost the
    // file: the same one it sends for a deleted row, on purpose (views_admin
    // TicketAdminAttachmentDownloadView; backend test_attachment_streaming.py
    // NOT_FOUND asserts exactly this body for a blob missing on Azure and a
    // file missing from local disk). Nothing was deleted, and the queue still
    // shows the ticket, so a sentence that says "was deleted" is false here.
    api.downloadTicketAttachment.mockRejectedValue(
      await serverError(404, { msg: 'Attachment not found', data: null })
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(errors(panel)[0].text()).toBe(DOWNLOAD_NOT_FOUND)
    expect(errors(panel)[0].text()).toContain('or the file is missing from storage')
    expect(errors(panel)[0].text()).not.toContain('was deleted')
  })

  it('says try again for a fault, which is the one case where that helps', async () => {
    api.downloadTicketAttachment.mockRejectedValue(
      await serverError(500, {
        error: 'Internal server error',
        code: 'internal_server_error',
        request_id: 'e1'
      })
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(errors(panel)[0].text()).toBe('Could not download that file. Try again.')
  })

  it('lets a second file download while the first is still going', async () => {
    // The regression a global "busy" flag would bring: a click on the
    // neighbouring file doing nothing at all while the first is in flight.
    let releaseFirst: () => void = () => {}
    api.downloadTicketAttachment.mockImplementationOnce(
      () => new Promise<void>((resolve) => (releaseFirst = resolve))
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await fileButton(panel, 'fine.png').trigger('click')
    releaseFirst()
    await flushPromises()

    expect(api.downloadTicketAttachment).toHaveBeenCalledTimes(2)
    expect(api.downloadTicketAttachment).toHaveBeenCalledWith(7, 18, 'fine.png')
  })

  it('ignores a second click on the file already downloading', async () => {
    // Both clicks are dispatched before anything is awaited, so no re-render
    // has marked the button busy. What stops the second call is the guard in
    // the handler, which reads live reactive state.
    let release: () => void = () => {}
    api.downloadTicketAttachment.mockImplementationOnce(
      () => new Promise<void>((resolve) => (release = resolve))
    )
    const panel = await showing([WITH_FILES])

    const button = fileButton(panel, 'gone.png').element as HTMLButtonElement
    button.click()
    button.click()
    release()
    await flushPromises()

    expect(api.downloadTicketAttachment).toHaveBeenCalledTimes(1)
  })

  it('ignores a press on a file already marked busy', async () => {
    // The button is never `disabled` (see the focus test below), so a click
    // after the re-render reaches the handler too, and the guard is all that
    // stands between it and a second download.
    let release: () => void = () => {}
    api.downloadTicketAttachment.mockImplementationOnce(
      () => new Promise<void>((resolve) => (release = resolve))
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()
    expect(fileButton(panel, 'gone.png').attributes('aria-disabled')).toBe('true')
    await fileButton(panel, 'gone.png').trigger('click')
    release()
    await flushPromises()

    expect(api.downloadTicketAttachment).toHaveBeenCalledTimes(1)
  })

  it('keeps focus on the file while it downloads: marked busy, not disabled', async () => {
    // A browser moves focus off a button that becomes disabled, to the page
    // body, which is outside this modal panel. jsdom does not, so the test
    // does what the browser would (the HTML "focus fixup" rule) to any
    // disabled button that has focus. jsdom also ignores blur() on a disabled
    // element, hence the enable, blur, disable.
    const focusFixup = () => {
      const active = document.activeElement
      if (active instanceof HTMLButtonElement && active.disabled) {
        active.disabled = false
        active.blur()
        active.disabled = true
      }
    }
    let release: () => void = () => {}
    api.downloadTicketAttachment.mockImplementationOnce(
      () => new Promise<void>((resolve) => (release = resolve))
    )
    const panel = await showing([WITH_FILES])
    const button = fileButton(panel, 'gone.png')
    ;(button.element as HTMLButtonElement).focus()

    await button.trigger('click')
    await flushPromises()
    focusFixup()

    expect(button.attributes('aria-disabled')).toBe('true')
    expect((button.element as HTMLButtonElement).disabled).toBe(false)
    expect(document.activeElement).toBe(button.element)

    release()
    await flushPromises()
    expect(button.attributes('aria-disabled')).toBeUndefined()
    expect(document.activeElement).toBe(button.element)
  })

  it('lets the same file be downloaded again once the first one finishes', async () => {
    // busy has to be cleared in `finally`, or the button is marked busy, and
    // ignores every press, for the rest of the session after one click.
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()
    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    expect(api.downloadTicketAttachment).toHaveBeenCalledTimes(2)
    expect(fileButton(panel, 'gone.png').attributes('aria-disabled')).toBeUndefined()
  })

  it('blames only the file that failed, not the one next to it', async () => {
    api.downloadTicketAttachment.mockRejectedValue(
      await serverError(404, { msg: 'Attachment not found', data: null })
    )
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()

    const items = panel.page.findAll('.agent-timeline__files > li')
    const withErrors = items.filter((item) => item.find('.agent-timeline__file-error').exists())
    expect(withErrors).toHaveLength(1)
    expect(withErrors[0].text()).toContain('gone.png')
  })

  it('clears a stale error when the same file is tried again', async () => {
    api.downloadTicketAttachment
      .mockRejectedValueOnce(await serverError(500, { error: 'x', code: 'internal_server_error', request_id: 'r' }))
      .mockResolvedValueOnce(undefined)
    const panel = await showing([WITH_FILES])

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()
    expect(errors(panel)).toHaveLength(1)

    await fileButton(panel, 'gone.png').trigger('click')
    await flushPromises()
    expect(errors(panel)).toHaveLength(0)
  })
})
