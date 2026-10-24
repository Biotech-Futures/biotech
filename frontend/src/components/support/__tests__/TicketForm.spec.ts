import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { appSelectLabels, appSelectText, pickAppSelect } from '@/__tests__/appSelect'
import AppSelect from '@/components/AppSelect.vue'
import TicketForm from '../TicketForm.vue'

vi.mock('@/utils/supportAPI', async () => {
  const actual = await vi.importActual<typeof import('@/utils/supportAPI')>(
    '@/utils/supportAPI'
  )
  return { ...actual, submitTicket: vi.fn() }
})

import { TICKET_CATEGORIES, submitTicket } from '@/utils/supportAPI'

// The two dropdowns are the platform's AppSelect since the 2026-10-22 client
// meeting (C-29), and each holds a text field of its own, so the subject is
// found by its placeholder rather than as "the text input".
const CATEGORY = '#ticket-category'
const URGENCY = '#ticket-urgency'
const SUBJECT = 'input[placeholder="Enter a short subject"]'
const placeholderOf = (wrapper: ReturnType<typeof mount>, selector: string) =>
  wrapper.get(selector).attributes('placeholder')

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

    expect(appSelectText(wrapper, CATEGORY)).toBe('')
    expect(placeholderOf(wrapper, CATEGORY)).toBe('Select a category')
  })

  it('renders every category the client asked for, in their order', async () => {
    // Derived from TICKET_CATEGORIES rather than retyped: the exact list and
    // its wording are pinned once, in utils/__tests__/supportAPI.spec.ts. What
    // this test adds is that the form actually renders all of them — a
    // v-for with a stale slice, or a filter someone adds later, fails here and
    // not there.
    const wrapper = mount(TicketForm)
    // Scoped to the category dropdown. There are two on the form, and a list
    // read off both would pass or fail for the wrong reason.
    const labels = await appSelectLabels(wrapper, CATEGORY)

    expect(labels).toEqual(TICKET_CATEGORIES.map((c) => c.label))
    expect(labels).toHaveLength(8)
    expect(labels).not.toContain('Programs & Groups')
  })

  it('will not submit until a category is chosen', async () => {
    const wrapper = mount(TicketForm)
    await wrapper.get(SUBJECT).setValue('Cannot sign in')
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
    await pickAppSelect(wrapper, CATEGORY, 'Help with a student or group')
    await pickAppSelect(wrapper, URGENCY, 'I can keep working')
    await wrapper.get(SUBJECT).setValue('Cannot sign in')
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
    await pickAppSelect(wrapper, CATEGORY, 'Help with a student or group')
    await pickAppSelect(wrapper, URGENCY, 'I can keep working')
    await wrapper.get(SUBJECT).setValue('Cannot sign in')
    await wrapper.get('textarea').setValue('It rejects my password.')
    await wrapper.get('form').trigger('submit')
    await new Promise((r) => setTimeout(r))

    // Back to the placeholder — otherwise the NEXT enquiry inherits this
    // one's category and files itself under it without a choice being made,
    // which is the same silent-default hole the placeholder was added for.
    expect(appSelectText(wrapper, CATEGORY)).toBe('')
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
  // "How can we help?" was this form's heading on p48. The second redesign
  // round moves it into the page header above the form (D2-01, held in
  // SupportCentrePage.spec.ts) and names the form "Raise an enquiry" (D2-02).
  const SPECIFIED = [
    'Raise an enquiry',
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
  // control and every portal ticket landed on the model default. At the
  // 8 October meeting they asked for it to start empty (C-22): "Can you make
  // that not default to anything? I would want them to select that."

  // The choices the urgency dropdown offers, as shown.
  const choices = (wrapper: ReturnType<typeof mount>) => appSelectLabels(wrapper, URGENCY)
  // And as the component hands them to it, value and words together.
  const urgencyOptions = (wrapper: ReturnType<typeof mount>) => wrapper.findAllComponents(AppSelect)[1].props('options')

  it('offers the three priorities, in urgency order', async () => {
    // Written out rather than derived from TICKET_PRIORITIES. The first
    // version compared the rendered labels against the same constant the
    // component renders from, so it was a tautology: swapping High and Low in
    // that constant left this green while the form offered them backwards.
    // The name promised an order and nothing verified one.
    const wrapper = mount(TicketForm)
    expect(await choices(wrapper)).toEqual([
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
    expect(urgencyOptions(wrapper)).toEqual([
      { value: 'high', label: 'I cannot continue' },
      { value: 'normal', label: 'I can keep working' },
      { value: 'low', label: 'It can wait' }
    ])
  })

  it('names no level, so there is no top of a scale to reach for', async () => {
    // "High / Normal / Low" is internal triage language and the audience is
    // school students. Worse, a visible top is a top everything arrives at:
    // the word is what a person answers, and an explanation beside it does
    // not argue against choosing it.
    const wrapper = mount(TicketForm)
    ;(await choices(wrapper)).forEach((label) => {
      expect(label).not.toMatch(/\b(high|normal|low|urgent|priority)\b/i)
    })
  })

  it('keeps every option short enough to survive a phone', async () => {
    // A closed dropdown does not wrap. At 320px the box measures about 179px,
    // which is roughly 26 characters at this font size — the first version of
    // this copy rendered as "I need this sorted, b". The placeholder is held
    // to it as well: it is what the closed box shows.
    const wrapper = mount(TicketForm)
    for (const text of [...(await choices(wrapper)), placeholderOf(wrapper, URGENCY)!]) {
      expect(text.length).toBeLessThanOrEqual(26)
    }
  })

  it('is labelled Urgency and starts on its placeholder, with nothing chosen', async () => {
    // The designer's label and placeholder (D2-03).
    const wrapper = mount(TicketForm)
    expect(wrapper.findAll('.ticket-form__label').map((l) => l.text())).toContain('Urgency')
    // The label names the dropdown's own field, as a label for= a select did.
    expect(wrapper.get('label[for="ticket-urgency"]').text()).toBe('Urgency')
    expect(appSelectText(wrapper, URGENCY)).toBe('')
    expect(placeholderOf(wrapper, URGENCY)).toBe('Select how urgent this is')
    // The placeholder is not a choice: the list offers the three and no more.
    expect(await choices(wrapper)).toHaveLength(3)
  })

  it('will not submit until an urgency is chosen', async () => {
    const wrapper = mount(TicketForm)
    await pickAppSelect(wrapper, CATEGORY, 'Account and access')
    await wrapper.get(SUBJECT).setValue('Cannot sign in')
    await wrapper.get('textarea').setValue('It rejects my password.')
    const button = wrapper.get('button[type="submit"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)

    // Pressing Enter in a field submits the form without the button.
    vi.mocked(submitTicket).mockClear()
    await wrapper.get('form').trigger('submit')
    expect(submitTicket).not.toHaveBeenCalled()

    await pickAppSelect(wrapper, URGENCY, 'It can wait')
    expect((button.element as HTMLButtonElement).disabled).toBe(false)
  })

  it('no longer carries the hint under the field', () => {
    // The designer took it out with the default (D2-03).
    const wrapper = mount(TicketForm)
    expect(wrapper.text()).not.toContain('Pick the one that is true for you')
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
    await pickAppSelect(wrapper, CATEGORY, 'Account and access')
    await pickAppSelect(wrapper, URGENCY, 'I cannot continue')
    await wrapper.get(SUBJECT).setValue('Locked out')
    await wrapper.get('textarea').setValue('My report is due tonight.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(send.mock.calls[0][0].priority).toBe('high')
  })

  it('goes back to its placeholder after a successful submission', async () => {
    const send = vi.mocked(submitTicket)
    send.mockClear()
    send.mockResolvedValue({
      id: 2, ticketNumber: 'SUP-2026-00002', subject: 'x',
      category: 'account_access', priority: 'high', status: 'open',
      body: 'b', createdAt: 'now', lastUpdated: 'now', messages: []
    })
    const wrapper = mount(TicketForm)
    await pickAppSelect(wrapper, CATEGORY, 'Account and access')
    await pickAppSelect(wrapper, URGENCY, 'I cannot continue')
    await wrapper.get(SUBJECT).setValue('Locked out')
    await wrapper.get('textarea').setValue('My report is due tonight.')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    // Otherwise the next enquiry the same person raises inherits an urgency
    // they set for a different problem.
    expect(appSelectText(wrapper, URGENCY)).toBe('')
  })
})

