import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import TicketForm from '../TicketForm.vue'

vi.mock('@/utils/supportAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/supportAPI')>(
    '@/utils/supportAPI'
  )
  return { ...actual, submitTicket: vi.fn() }
})

import { TICKET_CATEGORIES, TICKET_PRIORITIES, submitTicket } from '@/utils/supportAPI'

/**
 * The category dropdown is a data-collection default, not a piece of styling.
 *
 * It used to start on the first option, so anybody who never touched it filed
 * their enquiry under "Account & Access" without choosing it, and afterwards
 * nothing could separate those from a real choice. That silently ruins the
 * category breakdown the client asked for on p52, which is why the placeholder
 * gets tests of its own rather than being taken on trust.
 */
describe('TicketForm category', () => {
  it('starts on the placeholder, not on the first real category', () => {
    const wrapper = mount(TicketForm)
    const select = wrapper.get('select')

    expect((select.element as HTMLSelectElement).value).toBe('')
    expect(select.text()).toContain('Select a category')
  })

  it('renders every category the client asked for, in their order', () => {
    // Derived from TICKET_CATEGORIES rather than retyped: the exact list and
    // its wording are pinned once, in utils/__tests__/supportAPI.spec.ts. What
    // this test adds is that the form actually renders all of them — a
    // v-for with a stale slice, or a filter someone adds later, fails here and
    // not there.
    const wrapper = mount(TicketForm)
    // Scoped to the first select. There are two on the form now — category and
    // priority — and a bare findAll('option') would count both lists and pass
    // or fail for the wrong reason.
    const labels = wrapper
      .findAll('select')[0]
      .findAll('option')
      .map((o) => o.text())
      .filter((t) => t !== 'Select a category')

    expect(labels).toEqual(TICKET_CATEGORIES.map((c) => c.label))
    expect(labels).toHaveLength(8)
    expect(labels).not.toContain('Programs & Groups')
  })

  it('will not submit until a category is chosen', async () => {
    const wrapper = mount(TicketForm)
    await wrapper.get('input[type="text"]').setValue('Cannot sign in')
    await wrapper.get('textarea').setValue('It rejects my password.')

    const button = wrapper.get('button[type="submit"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)

    // Belt and braces: submitting the form directly, the way pressing Enter in
    // a text input does, must not slip past the disabled button.
    await wrapper.get('form').trigger('submit')
    expect(submitTicket).not.toHaveBeenCalled()
  })

  it('submits once a category is chosen, and sends that category', async () => {
    const send = vi.mocked(submitTicket)
    send.mockResolvedValue({
      id: 1,
      ticketNumber: 'SUP-2026-00001',
      subject: 'Cannot sign in',
      category: 'help_student_group', priority: 'normal',
      status: 'open',
      body: 'It rejects my password.',
      createdAt: '2026-08-31T00:00:00Z',
      lastUpdated: '2026-08-31T00:00:00Z',
      messages: [],
    })

    const wrapper = mount(TicketForm)
    await wrapper.get('select').setValue('help_student_group')
    await wrapper.get('input[type="text"]').setValue('Cannot sign in')
    await wrapper.get('textarea').setValue('It rejects my password.')
    await wrapper.get('form').trigger('submit')

    expect(send).toHaveBeenCalledTimes(1)
    expect(send.mock.calls[0][0].category).toBe('help_student_group')
  })
})


/**
 * Two numbers and a reset the client's p48 mock-up specifies directly. The
 * 2000 cap already had one asymmetry: MAX_ATTACHMENTS=5 was pinned and the
 * body cap was not, so one could drift and not the other.
 */
describe('TicketForm contract numbers', () => {
  it('caps the message body at exactly 2000 characters', async () => {
    const { MAX_BODY_LENGTH } = await import('@/utils/supportAPI')
    expect(MAX_BODY_LENGTH).toBe(2000)

    const wrapper = mount(TicketForm)
    expect(wrapper.get('textarea').attributes('maxlength')).toBe('2000')
    // Spaced the way the client's mock-up prints it: "0 / 2000".
    expect(wrapper.text()).toContain('0 / 2000')
  })

  it('returns the category to the placeholder after a successful submit', async () => {
    vi.mocked(submitTicket).mockResolvedValueOnce({
      id: 1, ticketNumber: 'SUP-2026-00001', subject: 'x', category: 'help_student_group', priority: 'normal',
      status: 'open', lastUpdated: '2026-08-01T00:00:00Z', createdAt: '2026-08-01T00:00:00Z',
      messages: [], region: '',
    } as never)
    const wrapper = mount(TicketForm)
    await wrapper.get('select').setValue('help_student_group')
    await wrapper.get('input[type="text"]').setValue('Cannot sign in')
    await wrapper.get('textarea').setValue('It rejects my password.')
    await wrapper.get('form').trigger('submit')
    await new Promise((r) => setTimeout(r))

    // Back to the placeholder — otherwise the NEXT enquiry inherits this
    // one's category and files itself under it without a choice being made,
    // which is the same silent-default hole the placeholder was added for.
    expect((wrapper.get('select').element as HTMLSelectElement).value).toBe('')
  })
})

describe('the wording the client showed on p48', () => {
  /**
   * p48 is marked ILLUSTRATIVE CONCEPT, so the layout is negotiable and the
   * numbers on it are not. The copy sits in between: nothing forces us to use
   * the client's exact words, but drifting off them ("Category" for "Issue
   * category", "A short summary" for "Enter a short subject", "Submit
   * enquiry" for "Submit ticket") is the kind of difference nobody notices in
   * review and the client notices in the first thirty seconds of a demo.
   * Pinned here so it cannot drift back silently.
   */
  const SPECIFIED = [
    'How can we help?',
    'Issue category',
    'Select a category',
    'Enter a short subject',
    'Describe your issue in detail...',
    'Submit ticket',
    // The counter is printed with spaces around the slash on the mock-up.
    '0 / 2000',
  ]

  it('renders every string from the specification page', () => {
    const wrapper = mount(TicketForm)
    const html = wrapper.html()
    for (const text of SPECIFIED) {
      expect(html).toContain(text)
    }
  })
})

describe('TicketForm priority', () => {
  // The client settled on 2026-09-04 that "the person raising the enquiry (not
  // necessarily a student) should be able to set a priority, but the support
  // agent should be able to change it". Before that the form had no such
  // control and every portal ticket landed on the model default.

  it('offers the three priorities, in urgency order', () => {
    // Written out rather than derived from TICKET_PRIORITIES. The first
    // version compared the rendered labels against the same constant the
    // component renders from, so it was a tautology: swapping High and Low in
    // that constant left this green while the form offered them backwards.
    // The name promised an order and nothing verified one.
    const wrapper = mount(TicketForm)
    const labels = wrapper
      .findAll('select')[1]
      .findAll('option')
      .map((o) => o.text())
    expect(labels).toEqual([
      'I cannot continue',
      'I can keep working',
      'It can wait'
    ])
  })

  it('maps each option to the value the backend stores', () => {
    // The other half. Labels are the portal's own wording and the stored
    // values are the queue's; a test on the text alone would not notice the
    // two being wired up the wrong way round.
    const wrapper = mount(TicketForm)
    const values = wrapper
      .findAll('select')[1]
      .findAll('option')
      .map((o) => (o.element as HTMLOptionElement).value)
    expect(values).toEqual(['high', 'normal', 'low'])
  })

  it('names no level, so there is no top of a scale to reach for', () => {
    // "High / Normal / Low" is internal triage language and the audience is
    // school students. Worse, a visible top is a top everything arrives at:
    // the word is what a person answers, and an explanation beside it does
    // not argue against choosing it.
    const wrapper = mount(TicketForm)
    const labels = wrapper
      .findAll('select')[1]
      .findAll('option')
      .map((o) => o.text())
    labels.forEach((label) => {
      expect(label).not.toMatch(/\b(high|normal|low|urgent|priority)\b/i)
    })
  })

  it('keeps every option short enough to survive a phone', () => {
    // A closed <select> does not wrap. At 320px the control measures about
    // 179px, which is roughly 26 characters at this font size — the first
    // version of this copy rendered as "I need this sorted, b". The default
    // option is the one line a student who never touches the dropdown reads.
    const wrapper = mount(TicketForm)
    wrapper
      .findAll('select')[1]
      .findAll('option')
      .forEach((o) => expect(o.text().length).toBeLessThanOrEqual(26))
  })

  it('puts the fuller explanation where it can wrap', () => {
    // What the short labels gave up has to land somewhere a phone can render
    // it, or the scale is three bare fragments.
    const wrapper = mount(TicketForm)
    expect(wrapper.text()).toContain('Pick the one that is true for you')
  })

  it('starts on Normal, so the field is never left empty', () => {
    const wrapper = mount(TicketForm)
    expect((wrapper.findAll('select')[1].element as HTMLSelectElement).value).toBe(
      'normal'
    )
  })

  it('does not block submission the way a missing category does', async () => {
    // A blank category is a fact we do not have. A blank urgency has an
    // honest default, and making it required is what pushes people to High.
    const wrapper = mount(TicketForm)
    await wrapper.findAll('select')[0].setValue('account_access')
    await wrapper.get('input[type="text"]').setValue('Cannot sign in')
    await wrapper.get('textarea').setValue('It rejects my password.')
    expect(
      (wrapper.get('button[type="submit"]').element as HTMLButtonElement).disabled
    ).toBe(false)
  })

  it('sends the chosen priority', async () => {
    const send = vi.mocked(submitTicket)
    // Cleared, because this file has no global reset and the earlier
    // describe block already called it: without this, calls[0] is somebody
    // else's submission and the assertion below reads the wrong payload.
    send.mockClear()
    send.mockResolvedValue({
      id: 1, ticketNumber: 'SUP-2026-00001', subject: 'x',
      category: 'account_access', priority: 'high', status: 'open',
      body: 'b', createdAt: 'now', lastUpdated: 'now', messages: []
    })
    const wrapper = mount(TicketForm)
    await wrapper.findAll('select')[0].setValue('account_access')
    await wrapper.findAll('select')[1].setValue('high')
    await wrapper.get('input[type="text"]').setValue('Locked out')
    await wrapper.get('textarea').setValue('My report is due tonight.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(send.mock.calls[0][0].priority).toBe('high')
  })

  it('goes back to Normal after a successful submission', async () => {
    const send = vi.mocked(submitTicket)
    send.mockClear()
    send.mockResolvedValue({
      id: 2, ticketNumber: 'SUP-2026-00002', subject: 'x',
      category: 'account_access', priority: 'high', status: 'open',
      body: 'b', createdAt: 'now', lastUpdated: 'now', messages: []
    })
    const wrapper = mount(TicketForm)
    await wrapper.findAll('select')[0].setValue('account_access')
    await wrapper.findAll('select')[1].setValue('high')
    await wrapper.get('input[type="text"]').setValue('Locked out')
    await wrapper.get('textarea').setValue('My report is due tonight.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    // Otherwise the next enquiry the same person raises inherits an urgency
    // they set for a different problem.
    expect((wrapper.findAll('select')[1].element as HTMLSelectElement).value).toBe(
      'normal'
    )
  })
})

