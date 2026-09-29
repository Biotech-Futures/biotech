import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'

import TicketAnalyticsPage from '@/views/admin/tickets/TicketAnalyticsPage.vue'
import { ApiError } from '@/utils/apiError'
import { fetchAssignees, fetchTicketAnalytics } from '@/utils/ticketAgentAPI'
import { ticketAnalyticsSchema, type AssigneeOption, type TicketAnalytics } from '@/utils/ticketAgentSchema'

// Only the two requests are replaced. The error readers (wasRefused,
// ticketRefusalReason) stay real, because which sentence a failure gets is
// the page's decision and those are the functions it makes it with.
vi.mock('@/utils/ticketAgentAPI', async () => ({
  ...(await vi.importActual<typeof import('@/utils/ticketAgentAPI')>('@/utils/ticketAgentAPI')),
  fetchTicketAnalytics: vi.fn(),
  fetchAssignees: vi.fn()
}))

// The roster the assignee breakdown reads names out of. Sana Reid is id 11
// because that is the id the assignee chart was labelling its bars with.
const roster: AssigneeOption[] = [{ id: 11, name: 'Sana Reid', assignable: true }]

/**
 * What `GET /admin/tickets/analytics/` advertises, in its order.
 *
 * The React list used to stop at six, one short of what the endpoint sends,
 * so `priority` was never in a fixture and the dropdown shipped showing it as
 * its own database key. What the fix rests on is that the page derives every
 * label rather than looking it up, which one test below pins by asking it for
 * a dimension nobody has written yet.
 */
const DIMENSIONS = ['region', 'userType', 'category', 'status', 'assignee', 'channel', 'priority']

/**
 * Every fixture goes through the real schema.
 *
 * The first React version of this file hand-wrote the payload and got five
 * keys wrong. The page rendered the literal string "undefined" in four places
 * and all five tests passed. Parsing here makes a fixture that does not match
 * what the endpoint returns fail in the fixture, not silently in the
 * assertions.
 */
function payload(overrides: Record<string, unknown> = {}): TicketAnalytics {
  return ticketAnalyticsSchema.parse({
    window: { from: null, to: null },
    demand: {
      volume: 7,
      categoryMix: [{ value: 'account_access', count: 4 }],
      channelMix: [{ value: 'portal', count: 7 }]
    },
    flow: {
      unassignedBacklog: 2,
      ageByStatus: [{ status: 'open', averageSeconds: 3600 }],
      reopens: 11,
      handOffs: 12
    },
    service: {
      firstResponseSeconds: 1800,
      answeredCount: 5,
      resolutionSeconds: 7200,
      resolvedCount: 3,
      overdue: 13
    },
    quality: {
      resolutionRate: 0.5,
      resolvedCount: 4,
      totalCount: 8,
      repeatContacts: 9,
      satisfaction: null,
      satisfactionAvailable: false
    },
    segment: { dimension: 'region', buckets: [{ value: 'Australia', count: 5 }] },
    dimensions: DIMENSIONS,
    ...overrides
  })
}

const envelope = (error: string, code: string) => ({ error, code, request_id: 'req-1' })

let wrapper: VueWrapper | null = null

async function openPage() {
  wrapper = mount(TicketAnalyticsPage)
  await flushPromises()
  return wrapper
}

const breakdown = () => wrapper!.find<HTMLSelectElement>('#ticket-analytics-dimension')

async function chooseDimension(value: string) {
  await breakdown().setValue(value)
  await flushPromises()
}

// A chart's numbers, read the way a screen reader reads them: from its table.
function bars(section: string): string[] {
  return wrapper!
    .find(`section[aria-labelledby="ticket-analytics-${section}"]`)
    .findAll('[data-testid="measure-table"] tr')
    .map((tr) => `${tr.find('th').text()}:${tr.find('td').text()}`)
}

// The tiles, as "label=value (hint)".
function tiles(section: string): string[] {
  return wrapper!
    .find(`section[aria-labelledby="ticket-analytics-${section}"]`)
    .findAll('.stat-tile')
    .map(
      (tile) =>
        `${tile.find('.stat-tile__label').text()}=${tile.find('.stat-tile__value').text()} (${tile.find('.stat-tile__hint').text()})`
    )
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(fetchTicketAnalytics).mockResolvedValue(payload())
  vi.mocked(fetchAssignees).mockResolvedValue(roster)
  // The page logs every failure the way the other admin pages do.
  vi.spyOn(console, 'warn').mockImplementation(() => {})
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.restoreAllMocks()
})

describe('TicketAnalyticsPage', () => {
  it('names the four questions the client wrote on p52, and the breakdown', async () => {
    await openPage()

    // The page is organised by the client's own four groups, and each carries
    // the question they wrote above it. Losing the questions would leave a
    // wall of numbers that answers nothing in particular.
    expect(wrapper!.findAll('h2').map((h2) => h2.text())).toEqual([
      'Demand · what help is being requested?',
      'Flow · where does work slow down?',
      'Service · how quickly do we respond?',
      'Quality · did the support help?',
      'Broken down by region'
    ])
  })

  it('says what the dates mean above the controls', async () => {
    await openPage()

    expect(wrapper!.find('h1').text()).toBe('Ticket analytics')
    expect(wrapper!.find('.ticket-analytics__subtitle').text()).toBe(
      'Dates are read as UTC, the same rule the ticket numbering uses. A window that starts on 1 March opens at 11am Sydney time.'
    )
  })

  it('renders the numbers, not the string undefined', async () => {
    // The assertion the first React version of this file was missing.
    await openPage()

    expect(wrapper!.text()).not.toContain('undefined')
    expect(tiles('demand')).toEqual(['Tickets raised=7 (In the selected window)'])
    expect(tiles('flow')).toEqual([
      'Unassigned=2 (Nobody has picked it up)',
      'Reopens=11 (Counted per event)',
      'Hand-offs=12 (Passed to someone else)'
    ])
    expect(tiles('quality')[1]).toBe('Came back=9 (People with more than one)')
  })

  it('writes the service times as durations, each against the count it averages', async () => {
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        service: {
          firstResponseSeconds: 1800,
          answeredCount: 5,
          // The value React printed as "1h 60m".
          resolutionSeconds: 7199,
          resolvedCount: 3,
          overdue: 13
        }
      })
    )
    await openPage()

    expect(tiles('service')).toEqual([
      'First reply=30m (Average of 5 answered)',
      'To resolve=2h (Average of 3 resolved)',
      'Overdue=13 (Waiting on support for longer than its priority allows)'
    ])
  })

  it('describes Overdue by the rule the number is actually counted with', async () => {
    // The client replaced "no first reply inside its window" on 2026-09-04:
    // the clock restarts every time the requester writes and stops every time
    // support answers. Word for word the sentence the queue's Overdue counter
    // carries, so the same number is not described two ways in one product.
    await openPage()

    expect(wrapper!.text()).toContain('Waiting on support for longer than its priority allows')
    expect(wrapper!.text().toLowerCase()).not.toContain('no first reply')
  })

  it('says satisfaction was never collected rather than showing a zero', async () => {
    // No survey has been sent, so a number here would be invented, and "0"
    // reads as "people are unhappy" rather than "nobody was asked".
    await openPage()

    expect(tiles('quality')[2]).toBe('Satisfaction=— (Not collected yet)')
  })

  it('keeps the React wording if the server ever says satisfaction is available', async () => {
    // Latent in React (U4 AN-25): the value stays a dash and only the hint
    // changes. The backend hard-codes false today; this pins parity, it is
    // not a design to build on.
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        quality: {
          resolutionRate: 0.5,
          resolvedCount: 4,
          totalCount: 8,
          repeatContacts: 9,
          satisfaction: null,
          satisfactionAvailable: true
        }
      })
    )
    await openPage()

    expect(tiles('quality')[2]).toBe('Satisfaction=— (Average rating)')
  })

  it('reports the resolution rate against the number it was taken from', async () => {
    await openPage()

    // "50%" from six tickets is a different claim from "50%" from six hundred.
    expect(tiles('quality')[0]).toBe('Resolved=50% (4 of 8)')
  })

  it('shows a dash, not a zero, when the window holds no tickets at all', async () => {
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        quality: {
          resolutionRate: null,
          resolvedCount: 0,
          totalCount: 0,
          repeatContacts: 0,
          satisfaction: null,
          satisfactionAvailable: false
        }
      })
    )
    await openPage()

    // A resolution rate of 0% for an empty window is a claim about nothing.
    expect(tiles('quality')[0]).toBe('Resolved=— (0 of 0)')
    expect(wrapper!.text()).not.toContain('0%')
  })

  it('labels the Demand bars in words, and an empty category the same way everywhere', async () => {
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        demand: {
          volume: 7,
          categoryMix: [
            { value: 'account_access', count: 4 },
            { value: '', count: 2 },
            { value: 'flagged_content', count: 1 }
          ],
          channelMix: [
            { value: 'portal', count: 5 },
            { value: 'ai_screening', count: 1 },
            { value: 'email', count: 1 }
          ]
        },
        segment: {
          dimension: 'category',
          buckets: [
            { value: 'account_access', count: 4 },
            { value: '', count: 2 }
          ]
        }
      })
    )
    await openPage()

    const [byCategory, byChannel] = wrapper!
      .find('section[aria-labelledby="ticket-analytics-demand"]')
      .findAll('[data-testid="measure-table"]')
      .map((table) => table.findAll('tr').map((tr) => `${tr.find('th').text()}:${tr.find('td').text()}`))
    expect(byCategory).toEqual(['Account and access:4', 'Not categorised:2', 'Flagged content:1'])
    expect(byChannel).toEqual(['Portal:5', 'Raised by screening:1', 'Email:1'])

    // React said "Not recorded" for the same empty bucket here (U4 AN-27).
    await chooseDimension('category')
    expect(bars('segment')).toEqual(['Account and access:4 tickets', 'Not categorised:2 tickets'])
  })

  it('draws how long each open status has sat, as durations, with a nothing-open sentence', async () => {
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        flow: {
          unassignedBacklog: 2,
          ageByStatus: [
            { status: 'pending_user', averageSeconds: 122400 },
            { status: 'open', averageSeconds: 3600 },
            // An average over nothing: drawn as a zero bar, as in React.
            { status: 'in_progress', averageSeconds: null }
          ],
          reopens: 11,
          handOffs: 12
        }
      })
    )
    await openPage()

    expect(bars('flow')).toEqual(['Pending user:34h', 'Open:1h', 'In progress:0m'])

    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({ flow: { unassignedBacklog: 0, ageByStatus: [], reopens: 0, handOffs: 0 } })
    )
    await wrapper!.find('#ticket-analytics-to').setValue('2026-09-03')
    await flushPromises()

    expect(
      wrapper!.find('section[aria-labelledby="ticket-analytics-flow"]').text()
    ).toContain('Nothing open in this window.')
  })

  it('says so when the figures could not be loaded', async () => {
    // Never a blank page dressed as data: an agent reading zeros they think
    // are real is worse than an agent who knows the request failed.
    vi.mocked(fetchTicketAnalytics).mockRejectedValue(new TypeError('Failed to fetch'))
    await openPage()

    expect(wrapper!.find('[role="alert"]').text()).toBe('Those numbers could not be loaded.')
    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(false)
  })

  it('blanks the page on a payload that does not match the schema, and says so', async () => {
    // U4 AN-18: the whole payload is parsed in one go, and the assignee id
    // once arrived as a number where the schema wanted a string. The parse
    // runs inside the real fetchTicketAnalytics; its rejection is replayed
    // here so the page's handling of it is what is tested.
    const broken = { ...payload(), segment: { dimension: 'assignee', buckets: [{ value: 11, count: 4 }] } }
    const parseFailure = await ticketAnalyticsSchema.parseAsync(broken).catch((error: unknown) => error)
    vi.mocked(fetchTicketAnalytics).mockRejectedValue(parseFailure)
    await openPage()

    expect(wrapper!.find('[role="alert"]').text()).toBe('Those numbers could not be loaded.')
    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(false)
  })

  it('tells a refused reader they lack access, not that something broke', async () => {
    vi.mocked(fetchTicketAnalytics).mockRejectedValue(
      new ApiError(envelope('You do not have support privileges.', 'permission_denied'), 403)
    )
    await openPage()

    expect(wrapper!.find('[role="alert"]').text()).toBe(
      'You do not have access to the ticket dashboard. It is open to the support team and to administrators.'
    )
  })

  it("repeats the server's reason when the window itself is the problem", async () => {
    // A range typed back to front is the reader's to fix, and the server has
    // already said so. "Those numbers could not be loaded" sends them looking
    // for a fault instead.
    vi.mocked(fetchTicketAnalytics).mockRejectedValue(
      new ApiError(envelope('from must be earlier than to.', 'invalid'), 400)
    )
    await openPage()

    expect(wrapper!.find('[role="alert"]').text()).toBe('from must be earlier than to.')
    // The controls stay, so the window can be fixed where it was typed.
    expect(wrapper!.find('#ticket-analytics-from').exists()).toBe(true)
    expect(wrapper!.find('#ticket-analytics-to').exists()).toBe(true)
  })

  it('shows the F-35 answer for a closing date past the end of the calendar', async () => {
    // to=9999-12-31 used to be a 500. The backend now answers 400 with this
    // sentence (views_admin.py _window_bound), and the page repeats it.
    vi.mocked(fetchTicketAnalytics)
      .mockResolvedValueOnce(payload())
      .mockRejectedValueOnce(
        new ApiError(envelope('to is outside the range of dates a report can cover.', 'invalid'), 400)
      )
    await openPage()

    await wrapper!.find('#ticket-analytics-to').setValue('9999-12-31')
    await flushPromises()

    expect(vi.mocked(fetchTicketAnalytics).mock.calls[1]![0]).toEqual({
      from: '',
      to: '9999-12-31',
      dimension: 'region'
    })
    expect(wrapper!.find('[role="alert"]').text()).toBe(
      'to is outside the range of dates a report can cover.'
    )
  })

  it('does not repeat a server fault back as if the reader could fix it', async () => {
    // The 500 envelope carries an `error` too, and it says "Internal server
    // error". Passing that on would be a worse sentence than the generic one.
    vi.mocked(fetchTicketAnalytics).mockRejectedValue(
      new ApiError(envelope('Internal server error', 'internal_server_error'), 500)
    )
    await openPage()

    expect(wrapper!.find('[role="alert"]').text()).toBe('Those numbers could not be loaded.')
  })

  it('sends the dates exactly as picked and echoes them back with no date ambiguity', async () => {
    /**
     * The native date input renders in the browser's locale: "mm/dd/yyyy" on
     * a machine set to US English, while the platform's users are Australian.
     * 03/09 is two different days depending on which you assume, and the
     * control cannot be told which to use.
     *
     * It also has to say "inclusive", because the closing date counts the
     * whole day named. That correction is the server's alone: the request
     * carries the day as typed, and adding one here would count it twice.
     */
    await openPage()
    expect(wrapper!.find('.ticket-analytics__window').exists()).toBe(false)

    await wrapper!.find('#ticket-analytics-from').setValue('2026-08-26')
    await flushPromises()
    expect(wrapper!.find('.ticket-analytics__window').text()).toBe(
      'Covering 26 Aug 2026 onwards, in UTC.'
    )

    await wrapper!.find('#ticket-analytics-to').setValue('2026-09-03')
    await flushPromises()
    expect(wrapper!.find('.ticket-analytics__window').text()).toBe(
      'Covering 26 Aug 2026 to 3 Sept 2026 inclusive, in UTC.'
    )
    expect(vi.mocked(fetchTicketAnalytics).mock.calls.map((call) => call[0])).toEqual([
      { from: '', to: '', dimension: 'region' },
      { from: '2026-08-26', to: '', dimension: 'region' },
      { from: '2026-08-26', to: '2026-09-03', dimension: 'region' }
    ])

    await wrapper!.find('#ticket-analytics-from').setValue('')
    await flushPromises()
    expect(wrapper!.find('.ticket-analytics__window').text()).toBe(
      'Covering everything up to and including 3 Sept 2026, in UTC.'
    )
  })

  it('names every dimension in English, including one nobody has written yet', async () => {
    // Neither "programStage" nor "first_response" is a dimension the backend
    // has. They stand in for whichever one it adds next. Two spellings,
    // because the backend writes some names in camelCase and the database
    // writes most of its own in snake_case.
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({ dimensions: [...DIMENSIONS, 'programStage', 'first_response'] })
    )
    await openPage()

    expect(wrapper!.find('label[for="ticket-analytics-dimension"]').text()).toBe('Break down by')
    expect(breakdown().findAll('option').map((option) => option.text())).toEqual([
      'Region',
      'User type',
      'Category',
      'Status',
      'Assignee',
      'Channel',
      'Priority',
      'Program stage',
      'First response'
    ])
  })

  it('asks for the chosen breakdown and retitles the card after it', async () => {
    await openPage()
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({ segment: { dimension: 'userType', buckets: [{ value: 'mentor', count: 3 }] } })
    )

    await chooseDimension('userType')

    expect(vi.mocked(fetchTicketAnalytics).mock.lastCall![0]).toEqual({
      from: '',
      to: '',
      dimension: 'userType'
    })
    expect(wrapper!.findAll('h2').at(-1)!.text()).toBe('Broken down by user type')
    expect(bars('segment')).toEqual(['mentor:3 tickets'])
  })

  it('labels the assignee breakdown with names, never with user ids', async () => {
    // The chart the client asked for by name. A bar labelled "11" answers
    // "who is carrying the load?" with a number nobody can read.
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        segment: {
          dimension: 'assignee',
          buckets: [
            { value: '', count: 9 },
            { value: '11', count: 4 },
            { value: '77', count: 1 }
          ]
        }
      })
    )
    await openPage()
    await chooseDimension('assignee')

    // 77 is nobody on the roster, which is what a deleted account looks like.
    // An id is a poor label; a blank one would be worse.
    expect(bars('segment')).toEqual(['Not recorded:9 tickets', 'Sana Reid:4 tickets', '#77:1 tickets'])
  })

  it('tells the reader why the bars are ids when the roster did not load', async () => {
    // The failure mode of the fix above is the defect it fixed: no roster, and
    // every bar reads "#11" again.
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({ segment: { dimension: 'assignee', buckets: [{ value: '11', count: 4 }] } })
    )
    vi.mocked(fetchAssignees).mockRejectedValue(new TypeError('Failed to fetch'))
    await openPage()

    // Region is on screen first, and it does not read the roster at all.
    // Warning about labels nobody is looking at is noise.
    expect(wrapper!.find('[role="alert"]').exists()).toBe(false)

    await chooseDimension('assignee')

    expect(wrapper!.find('[role="alert"]').text()).toBe(
      'The assignee list could not be loaded, so the bars below are labelled with user ids instead of names. Reload to try again.'
    )
    expect(bars('segment')).toEqual(['#11:4 tickets'])
  })

  it('keeps two agents apart when they share a display name', async () => {
    // Before the names went in, the labels were ids and were distinct by
    // construction; a name on its own puts two bars on the chart with one
    // caption between them.
    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        segment: {
          dimension: 'assignee',
          buckets: [
            { value: '3', count: 5 },
            { value: '4', count: 2 },
            { value: '11', count: 1 }
          ]
        }
      })
    )
    vi.mocked(fetchAssignees).mockResolvedValue([
      { id: 3, name: 'Sam Reid', assignable: true },
      { id: 4, name: 'Sam Reid', assignable: true },
      { id: 11, name: 'Sana Reid', assignable: true }
    ])
    await openPage()
    await chooseDimension('assignee')

    // Sana Reid is nobody else, so her bar keeps a name and nothing else.
    expect(bars('segment')).toEqual([
      'Sam Reid #3:5 tickets',
      'Sam Reid #4:2 tickets',
      'Sana Reid:1 tickets'
    ])
  })

  it('writes priorities, statuses and channels the way every other screen writes them', async () => {
    await openPage()

    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        segment: {
          dimension: 'priority',
          buckets: [
            { value: 'normal', count: 6 },
            { value: 'high', count: 2 },
            { value: 'low', count: 1 }
          ]
        }
      })
    )
    await chooseDimension('priority')
    expect(bars('segment')).toEqual(['Normal:6 tickets', 'High:2 tickets', 'Low:1 tickets'])

    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({
        segment: {
          dimension: 'status',
          buckets: [
            { value: 'in_progress', count: 3 },
            { value: 'pending_user', count: 1 }
          ]
        }
      })
    )
    await chooseDimension('status')
    expect(bars('segment')).toEqual(['In progress:3 tickets', 'Pending user:1 tickets'])

    vi.mocked(fetchTicketAnalytics).mockResolvedValue(
      payload({ segment: { dimension: 'channel', buckets: [{ value: 'ai_screening', count: 2 }] } })
    )
    await chooseDimension('channel')
    expect(bars('segment')).toEqual(['Raised by screening:2 tickets'])
  })

  it('keeps naming the chosen breakdown while the window is refused', async () => {
    // The options come from the payload, and a refused window has none. The
    // React control went blank, so the one thing the reader had just chosen
    // stopped being on screen at the moment they were told something is wrong.
    await openPage()
    await chooseDimension('priority')

    vi.mocked(fetchTicketAnalytics).mockRejectedValue(
      new ApiError(envelope('from must be earlier than to.', 'invalid'), 400)
    )
    await wrapper!.find('#ticket-analytics-from').setValue('2026-09-10')
    await flushPromises()

    expect(wrapper!.find('[role="alert"]').text()).toBe('from must be earlier than to.')
    expect(breakdown().element.selectedOptions[0]?.textContent?.trim()).toBe('Priority')
  })

  it('blanks the cards while a new window loads, rather than showing the old numbers under it', async () => {
    // U4 AN-17, kept as React had it: nothing holds the previous payload, so
    // no number on screen ever belongs to a window the inputs no longer show.
    await openPage()
    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(true)

    let answer: (value: TicketAnalytics) => void = () => {}
    vi.mocked(fetchTicketAnalytics).mockImplementationOnce(
      () => new Promise((resolve) => (answer = resolve))
    )
    await wrapper!.find('#ticket-analytics-to').setValue('2026-09-03')

    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(false)
    expect(wrapper!.find('.ticket-analytics__loading').text()).toBe('Loading…')

    answer(payload())
    await flushPromises()

    expect(wrapper!.find('.ticket-analytics__loading').exists()).toBe(false)
    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(true)
  })

  it('paints only the answer for the window on screen when two requests finish out of order', async () => {
    // Every keystroke in a date box is a request. React Query keyed the
    // answers by window; here a token does the same job.
    let firstAnswer: (value: TicketAnalytics) => void = () => {}
    vi.mocked(fetchTicketAnalytics)
      .mockImplementationOnce(() => new Promise((resolve) => (firstAnswer = resolve)))
      .mockResolvedValueOnce(payload({ demand: { volume: 42, categoryMix: [], channelMix: [] } }))
    await openPage()

    await wrapper!.find('#ticket-analytics-to').setValue('2026-09-03')
    await flushPromises()
    expect(tiles('demand')).toEqual(['Tickets raised=42 (In the selected window)'])

    // The request for the old window lands last.
    firstAnswer(payload({ demand: { volume: 1, categoryMix: [], channelMix: [] } }))
    await flushPromises()

    expect(tiles('demand')).toEqual(['Tickets raised=42 (In the selected window)'])
    expect(wrapper!.find('.ticket-analytics__loading').exists()).toBe(false)
  })

  it('does not raise an alert for a window the inputs have already left', async () => {
    // The failing request is for the old window; the numbers on screen are
    // for the new one. An alert over them would say those numbers failed.
    let firstFails: (reason: unknown) => void = () => {}
    vi.mocked(fetchTicketAnalytics)
      .mockImplementationOnce(() => new Promise((_, reject) => (firstFails = reject)))
      .mockResolvedValueOnce(payload({ demand: { volume: 42, categoryMix: [], channelMix: [] } }))
    await openPage()

    await wrapper!.find('#ticket-analytics-to').setValue('2026-09-03')
    await flushPromises()
    firstFails(new ApiError(envelope('from must be earlier than to.', 'invalid'), 400))
    await flushPromises()

    expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    expect(tiles('demand')).toEqual(['Tickets raised=42 (In the selected window)'])
  })

  it('keeps saying Loading while the newest request is still out, whatever older ones do', async () => {
    let newestAnswer: (value: TicketAnalytics) => void = () => {}
    let oldestAnswer: (value: TicketAnalytics) => void = () => {}
    vi.mocked(fetchTicketAnalytics)
      .mockImplementationOnce(() => new Promise((resolve) => (oldestAnswer = resolve)))
      .mockImplementationOnce(() => new Promise((resolve) => (newestAnswer = resolve)))
    await openPage()
    await wrapper!.find('#ticket-analytics-to').setValue('2026-09-03')

    // The old window's answer arrives while the new window's is still out.
    oldestAnswer(payload())
    await flushPromises()

    expect(wrapper!.find('.ticket-analytics__loading').text()).toBe('Loading…')
    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(false)

    newestAnswer(payload())
    await flushPromises()

    expect(wrapper!.find('.ticket-analytics__loading').exists()).toBe(false)
    expect(wrapper!.find('.ticket-analytics__grid').exists()).toBe(true)
  })

  it('drops the complaint once the window is fixed', async () => {
    vi.mocked(fetchTicketAnalytics).mockRejectedValueOnce(
      new ApiError(envelope('from must be earlier than to.', 'invalid'), 400)
    )
    await openPage()
    expect(wrapper!.find('[role="alert"]').text()).toBe('from must be earlier than to.')

    await wrapper!.find('#ticket-analytics-from').setValue('2026-08-01')
    await flushPromises()

    expect(wrapper!.find('[role="alert"]').exists()).toBe(false)
    expect(tiles('demand')).toEqual(['Tickets raised=7 (In the selected window)'])
  })

  it('asks the server again every time the page opens rather than reusing an earlier answer', async () => {
    // U4 AN-05: React's app-wide cache showed a revisited window's old
    // numbers. Each mount here is a fresh read of both the numbers and the
    // roster.
    await openPage()
    wrapper!.unmount()
    wrapper = null
    await openPage()

    expect(vi.mocked(fetchTicketAnalytics)).toHaveBeenCalledTimes(2)
    expect(vi.mocked(fetchTicketAnalytics).mock.calls[1]![0]).toEqual({
      from: '',
      to: '',
      dimension: 'region'
    })
    expect(vi.mocked(fetchAssignees)).toHaveBeenCalledTimes(2)
  })
})
