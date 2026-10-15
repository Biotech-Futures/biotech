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
  timezonePenalty: 12,
  sizeBonus: 3,
  totalPenalty: 12,
  objectiveScore: 91
}

/** A group the matcher proposes forming — the only kind of automatic target. */
const targetGroup = {
  id: 'new-Australia-1',
  groupName: 'Suggested Group 1',
  maxSize: 5,
  tutor: null,
  groupStudent: []
}

/**
 * An already-formed group. The backend can still propose joins into one until
 * its MA3 gating lands, so the board has to refuse it on its own.
 */
const formedGroup = {
  id: 10,
  groupName: 'BTF10',
  maxSize: 5,
  tutor: null,
  groupStudent: [{ id: 6, name: 'Theo Park', interests: ['Biology'] }]
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
    },
    {
      student: { id: 3, name: 'Omar Haddad', country: 'Australia', interests: ['Biology'] },
      recommendGroup: formedGroup,
      reason: 'Joins an existing group.',
      score: 80,
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
    if (String(url).includes('/matching/configs/active/')) {
      return jsonResponse({
        data: null,
        weights: {
          yearWeight: 8.0,
          timezoneWeight: 2.0,
          timezoneMaxPenalty: 18.0,
          sizeBonusWeight: 6.0
        },
        requiredTotal: '100.00',
        defaults: {
          year_weight: 20.0,
          timezone_weight: 30.0,
          timezone_max_weight: 25.0,
          size_bonus_weight: 25.0
        }
      })
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

const modeButton = (wrapper: VueWrapper, label: string) =>
  wrapper.findAll('[role="radio"]').find((button) => button.text().trim() === label)!

const matchUrls = (fetch: ReturnType<typeof fetchMock>) =>
  fetch.mock.calls.map((call) => String(call[0])).filter((url) => url.includes('/match/student/'))

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

  it('heads the tab "Student Grouping" rather than repeating the tab name', () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)

    // Mirrors the Mentor Matching tab's "Mentor Assignment" heading.
    expect(wrapper.find('h2').text()).toBe('Student Grouping')
    expect(wrapper.text()).toContain(
      'Run the algorithm, review suggested groups, then confirm assignments.'
    )
  })

  it('lists the modes Strict, Balanced, Coverage', () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)

    const radios = wrapper.findAll('[role="radio"]')
    expect(radios.map((radio) => radio.text().trim())).toEqual(['Strict', 'Balanced', 'Coverage'])
  })

  it('defaults to balanced mode, though it is not listed first', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)

    expect(modeButton(wrapper, 'Balanced').attributes('aria-checked')).toBe('true')
    expect(modeButton(wrapper, 'Strict').attributes('aria-checked')).toBe('false')
    expect(modeButton(wrapper, 'Coverage').attributes('aria-checked')).toBe('false')

    await runMatch(wrapper)
    expect(matchUrls(fetch)).toEqual([expect.stringContaining('/match/student/?mode=balanced')])
  })

  it('describes each mode in a tooltip tied to its button', () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)

    const strict = modeButton(wrapper, 'Strict')
    const tip = wrapper.find(`#${strict.attributes('aria-describedby')}`)
    expect(tip.attributes('role')).toBe('tooltip')
    expect(tip.text()).toContain('same country')
  })

  it('sends the selected mode to the matcher', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)

    await runMatch(wrapper)
    await modeButton(wrapper, 'Strict').trigger('click')
    expect(modeButton(wrapper, 'Strict').attributes('aria-checked')).toBe('true')
    expect(modeButton(wrapper, 'Balanced').attributes('aria-checked')).toBe('false')
    await runMatch(wrapper)
    await modeButton(wrapper, 'Coverage').trigger('click')
    await runMatch(wrapper)

    expect(matchUrls(fetch)).toEqual([
      expect.stringContaining('/match/student/?mode=balanced'),
      expect.stringContaining('/match/student/?mode=strict'),
      expect.stringContaining('/match/student/?mode=coverage')
    ])
    // MA3 holds in every mode: the formed group is still never a target.
    expect(wrapper.text()).toContain('Suggested Group 1')
    expect(wrapper.text()).not.toContain('BTF10')
  })

  it('clears the board when the matching mode changes', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)
    expect(wrapper.text()).toContain('Suggested Group 1')

    // Results are mode-specific; leaving stale ones on screen would
    // misrepresent what is about to be confirmed.
    await modeButton(wrapper, 'Coverage').trigger('click')

    expect(wrapper.text()).not.toContain('Suggested Group 1')
    expect(wrapper.text()).not.toContain('Waiting Area')
    expect(wrapper.text()).toContain('to load recommended groups')
    expect(buttonByText(wrapper, 'Confirm')!.attributes('disabled')).toBeDefined()
    expect(buttonByText(wrapper, 'Reset board')!.attributes('disabled')).toBeDefined()
  })

  it('keeps the board when the active mode is clicked again', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    await modeButton(wrapper, 'Balanced').trigger('click')

    expect(wrapper.text()).toContain('Suggested Group 1')
    expect(matchUrls(fetch)).toHaveLength(1)
  })

  it('does not load the scoring weights until they are opened', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)
    await flushPromises()

    expect(buttonByText(wrapper, 'Scoring weights')!.attributes('aria-expanded')).toBe('false')
    // The toggle shares the panel's "Scoring weights" name, so check the panel.
    expect(wrapper.find('#matching-config-title').exists()).toBe(false)
    expect(fetch.mock.calls.some((call) => String(call[0]).includes('/matching/configs/'))).toBe(
      false
    )
  })

  it('opens the student matching weights editor from the toolbar', async () => {
    const fetch = fetchMock()
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)

    const toggle = buttonByText(wrapper, 'Scoring weights')!
    await toggle.trigger('click')
    await flushPromises()

    expect(toggle.attributes('aria-expanded')).toBe('true')
    const region = wrapper.find(`#${toggle.attributes('aria-controls')}`)
    expect(region.attributes('hidden')).toBeUndefined()
    expect(region.find('#matching-config-title').text()).toBe('Scoring weights')
    expect(region.text()).toContain('Changes apply to the next student matching run.')

    // Collapsing hides it but keeps it mounted, so edits survive and reopening
    // does not refetch.
    await toggle.trigger('click')
    expect(region.attributes('hidden')).toBeDefined()
    await toggle.trigger('click')
    await flushPromises()
    const activeCalls = fetch.mock.calls.filter((call) =>
      String(call[0]).includes('/matching/configs/active/')
    )
    expect(activeCalls).toHaveLength(1)
  })

  it('renders proposed groups and the waiting area after a run', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.text()).toContain('Suggested Group 1')
    expect(wrapper.text()).toContain('Ava Nguyen')
    // Unmatched students start in the waiting area.
    expect(wrapper.text()).toContain('Waiting Area')
    expect(wrapper.text()).toContain('Liam Costa')
  })

  it('shows no summary stat tiles, before or after a run', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)

    // Removed: with no data before a run they had nothing to say, and after a
    // run the board already shows the same information.
    const statLabels = ['Total groups', 'Visible groups', 'Open seats', 'Waiting students']
    for (const label of statLabels) expect(wrapper.text()).not.toContain(label)

    await runMatch(wrapper)
    for (const label of statLabels) expect(wrapper.text()).not.toContain(label)
  })

  it('does not offer already-formed groups as drop targets', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    const groupNames = wrapper
      .findAll('.student-matching__board article')
      .map((card) => card.text())
    expect(groupNames).toHaveLength(1)
    expect(groupNames[0]).toContain('Suggested Group 1')
    // Neither a not-full group nor one the matcher proposed a join into.
    expect(wrapper.text()).not.toContain('BTF11')
    expect(wrapper.text()).not.toContain('Nina Larsen')
    expect(wrapper.text()).not.toContain('BTF10')
    expect(wrapper.text()).not.toContain('Theo Park')
  })

  it('keeps students recommended into an existing group in the waiting area', async () => {
    vi.stubGlobal('fetch', fetchMock())
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    const waitingArea = wrapper.find('.student-matching__waiting')
    expect(waitingArea.text()).toContain('Omar Haddad')
    expect(waitingArea.text()).toContain('Liam Costa')
    expect(waitingArea.text()).toContain('2 students')
    // Not offered as a pointer back to the formed group either.
    expect(waitingArea.text()).not.toContain('BTF10')
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
    expect(wrapper.text()).not.toContain('Suggested Group 1')
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

  it('confirms a newly formed group with its synthetic id intact', async () => {
    const fetch = fetchMock({
      match: {
        recommendations: [
          {
            student: { id: 7, name: 'Priya Raman', interests: ['Genetics'] },
            // The matcher proposes forming a group that has no row yet; the
            // backend creates it from this id on confirm.
            recommendGroup: {
              id: 'new-Australia-7',
              groupName: 'Suggested Group',
              maxSize: 5,
              tutor: null,
              groupStudent: []
            },
            reason: 'Formed a new group.',
            score: 92,
            scoreBreakdown: null
          }
        ]
      }
    })
    vi.stubGlobal('fetch', fetch)
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Suggested Group')
    expect(wrapper.text()).toContain('Priya Raman')

    await buttonByText(wrapper, 'Confirm')!.trigger('click')
    await flushPromises()

    const confirmCall = fetch.mock.calls.find((call) =>
      String(call[0]).includes('/match/confirm/')
    )
    const body = JSON.parse((confirmCall![1] as RequestInit).body as string)
    expect(body.assignments).toEqual([{ studentId: 7, groupId: 'new-Australia-7' }])
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
    // Omar's join into the formed group BTF10 is never written.
    expect(body.assignments).toEqual([{ studentId: 1, groupId: 'new-Australia-1' }])
  })

  it('filters the board with the group filter', async () => {
    const recommend = (id: number, name: string, group: typeof targetGroup) => ({
      student: { id, name, interests: [] },
      recommendGroup: group,
      reason: 'Formed a new group.',
      score: 90,
      scoreBreakdown: null
    })
    const fullGroup = {
      ...targetGroup,
      id: 'new-Australia-2',
      groupName: 'Suggested Group 2',
      maxSize: 1
    }
    vi.stubGlobal(
      'fetch',
      fetchMock({
        match: {
          recommendations: [
            recommend(1, 'Ava Nguyen', targetGroup),
            recommend(2, 'Liam Costa', fullGroup)
          ]
        }
      })
    )
    wrapper = mount(StudentMatchingPanel)
    await runMatch(wrapper)

    expect(wrapper.text()).toContain('Suggested Group 1')
    expect(wrapper.text()).toContain('Suggested Group 2')

    // "Full groups" hides the proposed group that still has open seats.
    await wrapper.find('select').setValue('full')
    expect(wrapper.text()).toContain('Suggested Group 2')
    expect(wrapper.text()).not.toContain('Suggested Group 1')
  })
})
