import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/utils/apiError'
import type { TicketMessage } from '@/utils/supportAPI'

// Only the network call is stubbed. attachmentErrorMessage stays real: it is
// the thing under test in three of the cases below, and a stub of it would be
// the sentences asserting themselves.
const downloadTicketAttachment = vi.fn()
vi.mock('@/utils/supportAPI', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/utils/supportAPI')>()),
  downloadTicketAttachment: (...args: unknown[]) => downloadTicketAttachment(...args)
}))

const TicketTimeline = (await import('../TicketTimeline.vue')).default

/** A refusal shaped the way apiErrorFromResponse really builds one, from the
 *  bodies measured against the live endpoint: `{msg, data}` from the view and
 *  `{detail}` from serve_managed_file. */
function refusal(status: number, message: string) {
  return new ApiError(
    { error: message, code: `http_${status}`, request_id: 'a1b2c3d4e5f6' },
    status
  )
}

function attachment(id: number, filename: string) {
  return { id, filename, mimeType: 'image/png', size: 1024 }
}

/**
 * The last link in the chain that answers a student.
 *
 * The backend decides what the requester may see, and it is tested there. But
 * this component keeps its own allow-list, so deleting one string from that
 * array mutes support replies with every backend test still green and every
 * other frontend test still green. That is the gap this file exists to close.
 */

function message(overrides: Partial<TicketMessage> = {}): TicketMessage {
  return {
    id: 1,
    messageType: 'user_message',
    body: 'I cannot open my group.',
    author: 'Mia Thompson',
    createdAt: '2026-08-31T02:00:00Z',
    attachments: [],
    ...overrides,
  }
}

function render(messages: TicketMessage[]) {
  return mount(TicketTimeline, { props: { ticketId: 42, messages } })
}

describe('TicketTimeline', () => {
  it('shows the body of a support reply', () => {
    // The system's only written promise to a requester is that they get an
    // answer here. If this assertion is the one that fails, the platform has
    // gone silent on a student.
    const wrapper = render([
      message({ id: 1 }),
      message({
        id: 2,
        messageType: 'support_reply',
        author: 'Support',
        body: 'Try resetting from the login page.',
      }),
    ])

    expect(wrapper.text()).toContain('Try resetting from the login page.')
  })

  it('attributes a support reply to the role, never to a named person', () => {
    const wrapper = render([
      message({ id: 2, messageType: 'support_reply', author: 'Support' }),
    ])

    expect(wrapper.text()).toContain('Support')
  })

  it('shows the requester their own message and the system notes', () => {
    const wrapper = render([
      message({ id: 1, body: 'I cannot open my group.' }),
      message({
        id: 2,
        messageType: 'system',
        author: null,
        body: 'Ticket reopened following your reply.',
      }),
    ])

    expect(wrapper.text()).toContain('I cannot open my group.')
    expect(wrapper.text()).toContain('Ticket reopened following your reply.')
  })

  it('renders nothing for an internal note, even if one ever reaches it', () => {
    // Belt and braces. The backend strips these at the queryset, which is
    // where the rule lives; this asserts the component would not surface one
    // if a future change let it through.
    const wrapper = render([
      message({ id: 1, body: 'Visible to the student.' }),
      message({
        id: 2,
        messageType: 'internal_note' as TicketMessage['messageType'],
        author: 'Sam Reid',
        body: 'SECRET-DO-NOT-LEAK',
      }),
    ])

    expect(wrapper.text()).toContain('Visible to the student.')
    expect(wrapper.text()).not.toContain('SECRET-DO-NOT-LEAK')
    expect(wrapper.text()).not.toContain('Sam Reid')
  })

  it('lists attachments against the message that carries them', () => {
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'screenshot.png')] })])

    expect(wrapper.get('button.timeline__file').text()).toContain('screenshot.png')
  })
})

/**
 * Opening an attachment.
 *
 * ⚠️ These assertions are deliberately STRUCTURAL, not behavioural, and the
 * reason matters. jsdom cannot navigate: clicking an `<a href>` there logs
 * "Not implemented: navigation" and leaves the document standing. So a test
 * that typed a draft, clicked a broken link and asserted the draft survived
 * would pass WITH THE BUG PRESENT. That is exactly the shape of fake test this
 * project has shipped before. The behavioural proof is the real-browser run in
 * e2e/tickets.spec.ts and in the report; what is pinned here is that there is
 * no anchor pointing at the endpoint, and that a refusal is rendered.
 */
describe('TicketTimeline opening an attachment', () => {
  beforeEach(() => {
    downloadTicketAttachment.mockReset()
    downloadTicketAttachment.mockResolvedValue(undefined)
  })

  it('never points the browser at the download endpoint', () => {
    // The defect itself. An anchor to this URL is a navigation the browser
    // commits to before it knows the answer, so a 403 or 404 replaces the
    // whole app and the reply box goes with it. Asserted on the endpoint
    // rather than on the tag, because an anchor with a click handler and a
    // live href is still middle-clickable straight into the bug.
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'screenshot.png')] })])

    // The guard first, so the scan below cannot pass on an empty render.
    expect(wrapper.get('button.timeline__file').text()).toContain('screenshot.png')
    const hrefs = wrapper.findAll('a').map((link) => link.attributes('href') ?? '')
    expect(hrefs.filter((href) => href.includes('/attachments/'))).toEqual([])
  })

  it('fetches the file, under the name the timeline is showing', async () => {
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'screenshot.png')] })])

    await wrapper.get('button.timeline__file').trigger('click')

    expect(downloadTicketAttachment).toHaveBeenCalledWith(42, 7, 'screenshot.png')
  })

  it('says why the file did not open, and leaves the page where it is', async () => {
    downloadTicketAttachment.mockRejectedValue(refusal(404, 'Attachment not found'))
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'screenshot.png')] })])

    await wrapper.get('button.timeline__file').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.get('.timeline__file-error').text()).toBe(
      'That file is not available any more. Reload this page to see the latest version of this enquiry.'
    )
    // Still rendering the timeline, still offering the file.
    expect(wrapper.find('button.timeline__file').exists()).toBe(true)
  })

  it('tells an expired session apart from a file that is gone', async () => {
    downloadTicketAttachment.mockRejectedValue(refusal(403, 'Authentication credentials were not provided.'))
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'screenshot.png')] })])

    await wrapper.get('button.timeline__file').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(wrapper.get('.timeline__file-error').text()).toBe(
      'Your sign-in has expired. Reload this page and sign in again to open this file.'
    )
  })

  it('blames only the file that failed, not the one next to it', async () => {
    // Five files fit on one message. One error string for the whole component
    // would put a "this file is gone" line under a file that is perfectly
    // fine.
    downloadTicketAttachment.mockRejectedValue(refusal(404, 'Attachment not found'))
    const wrapper = render([
      message({ id: 1, attachments: [attachment(7, 'gone.png'), attachment(8, 'fine.png')] }),
    ])

    await wrapper.findAll('button.timeline__file')[0].trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))

    // The <li> per file, not the outer row <li>, which contains both.
    const rows = wrapper.findAll('.timeline__files > li')
    const withErrors = rows.filter((row) => row.find('.timeline__file-error').exists())
    expect(withErrors).toHaveLength(1)
    expect(withErrors[0].text()).toContain('gone.png')
  })

  it('lets a second file download while the first is still going', async () => {
    // The regression this guard could have introduced. One global "busy" flag
    // makes a click on the neighbouring file do nothing at all, silently,
    // while the first is in flight — a thing the anchor it replaced never did.
    let releaseFirst: () => void = () => {}
    downloadTicketAttachment.mockImplementationOnce(
      () => new Promise<void>((resolve) => (releaseFirst = resolve))
    )
    const wrapper = render([
      message({ id: 1, attachments: [attachment(7, 'slow.png'), attachment(8, 'quick.png')] }),
    ])

    const buttons = wrapper.findAll('button.timeline__file')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    releaseFirst()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(downloadTicketAttachment).toHaveBeenCalledTimes(2)
    expect(downloadTicketAttachment).toHaveBeenCalledWith(42, 8, 'quick.png')
  })

  it('ignores a second click on the file already downloading', async () => {
    // Both clicks are dispatched BEFORE awaiting, so no re-render has happened
    // and the `disabled` attribute is not yet on the button. What stops the
    // second call here is the guard in the handler, which is the point: in a
    // real browser two clicks can land inside one frame. Deleting the guard
    // and leaving only `disabled` leaves this test red — measured.
    let release: () => void = () => {}
    downloadTicketAttachment.mockImplementationOnce(
      () => new Promise<void>((resolve) => (release = resolve))
    )
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'slow.png')] })])

    const button = wrapper.get('button.timeline__file')
    button.trigger('click')
    button.trigger('click')
    release()
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(downloadTicketAttachment).toHaveBeenCalledTimes(1)
  })

  it('clears a stale error when the same file is tried again', async () => {
    downloadTicketAttachment.mockRejectedValueOnce(refusal(404, 'Attachment not found'))
    const wrapper = render([message({ id: 1, attachments: [attachment(7, 'screenshot.png')] })])

    await wrapper.get('button.timeline__file').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(wrapper.find('.timeline__file-error').exists()).toBe(true)

    await wrapper.get('button.timeline__file').trigger('click')
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(wrapper.find('.timeline__file-error').exists()).toBe(false)
  })
})
