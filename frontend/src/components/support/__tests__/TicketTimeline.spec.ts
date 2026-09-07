import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TicketTimeline from '../TicketTimeline.vue'
import type { TicketMessage } from '@/utils/supportAPI'

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
    const wrapper = render([
      message({
        id: 1,
        attachments: [
          { id: 7, filename: 'screenshot.png', mimeType: 'image/png', size: 1024 },
        ],
      }),
    ])

    const link = wrapper.get('a')
    expect(link.text()).toContain('screenshot.png')
    expect(link.attributes('href')).toContain('/api/v1/tickets/42/attachments/7/')
  })

  it('opens an attachment in this tab, not a new one', () => {
    // The endpoint sends Content-Disposition: attachment, so nothing navigates
    // and nothing needs a tab. With target="_blank", WebKit opened one per
    // click and left every one of them behind: measured at 3 blank tabs after
    // 3 clicks in WebKit 26.0, and 0 with the target gone. Chromium closes
    // them either way, which is why nobody saw it.
    const wrapper = render([
      message({
        id: 1,
        attachments: [
          { id: 7, filename: 'screenshot.png', mimeType: 'image/png', size: 1024 },
        ],
      }),
    ])

    expect(wrapper.get('a').attributes('target')).toBeUndefined()
  })
})
