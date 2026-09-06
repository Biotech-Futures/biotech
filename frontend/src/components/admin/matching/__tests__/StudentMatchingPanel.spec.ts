import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import StudentMatchingPanel from '@/components/admin/matching/StudentMatchingPanel.vue'

/**
 * Integration coverage for the Student Matching tab: the panel, its composable,
 * the Zod parsing layer and adminAPI are all real here — only `fetch` is faked,
 * so a break anywhere along that chain shows up.
 *
 * Payloads deliberately use the backend's snake_case wrapper keys
 * (`unmatched_students`, `not_full_groups`) and the flat per-student
 * `recommendations` shape, which is what MatchStudentView actually returns.
 */

const scoreBreakdown = {
  baseScore: 100,
  yearPenalty: 0,
  countryPenalty: 12,
  timezonePenalty: 0,
  sizeBonus: 3,
  totalPenalty: 12,
  objectiveScore: 91
}

const targetGroup = {
  id: 10,
  groupName: 'BTF10',
  maxSize: 5,
  tutor: null,
  groupStudent: []
}

const matchData = {
  recommendations: [
    {
      student: {
        id: 1,
        name: 'Ava Nguyen',
        country: 'Australia',
        yearLevel: 10,
        interests: ['Biology']
      },
      recommendGroup: targetGroup,
      reason: 'Shares interest biology with the group.',
      score: 88,
      scoreBreakdown
    }
  ],
  unmatched_students: [
    {
      student: { id: 2, name: 'Liam Costa', interests: [] },
      reason: 'NO_SHARED_INTEREST',
      score: 0,
      scoreBreakdown: null
    }
  ],
  not_full_groups: [
    {
      id: 11,
      groupName: 'BTF11',
      maxSize: 5,
      tutor: null,
      groupStudent: [{ id: 5, name: 'Nina Larsen', interests: ['Bioethics'] }],
      student_count: 1,
      available_seats: 4
    }
  ]
}

const jsonResponse = (payload: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { 'Content-Type': 'application/json' }
    })
  )

const fetchMock = (options: { match?: unknown; matchStatus?: number } = {}) =>
  vi.fn().mockImplementation((url: string) => {
    if (String(url).includes('/services/csrf/')) {
      return jsonResponse({ csrfToken: 'csrf-test' })
    }
    if (String(url).includes('/match/confirm/')) {
      return jsonResponse({ msg: 'ok', data: { assigned_count: 1 } })
    }
    if (String(url).includes('/match/student/')) {
      if (options.matchStatus && options.matchStatus >= 400) {
        return jsonResponse({ msg: 'Server error' }, options.matchStatus)
      }
      return jsonResponse({ msg: 'ok', data: options.match ?? matchData })
    }
    return jsonResponse({})
  })

const buttonByText = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('button').find((button) => button.text().trim().startsWith(label))

const runMatch = async (wrapper: VueWrapper) => {
  await buttonByText(wrapper, 'Run match')!.trigger('click')
  await flushPromises()
}

let wrapper: VueWrapper | null = null

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  document.body.innerHTML = ''
  vi.unstubAllGlobals()
})

describe('StudentMatchingPanel', () => {
  it('prompts to run the matcher instead of showing an empty board', () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)

    // An unrun board must not read as a finished one with nothing left to do.
    expect(wrapper.text()).toContain('Click')
    expect(wrapper.text()).toContain('to load recommended groups')
    expect(wrapper.text()).not.toContain('Waiting Area')
  })

  it('does not call the matcher on mount', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)
    await flushPromises()

    const calls = fetch.mock.calls.filter((call) => String(call[0]).includes('/match/student/'))
    expect(calls).toHaveLength(0)
  })

  it('renders proposed groups, the waiting area and the stats after a run', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.text()).toContain('BTF10')
    expect(wrapper.text()).toContain('Ava Nguyen')
    // Unmatched students start in the waiting area.
    expect(wrapper.text()).toContain('Waiting Area')
    expect(wrapper.text()).toContain('Liam Costa')
    // notFullGroups render as drop targets even with nobody proposed for them.
    expect(wrapper.text()).toContain('BTF11')
    expect(wrapper.text()).toContain('Nina Larsen')
    expect(wrapper.text()).toContain('Total groups')
  })

  it('shows the size-bonus-inclusive score on the chip', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    // Scoped to Ava's chip: the waiting area renders first, so a bare find()
    // would pick up the unmatched student's chip instead.
    const avaChip = wrapper
      .findAll('.student-chip')
      .find((chip) => chip.text().includes('Ava Nguyen'))
    expect(avaChip).toBeDefined()

    // objectiveScore (91), not score (88) — the badge must agree with the
    // breakdown shown in the hover card.
    expect(avaChip!.find('.student-chip__score').text()).toBe('91')
  })

  it('surfaces a failed run with a retry action', async () => {
    vi.stubGlobal('fetch', fetchMock({ matchStatus: 500 }))
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    expect(buttonByText(wrapper, 'Retry')).toBeDefined()
    // A half-loaded board would be worse than none: confirming it would write
    // the wrong assignments.
    expect(wrapper.text()).not.toContain('BTF10')
  })

  it('rejects a malformed payload rather than rendering coerced defaults', async () => {
    vi.stubGlobal(
      'fetch',
      // Student with no id — the exact shape that used to be coerced to 0 and
      // posted to /match/confirm/.
      fetchMock({
        match: {
          recommendations: [
            { student: { name: 'Nameless' }, recommendGroup: targetGroup, score: 10 }
          ]
        }
      })
    )
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.find('[role="alert"]').text()).toContain('Student matching')
    expect(wrapper.text()).not.toContain('Nameless')
  })

  it('keeps confirm disabled until a match has been run', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)

    const confirm = buttonByText(wrapper, 'Confirm')!
    expect(confirm.attributes('disabled')).toBeDefined()

    await runMatch(wrapper)
    expect(buttonByText(wrapper, 'Confirm')!.attributes('disabled')).toBeUndefined()
  })

  it('posts the proposed assignments on confirm', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    await buttonByText(wrapper, 'Confirm')!.trigger('click')
    await flushPromises()

    const confirmCall = fetch.mock.calls.find((call) =>
      String(call[0]).includes('/match/confirm/')
    )
    expect(confirmCall).toBeDefined()
    const body = JSON.parse((confirmCall![1] as RequestInit).body as string)
    expect(body.assignments).toEqual([{ studentId: 1, groupId: 10 }])
  })

  it('filters the board with the group filter', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.text()).toContain('BTF11')

    // "Has recommended students" hides the group nobody was proposed for.
    await wrapper.find('select').setValue('needs_action')
    expect(wrapper.text()).toContain('BTF10')
    expect(wrapper.text()).not.toContain('BTF11')
  })
})
